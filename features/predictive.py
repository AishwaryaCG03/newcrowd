import numpy as np
import pandas as pd
import streamlit as st
from datetime import datetime

from db import add_alert
from prediction import bottleneck_probability, forecast_next, simulate_crowd_series


def predictive_page():
    st.header("Predictive Bottleneck Analysis")
    sim = st.session_state.sim
    with st.expander("Simulation Controls", expanded=True):
        sim["zone"] = st.text_input("Zone", value=sim.get("zone", "North Gate"))
        base_density = st.slider("Base Density (people/m²)", 0.2, 5.0, 2.5, 0.1)
        sim["velocity"] = st.slider("Average Velocity (m/s)", 0.0, 2.0, float(sim.get("velocity", 1.2)), 0.1)
        if st.button("Regenerate Series"):
            sim["density_series"] = simulate_crowd_series(60, base_density)

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
