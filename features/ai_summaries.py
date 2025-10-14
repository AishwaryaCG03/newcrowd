import random
import numpy as np
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

from ai import gemini_summarize
from db import list_incidents
from maps import create_heatmap


def ai_summaries_page():
    st.header("AI-Powered Situational Summaries")
    zone = st.text_input("Summarize security concerns in [Zone Name]", value="East Concourse")

    density = st.session_state.sim["density_series"].tolist()
    incidents = [r["type"] for r in list_incidents(10)]
    tweets = [
        "Crowd moving slow near gate",
        "Great vibes!",
        "People pushing in line",
        "Security helping a guest",
    ]

    if st.button("Generate Summary"):
        summary = gemini_summarize(zone, density, incidents, tweets)
        st.write(summary)

    st.subheader("Risk Heatmap")
    base = (28.6139, 77.2090)
    if "ai_heatmap_pts" not in st.session_state:
        pts = []
        for _ in range(30):
            lat = base[0] + random.uniform(-0.01, 0.01)
            lon = base[1] + random.uniform(-0.01, 0.01)
            weight = random.uniform(0.2, 1.0)
            pts.append((lat, lon, weight))
        st.session_state.ai_heatmap_pts = pts

    if st.button("Regenerate Heatmap"):
        pts = []
        for _ in range(30):
            lat = base[0] + random.uniform(-0.01, 0.01)
            lon = base[1] + random.uniform(-0.01, 0.01)
            weight = random.uniform(0.2, 1.0)
            pts.append((lat, lon, weight))
        st.session_state.ai_heatmap_pts = pts

    m = create_heatmap(base, st.session_state.ai_heatmap_pts)
    st_folium(m, width=800, height=500, key="ai_heatmap")
