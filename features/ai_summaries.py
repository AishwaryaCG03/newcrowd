import random
import numpy as np
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium
import os

from ai import gemini_summarize, analyze_heatmap_data
from db import (list_incidents, list_events_by_user, add_blueprint, get_blueprint_by_event,
               list_blueprints_by_user, update_blueprint_bounds)
from maps import create_heatmap, create_heatmap_with_blueprint, geocode_location
from blueprint_utils import (save_uploaded_blueprint, create_blueprint_overlay_map,
                           generate_blueprint_heatmap_points, validate_blueprint_bounds,
                           get_blueprint_preview_html, get_image_bounds_from_coordinates)


def ai_summaries_page():
    st.header("AI-Powered Situational Summaries & Commander Intelligence")
    
    # Show current event info
    current_event_name = st.session_state.get("current_event")
    if current_event_name:
        st.success(f"📅 **Currently analyzing:** {current_event_name}")
        
        # Get event details for display
        user_id = st.session_state.auth.get("user_id")
        if user_id:
            events = list_events_by_user(user_id)
            current_event = next((e for e in events if e['event_name'] == current_event_name), None)
            if current_event:
                col1, col2 = st.columns(2)
                with col1:
                    st.caption(f"📍 Venue: {current_event['venue_name'] if current_event['venue_name'] else 'Unknown'}")
                with col2:
                    st.caption(f"📅 Date: {current_event['date_time'] if current_event['date_time'] else 'Unknown'}")
    else:
        st.warning("📅 **No event selected.** Please select an event from the sidebar to begin analysis.")
        st.write("**Steps to get started:**")
        st.write("1. 📅 Select an event from the 'Event Selection' dropdown in the left sidebar")
        st.write("2. 🗺️ Upload a venue blueprint during event setup (if not already done)")
        st.write("3. 🔥 Generate heatmaps and ask AI questions")
        
        # Don't show tabs if no event selected
        return
    
    # Tab interface
    tab1, tab2 = st.tabs(["📊 AI Summaries", "🔥 Venue Heatmap"])
    
    with tab1:
        ai_summaries_tab()
    
    with tab2:
        venue_heatmap_tab()


def ai_summaries_tab():
    st.subheader("AI-Powered Situational Summaries")
    
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


def venue_heatmap_tab():
    st.subheader("Venue Heatmap with Blueprint Overlay")
    
    # Get current event blueprint
    current_event_name = st.session_state.get("current_event")
    if not current_event_name:
        st.info("📅 **Please select an event from the sidebar to view venue heatmaps.**")
        st.write("Use the 'Event Selection' dropdown in the left sidebar to choose which event you want to analyze.")
        return
    
    # Get blueprint for current event
    user_id = st.session_state.auth.get("user_id")
    events = list_events_by_user(user_id)
    current_event = None
    for event in events:
        if event['event_name'] == current_event_name:
            current_event = event
            break
    
    if not current_event:
        st.error("Current event not found")
        return
    
    blueprint = get_blueprint_by_event(current_event['id'])
    
    if not blueprint:
        st.info(f"No blueprint uploaded for event '{current_event_name}'. Please upload a blueprint during event setup.")
        return
    
    # Check if blueprint has bounds set
    if not blueprint['venue_bounds_north']:
        st.warning("This blueprint doesn't have geographic bounds set. Please contact support to set bounds.")
        return
    
    st.write(f"**Current Event:** {current_event_name}")
    st.write(f"**Blueprint:** {blueprint['blueprint_name']}")
    
    try:
        # Generate heatmap points
        bounds = get_image_bounds_from_coordinates(
            blueprint['venue_bounds_north'],
            blueprint['venue_bounds_south'],
            blueprint['venue_bounds_east'],
            blueprint['venue_bounds_west']
        )
        
        # Simulate heatmap data
        density = st.session_state.sim["density_series"].tolist()
        
        if st.button("Generate Heatmap", key="generate_heatmap"):
            st.session_state.blueprint_heatmap_points = generate_blueprint_heatmap_points(
                bounds["center_lat"], bounds["center_lng"], bounds, num_points=100
            )
            st.rerun()
        
        # Display heatmap using the new maps function
        if hasattr(st.session_state, 'blueprint_heatmap_points'):
            # Use the new blueprint-enabled heatmap function
            m = create_heatmap_with_blueprint(
                (bounds["center_lat"], bounds["center_lng"]), 
                st.session_state.blueprint_heatmap_points
            )
            
            st_folium(m, width=900, height=600, key="blueprint_heatmap")
            
            # Heatmap statistics
            st.subheader("Heatmap Statistics")
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("Total Data Points", len(st.session_state.blueprint_heatmap_points))
            
            with col2:
                avg_intensity = np.mean([point[2] for point in st.session_state.blueprint_heatmap_points])
                st.metric("Average Intensity", f"{avg_intensity:.2f}")
            
            with col3:
                max_intensity = np.max([point[2] for point in st.session_state.blueprint_heatmap_points])
                st.metric("Peak Intensity", f"{max_intensity:.2f}")
            
            # Heatmap controls
            st.subheader("Heatmap Controls")
            col1, col2 = st.columns(2)
            
            with col1:
                if st.button("Regenerate Heatmap"):
                    st.session_state.blueprint_heatmap_points = generate_blueprint_heatmap_points(
                        bounds["center_lat"], bounds["center_lng"], bounds, num_points=100
                    )
                    st.rerun()
            
            with col2:
                show_raw_data = st.checkbox("Show Raw Data Points")
                if show_raw_data:
                    df = pd.DataFrame(st.session_state.blueprint_heatmap_points, 
                                    columns=['Latitude', 'Longitude', 'Intensity'])
                    st.dataframe(df, use_container_width=True)
        else:
            st.info("Click 'Generate Heatmap' to create a heatmap overlay on your blueprint.")
            
            # Show blueprint without heatmap using the new maps function
            m = create_heatmap_with_blueprint((bounds["center_lat"], bounds["center_lng"]), [])
            st_folium(m, width=900, height=600, key="blueprint_preview")
    except Exception as e:
        st.error(f"Error calculating bounds: {str(e)}")
