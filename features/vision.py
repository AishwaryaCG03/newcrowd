import numpy as np
import streamlit as st

from ai import gemini_vision_analyze


def vision_page():
    st.header("Anomaly Detection (Vision AI)")
    file = st.file_uploader("Upload image (jpg/png)", type=["jpg", "jpeg", "png"])
    if file is not None:
        import cv2
        import numpy as np

        bytes_data = file.read()
        img_arr = np.frombuffer(bytes_data, np.uint8)
        img = cv2.imdecode(img_arr, cv2.IMREAD_COLOR)

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        blur = cv2.GaussianBlur(gray, (7, 7), 0)
        edges = cv2.Canny(blur, 50, 150)
        edge_score = edges.mean() / 255.0

        smoke_like = (gray.mean() > 120 and edge_score < 0.05)

        if smoke_like:
            st.error("🚨 Potential smoke-like pattern detected!")
        else:
            st.success("No obvious anomaly from OpenCV check")

        gem = gemini_vision_analyze(bytes_data)
        if gem:
            st.error(f"🚨 AI anomaly: {gem}")

        st.image(img[:, :, ::-1], caption="Uploaded Image", use_column_width=True)
