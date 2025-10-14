import pandas as pd
import streamlit as st

from db import create_event, list_events_by_user


def event_setup_page():
    st.header("Event Setup")
    st.write("Provide your event details below.")
    with st.form("event_form"):
        event_name = st.text_input("Event Name")
        goal = st.text_input("Goal / Objective")
        target_audience = st.text_input("Target Audience")
        date_time = st.text_input("Date and Time (e.g., 2025-10-14 18:00)")
        venue_name = st.text_input("Venue Name")
        address = st.text_area("Venue Address")
        ticket_price = st.number_input("Ticket Price (optional)", min_value=0.0, step=0.5, format="%.2f")
        sponsors = st.text_input("Sponsors (optional, comma-separated)")
        description = st.text_area("Description")
        submit = st.form_submit_button("Register Event")

    if submit:
        required = [event_name, goal, target_audience, date_time, venue_name, address, description]
        if any(not x for x in required):
            st.error("Please fill all required fields")
        else:
            data = {
                "event_name": event_name,
                "goal": goal,
                "target_audience": target_audience,
                "date_time": date_time,
                "venue_name": venue_name,
                "address": address,
                "ticket_price": ticket_price if ticket_price else None,
                "sponsors": sponsors,
                "description": description,
            }
            create_event(st.session_state.auth["user_id"], data)
            st.success("Event registered successfully!")
            st.session_state.current_event = event_name
            st.session_state.page = "dashboard"
            st.rerun()

    st.subheader("Your Events")
    rows = list_events_by_user(st.session_state.auth["user_id"]) or []
    if rows:
        df = pd.DataFrame([dict(r) for r in rows])
        desired = ["id", "event_name", "date_time", "venue_name"]
        existing = [c for c in desired if c in df.columns]
        st.dataframe(df[existing] if existing else df)
    else:
        st.info("No events yet.")
