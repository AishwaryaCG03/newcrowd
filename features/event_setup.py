import pandas as pd
import streamlit as st
import os

from db import create_event, list_events_by_user, add_blueprint
from blueprint_utils import save_uploaded_blueprint, validate_blueprint_bounds


def event_setup_page():
    st.header("Event Setup")
    st.write("Provide your event details and upload venue blueprint below.")
    
    with st.form("event_form"):
        # Basic event information
        st.subheader("📋 Event Information")
        event_name = st.text_input("Event Name")
        goal = st.text_input("Goal / Objective")
        target_audience = st.text_input("Target Audience")
        date_time = st.text_input("Date and Time (e.g., 2025-10-14 18:00)")
        venue_name = st.text_input("Venue Name")
        address = st.text_area("Venue Address")
        ticket_price = st.number_input("Ticket Price (optional)", min_value=0.0, step=0.5, format="%.2f")
        sponsors = st.text_input("Sponsors (optional, comma-separated)")
        description = st.text_area("Description")
        
        # Blueprint upload section
        st.subheader("🗺️ Venue Blueprint Upload")
        st.write("Upload a blueprint or layout image of your venue to enable advanced mapping features.")
        
        uploaded_blueprint = st.file_uploader(
            "Upload Venue Blueprint (Optional)", 
            type=['png', 'jpg', 'jpeg'],
            help="Upload a PNG, JPG, or JPEG image of your venue blueprint/layout"
        )
        
        blueprint_name = ""
        north_bound = south_bound = east_bound = west_bound = None
        
        if uploaded_blueprint:
            blueprint_name = st.text_input("Blueprint Name", placeholder="e.g., Main Floor Layout")
            
            st.write("**Set Geographic Bounds for Blueprint**")
            st.caption("Define the geographic boundaries that correspond to your blueprint image")
            
            col1, col2 = st.columns(2)
            with col1:
                north_bound = st.number_input("North Boundary (Latitude)", value=28.6149, format="%.6f", step=0.000001)
                south_bound = st.number_input("South Boundary (Latitude)", value=28.6129, format="%.6f", step=0.000001)
            with col2:
                east_bound = st.number_input("East Boundary (Longitude)", value=77.2100, format="%.6f", step=0.000001)
                west_bound = st.number_input("West Boundary (Longitude)", value=77.2080, format="%.6f", step=0.000001)
            
            # Show blueprint preview
            if uploaded_blueprint:
                st.image(uploaded_blueprint, caption="Blueprint Preview", use_column_width=True)
        
        submit = st.form_submit_button("Register Event", type="primary")

    if submit:
        required = [event_name, goal, target_audience, date_time, venue_name, address, description]
        if any(not x for x in required):
            st.error("Please fill all required fields")
        else:
            # Validate blueprint if uploaded
            if uploaded_blueprint and blueprint_name.strip():
                if not validate_blueprint_bounds(north_bound, south_bound, east_bound, west_bound):
                    st.error("Invalid geographic bounds. Please check your coordinates.")
                    return
            
            # Create event
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
            
            # Create event and get the event ID
            create_event(st.session_state.auth["user_id"], data)
            
            # Get the created event ID
            events = list_events_by_user(st.session_state.auth["user_id"])
            created_event = None
            for event in events:
                if event['event_name'] == event_name:
                    created_event = event
                    break
            
            # Upload blueprint if provided
            if uploaded_blueprint and blueprint_name.strip() and created_event:
                blueprint_data = save_uploaded_blueprint(
                    uploaded_blueprint, created_event['id'], blueprint_name
                )
                
                if blueprint_data:
                    add_blueprint(
                        event_id=created_event['id'],
                        blueprint_name=blueprint_name,
                        file_path=blueprint_data['file_path'],
                        original_filename=blueprint_data['original_filename'],
                        file_size=blueprint_data['file_size'],
                        image_width=blueprint_data['image_width'],
                        image_height=blueprint_data['image_height'],
                        venue_bounds_north=north_bound,
                        venue_bounds_south=south_bound,
                        venue_bounds_east=east_bound,
                        venue_bounds_west=west_bound,
                        description=f"Blueprint for {event_name}"
                    )
            
            st.success("Event registered successfully!")
            if uploaded_blueprint and blueprint_name.strip():
                st.success("Blueprint uploaded successfully!")
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
