import random
from datetime import datetime
from typing import List, Tuple

import numpy as np
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

from auth import begin_login, complete_login, is_test_mode, signup
from db import (
    add_alert,
    add_incident,
    create_event,
    get_user_by_email,
    list_alerts,
    list_events_by_user,
    list_incidents,
)
from prediction import bottleneck_probability, forecast_next, simulate_crowd_series
from ai import gemini_summarize, gemini_vision_analyze, simple_sentiment
from maps import add_route_to_map, create_heatmap, directions_route


def ensure_session():
    if "auth" not in st.session_state:
        st.session_state.auth = {"logged_in": False, "email": None, "user_id": None}
    if "page" not in st.session_state:
        st.session_state.page = "auth"
    if "current_event" not in st.session_state:
        st.session_state.current_event = None
    if "sim" not in st.session_state:
        st.session_state.sim = {
            "density_series": simulate_crowd_series(60),
            "velocity": 1.2,
            "zone": "North Gate",
        }


def header():
    cols = st.columns([1, 2, 1])
    with cols[1]:
        st.title("EventGuard AI")
        st.caption("AI-powered situational awareness for safer events")
    with cols[2]:
        tm = "ON" if is_test_mode() else "OFF"
        st.info(f"Test Mode: {tm}")


def nav():
    if st.session_state.auth.get("logged_in"):
        with st.sidebar:
            # Event Selection
            st.subheader("📅 Event Selection")
            user_id = st.session_state.auth.get("user_id")
            if user_id:
                events = list_events_by_user(user_id) or []
                events = [dict(r) for r in events]
                
                if events:
                    event_names = [event['event_name'] for event in events]
                    current_event = st.session_state.get("current_event", event_names[0] if event_names else None)
                    
                    selected_event = st.selectbox(
                        "Select Event:",
                        options=event_names,
                        index=event_names.index(current_event) if current_event in event_names else 0,
                        help="Choose which event to analyze and manage"
                    )
                    
                    if selected_event != current_event:
                        st.session_state.current_event = selected_event
                        st.rerun()
                    
                    # Show selected event info
                    selected_event_data = next((e for e in events if e['event_name'] == selected_event), None)
                    if selected_event_data:
                        st.caption(f"📍 {selected_event_data['venue_name'] if selected_event_data['venue_name'] else 'Unknown Venue'}")
                        st.caption(f"📅 {selected_event_data['date_time'] if selected_event_data['date_time'] else 'Unknown Date'}")
                else:
                    st.info("No events created yet. Create an event first!")
                    st.session_state.current_event = None
            
            st.divider()
            
            # Navigation
            st.subheader("🧭 Navigation")
            choice = st.radio(
                "Go to",
                [
                    "Dashboard",
                    "Event Setup",
                    "Predictive Bottlenecks",
                    "AI Summaries",
                    "Incidents & Dispatch",
                    "Lost & Found",
                    "Geo-Fencing Alerts",
                ],
            )
            
            st.divider()
            
            if st.button("Logout"):
                st.session_state.auth = {"logged_in": False, "email": None, "user_id": None}
                st.session_state.page = "auth"
            return choice
    return None
