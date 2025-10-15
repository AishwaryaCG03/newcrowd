import os
import time
import tempfile
import numpy as np
import pandas as pd
import streamlit as st
from datetime import datetime
import cv2

from db import add_alert
from prediction import bottleneck_probability, forecast_next, simulate_crowd_series
from ultralytics import YOLO

def _nms(rects, weights, iou_thresh=0.4):
    if len(rects) == 0:
        return []
    boxes = np.array(rects, dtype=float)
    scores = np.array(weights if weights is not None else [1.0]*len(rects), dtype=float)
    x1 = boxes[:, 0]
    y1 = boxes[:, 1]
    x2 = boxes[:, 0] + boxes[:, 2]
    y2 = boxes[:, 1] + boxes[:, 3]
    areas = (x2 - x1 + 1) * (y2 - y1 + 1)
    idxs = np.argsort(scores)
    pick = []
    while len(idxs) > 0:
        i = idxs[-1]
        pick.append(i)
        xx1 = np.maximum(x1[i], x1[idxs[:-1]])
        yy1 = np.maximum(y1[i], y1[idxs[:-1]])
        xx2 = np.minimum(x2[i], x2[idxs[:-1]])
        yy2 = np.minimum(y2[i], y2[idxs[:-1]])
        w = np.maximum(0, xx2 - xx1 + 1)
        h = np.maximum(0, yy2 - yy1 + 1)
        inter = w * h
        iou = inter / (areas[i] + areas[idxs[:-1]] - inter + 1e-9)
        idxs = idxs[np.where(iou <= iou_thresh)[0]]
    return [tuple(map(int, rects[i])) for i in pick]


def _estimate_from_video(file_bytes: bytes, area_m2: float, meters_per_pixel: float, frame_stride: int, max_frames: int):
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
    try:
        tmp.write(file_bytes)
        tmp.flush()
        tmp.close()
        cap = cv2.VideoCapture(tmp.name)
        fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        yolo_model = YOLO("yolov8n.pt")
        prev_gray = None
        densities = []
        flows = []
        total = 0
        idx = 0
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            if (idx % frame_stride) != 0:
                idx += 1
                continue
            img = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            rects = []
            res = yolo_model.predict(frame, conf=0.35, iou=0.45, imgsz=640, verbose=False)[0]
            if res and res.boxes is not None:
                b = res.boxes
                cls = b.cls.cpu().numpy().astype(int)
                xyxy = b.xyxy.cpu().numpy()
                for j in range(len(cls)):
                    if cls[j] == 0:  # person class
                        x1, y1, x2, y2 = xyxy[j]
                        rects.append((int(x1), int(y1), int(x2 - x1), int(y2 - y1)))
            count = len(rects)
            density = count / max(area_m2, 1e-6)
            densities.append(density)
            if prev_gray is not None:
                flow = cv2.calcOpticalFlowFarneback(prev_gray, img, None, 0.5, 3, 15, 3, 5, 1.2, 0)
                mag, ang = cv2.cartToPolar(flow[..., 0], flow[..., 1])
                mean_pix_per_frame = float(np.nanmean(mag))
                mps = mean_pix_per_frame * meters_per_pixel * fps
                flows.append(mps)
            prev_gray = img
            total += 1
            idx += 1
            if total >= max_frames:
                break
        cap.release()
        density_series = np.array(densities, dtype=float)
        velocity_mps = float(np.nanmedian(flows)) if flows else 0.8
        return density_series, velocity_mps
    finally:
        try:
            os.unlink(tmp.name)
        except Exception:
            pass


def predictive_page():
    st.header("Predictive Bottleneck Analysis")
    sim = st.session_state.sim
    with st.expander("Simulation Controls", expanded=True):
        sim["zone"] = st.text_input("Zone", value=sim.get("zone", "North Gate"))
        base_density = st.slider("Base Density (people/m²)", 0.2, 5.0, 2.5, 0.1)
        sim["velocity"] = st.slider("Average Velocity (m/s)", 0.0, 2.0, float(sim.get("velocity", 1.2)), 0.1)
        if st.button("Regenerate Series"):
            sim["density_series"] = simulate_crowd_series(60, base_density)

    with st.expander("Local Camera (OpenCV)", expanded=False):
        cols = st.columns(4)
        with cols[0]:
            lc_index = st.number_input("Camera Index", min_value=0, value=0, step=1, key="lc_index")
        with cols[1]:
            lc_area_m2 = st.number_input("Observed Area (m²)", min_value=1.0, value=100.0, step=1.0, key="lc_area")
        with cols[2]:
            lc_mpp = st.number_input("Meters per Pixel", min_value=0.0001, value=0.02, step=0.005, format="%.4f", key="lc_mpp")
        with cols[3]:
            lc_stride = st.number_input("Frame Stride", min_value=1, value=2, step=1, key="lc_stride")

        if "local_cam" not in st.session_state:
            st.session_state.local_cam = {
                "running": False,
                "densities": [],
                "flows": [],
                "count": 0,
                "rate_per_hour": 0.0,
            }

        lc = st.session_state.local_cam
        c1, c2 = st.columns([1, 1])
        start_clicked = c1.button("Start Local Camera")
        stop_clicked = c2.button("Stop")
        frame_ph = st.empty()

        if start_clicked:
            lc.update({"running": True, "densities": [], "flows": [], "count": 0, "rate_per_hour": 0.0})
        if stop_clicked:
            lc["running"] = False

        if lc.get("running"):
            cap = cv2.VideoCapture(int(lc_index))
            if not cap.isOpened():
                st.error("Could not open camera. Try a different index.")
                lc["running"] = False
            else:
                yolo_model = YOLO("yolov8n.pt")
                i = 0
                t_end = time.time() + 30
                prev_gray = None
                history = []
                ema_count = 0.0
                while lc.get("running") and time.time() < t_end:
                    ok, frame = cap.read()
                    if not ok:
                        break
                    if (i % int(lc_stride)) != 0:
                        i += 1
                        continue
                    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                    rects = []
                    res = yolo_model.predict(frame, conf=0.35, iou=0.45, imgsz=640, verbose=False)[0]
                    if res and res.boxes is not None:
                        b = res.boxes
                        cls = b.cls.cpu().numpy().astype(int)
                        xyxy = b.xyxy.cpu().numpy()
                        for j in range(len(cls)):
                            if cls[j] == 0:
                                x1, y1, x2, y2 = xyxy[j]
                                rects.append((int(x1), int(y1), int(x2 - x1), int(y2 - y1)))
                    count = int(len(rects))
                    if i == 0:
                        ema_count = float(count)
                    else:
                        ema_count = 0.3 * float(count) + 0.7 * float(ema_count)
                    density = count / max(float(lc_area_m2), 1e-6)
                    lc["densities"].append(density)
                    ts = time.time()
                    history.append((ts, ema_count))
                    cutoff = ts - 300.0
                    history = [(t, c) for (t, c) in history if t >= cutoff]
                    lc["count"] = int(ema_count)
                    if len(history) >= 2:
                        t0, c0 = history[0]
                        t1, c1v = history[-1]
                        dt = max(t1 - t0, 1e-3)
                        lc["rate_per_hour"] = float(((c1v - c0) / dt) * 3600.0)
                    if prev_gray is not None:
                        flow = cv2.calcOpticalFlowFarneback(prev_gray, gray, None, 0.5, 3, 15, 3, 5, 1.2, 0)
                        mag, _ = cv2.cartToPolar(flow[..., 0], flow[..., 1])
                        mean_pix = float(np.nanmean(mag))
                        fps = 15.0
                        mps = mean_pix * float(lc_mpp) * fps
                        lc["flows"].append(mps)
                    prev_gray = gray
                    for (x, y, w, h) in rects:
                        cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
                    flows_buf = lc.get('flows', [])
                    last_vel = flows_buf[-1] if flows_buf else 0.0
                    hud = f"count={lc['count']} density={density:.2f}/m² vel={last_vel:.2f} m/s rate={lc['rate_per_hour']:.1f}/h"
                    cv2.putText(frame, hud, (10, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)
                    frame_ph.image(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB), channels="RGB")
                    time.sleep(0.03)
                    i += 1
                cap.release()
                lc["running"] = False
    with st.expander("Camera-based Estimation", expanded=False):
        file = st.file_uploader("Upload crowd video (mp4/avi)", type=["mp4", "avi", "mov"], key="crowd_video")
        cols = st.columns(3)
        with cols[0]:
            area_m2 = st.number_input("Observed Area (m²)", min_value=1.0, value=100.0, step=1.0)
        with cols[1]:
            meters_per_pixel = st.number_input("Meters per Pixel", min_value=0.0001, value=0.02, step=0.005, format="%.4f")
        with cols[2]:
            frame_stride = st.number_input("Frame Stride", min_value=1, value=5, step=1)
        max_frames = st.number_input("Max Frames", min_value=5, value=120, step=5)
        if st.button("Estimate from Video") and file is not None:
            bytes_data = file.read()
            dens, vel = _estimate_from_video(bytes_data, float(area_m2), float(meters_per_pixel), int(frame_stride), int(max_frames))
            if len(dens) >= 5:
                sim["density_series"] = dens
            sim["velocity"] = float(np.clip(vel, 0.0, 2.0))
            st.success(f"Estimated velocity: {sim['velocity']:.2f} m/s; mean density: {float(np.mean(sim['density_series'])):.2f} people/m²")

    series = sim["density_series"]
    pred = forecast_next(series, steps=20)

    ts = np.concatenate([series, pred])
    df = pd.DataFrame({"t": np.arange(len(ts)), "density": ts})
    st.line_chart(df, x="t", y="density", height=250)

    prob = bottleneck_probability(pred, threshold=4.0)
    if prob >= 0.8:
        st.warning(f"⚠️ {int(prob*100)}% chance of bottleneck near {sim['zone']} in 15-20 mins")
        add_alert(sim["zone"], "high", datetime.utcnow().isoformat())
    elif prob >= 0.5:
        st.info(f"Possible congestion (p={prob}) near {sim['zone']} in 15-20 mins")
        add_alert(sim["zone"], "medium", datetime.utcnow().isoformat())
    else:
        st.success("Flow normal. Low risk of bottleneck in next 20 mins")

