import streamlit as st

from auth import is_test_mode
from db import list_alerts, list_incidents


def dashboard_page():
    st.header("Dashboard")
    ev = st.session_state.current_event or "(no event selected)"
    st.write(f"Current Event: {ev}")
    cols = st.columns(3)
    with cols[0]:
        st.metric("Active Incidents", len(list_incidents()))
    with cols[1]:
        alerts = list_alerts()
        st.metric("Recent Alerts", len(alerts))
    with cols[2]:
        st.metric("Test Mode", "ON" if is_test_mode() else "OFF")
