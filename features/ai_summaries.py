import random
import numpy as np
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium
import os

from ai import gemini_summarize, analyze_heatmap_data, gemini_commander_qa
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
    tab1, tab2, tab3 = st.tabs(["📊 AI Summaries", "🔥 Venue Heatmap", "🤖 Commander Q&A"])
    
    with tab1:
        ai_summaries_tab()
    
    with tab2:
        venue_heatmap_tab()
    
    with tab3:
        commander_qa_tab()


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


def commander_qa_tab():
    st.subheader("🤖 AI Commander Intelligence")
    st.write("Ask questions about crowd density patterns, safety concerns, and get AI-powered recommendations based on heatmap analysis.")
    
    # Get current event context
    current_event_name = st.session_state.get("current_event")
    if not current_event_name:
        st.info("📅 **Please select an event from the sidebar to access commander intelligence.**")
        st.write("Use the 'Event Selection' dropdown in the left sidebar to choose which event you want to analyze.")
        return
    
    # Get event details
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
    
    # Check if we have heatmap data
    if not hasattr(st.session_state, 'blueprint_heatmap_points') or not st.session_state.blueprint_heatmap_points:
        st.warning("Please generate a heatmap first in the 'Venue Heatmap' tab to enable AI analysis.")
        return
    
    # Get additional context data
    incidents = [r["type"] for r in list_incidents(10)]
    zones = []  # Could be populated from geo-fencing data
    
    # Analyze heatmap data
    heatmap_analysis = analyze_heatmap_data(
        st.session_state.blueprint_heatmap_points,
        zones=zones,
        incidents=incidents
    )
    
    # Display current analysis summary
    st.subheader("📊 Current Situation Analysis")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Risk Level", heatmap_analysis.get('risk_assessment', {}).get('risk_level', 'Unknown'))
    
    with col2:
        st.metric("Avg Density", f"{heatmap_analysis.get('average_intensity', 0):.2f}")
    
    with col3:
        st.metric("Hotspots", heatmap_analysis.get('hotspot_count', 0))
    
    with col4:
        st.metric("Data Points", heatmap_analysis.get('total_points', 0))
    
    # Risk assessment display
    risk_assessment = heatmap_analysis.get('risk_assessment', {})
    if risk_assessment:
        risk_level = risk_assessment.get('risk_level', 'Unknown')
        risk_color = risk_assessment.get('color', 'gray')
        
        if risk_level == "HIGH":
            st.error(f"🔴 **HIGH RISK** - Risk Score: {risk_assessment.get('risk_score', 0)}")
        elif risk_level == "MEDIUM":
            st.warning(f"🟠 **MEDIUM RISK** - Risk Score: {risk_assessment.get('risk_score', 0)}")
        else:
            st.success(f"🟢 **LOW RISK** - Risk Score: {risk_assessment.get('risk_score', 0)}")
        
        # Show recommendations
        recommendations = risk_assessment.get('recommendations', [])
        if recommendations:
            st.write("**Immediate Recommendations:**")
            for rec in recommendations:
                st.write(f"• {rec}")
    
    # Commander Q&A Interface
    st.subheader("💬 Ask the AI Commander")
    
    # Predefined questions
    st.write("**Quick Questions:**")
    quick_questions = [
        "What are the current safety concerns?",
        "Where should I deploy additional security?",
        "Are there any crowd management issues?",
        "What areas need immediate attention?",
        "How is the overall crowd flow?",
        "What are the risk factors I should monitor?"
    ]
    
    cols = st.columns(2)
    selected_quick_question = None
    
    for i, question in enumerate(quick_questions):
        with cols[i % 2]:
            if st.button(question, key=f"quick_{i}", help="Click to ask this question"):
                selected_quick_question = question
    
    # Custom question input
    st.write("**Or ask your own question:**")
    custom_question = st.text_input(
        "Enter your question about the current situation:",
        placeholder="e.g., Should I be concerned about the crowd density near the main stage?",
        value=selected_quick_question if selected_quick_question else ""
    )
    
    # Ask question button
    if st.button("Ask AI Commander", type="primary", disabled=not custom_question.strip()):
        if custom_question.strip():
            with st.spinner("AI Commander is analyzing the situation..."):
                # Get AI response
                ai_response = gemini_commander_qa(
                    custom_question,
                    heatmap_analysis,
                    current_event
                )
                
                # Store in session state for display
                if 'commander_qa_history' not in st.session_state:
                    st.session_state.commander_qa_history = []
                
                st.session_state.commander_qa_history.append({
                    'question': custom_question,
                    'response': ai_response,
                    'timestamp': pd.Timestamp.now().strftime('%H:%M:%S'),
                    'analysis': heatmap_analysis
                })
                
                st.rerun()
    
    # Display Q&A History
    if hasattr(st.session_state, 'commander_qa_history') and st.session_state.commander_qa_history:
        st.subheader("📝 Q&A History")
        
        # Show latest response
        latest_qa = st.session_state.commander_qa_history[-1]
        
        st.write(f"**Question:** {latest_qa['question']}")
        st.write(f"**Asked at:** {latest_qa['timestamp']}")
        
        # Display AI response with proper formatting
        st.write("**AI Commander Response:**")
        st.markdown(latest_qa['response'])
        
        # Show analysis context used
        with st.expander("View Analysis Context Used"):
            st.json(heatmap_analysis)
        
        # Show full history
        if len(st.session_state.commander_qa_history) > 1:
            with st.expander("View All Q&A History"):
                for i, qa in enumerate(reversed(st.session_state.commander_qa_history)):
                    st.write(f"**{len(st.session_state.commander_qa_history) - i}.** {qa['question']} ({qa['timestamp']})")
                    st.write(f"*{qa['response'][:100]}...*")
                    st.write("---")
        
        # Clear history button
        if st.button("Clear Q&A History"):
            st.session_state.commander_qa_history = []
            st.rerun()
    
    # Additional insights section
    st.subheader("🔍 Detailed Analysis")
    
    if heatmap_analysis and 'distribution' in heatmap_analysis:
        distribution = heatmap_analysis['distribution']
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("**Crowd Density Distribution:**")
            st.write(f"• High Density Areas: {distribution.get('high_density', 0)}")
            st.write(f"• Medium Density Areas: {distribution.get('medium_density', 0)}")
            st.write(f"• Low Density Areas: {distribution.get('low_density', 0)}")
        
        with col2:
            st.write("**Density Statistics:**")
            st.write(f"• Average: {heatmap_analysis.get('average_intensity', 0):.3f}")
            st.write(f"• Maximum: {heatmap_analysis.get('max_intensity', 0):.3f}")
            st.write(f"• Minimum: {heatmap_analysis.get('min_intensity', 0):.3f}")
    
    # Recent incidents context
    if incidents:
        st.write("**Recent Incidents Context:**")
        for incident in incidents[:5]:
            st.write(f"• {incident}")
    
    # Get blueprint for current event to access bounds
    blueprint = get_blueprint_by_event(current_event['id'])
    if not blueprint:
        st.warning("No blueprint found for this event. Please upload a blueprint first.")
        return
        
    # Check if blueprint has bounds set
    if not all(key in blueprint for key in ['venue_bounds_north', 'venue_bounds_south', 
                                          'venue_bounds_east', 'venue_bounds_west']):
        st.warning("This blueprint doesn't have geographic bounds set. Please set the venue bounds first.")
        return
        
    try:
        # Calculate bounds from blueprint coordinates
        bounds = get_image_bounds_from_coordinates(
            blueprint['venue_bounds_north'],
            blueprint['venue_bounds_south'],
            blueprint['venue_bounds_east'],
            blueprint['venue_bounds_west']
        )
        
        # Refresh analysis button
        if st.button("🔄 Refresh Analysis"):
            if not all(key in bounds for key in ["center_lat", "center_lng"]):
                st.error("Invalid bounds data. Please check the blueprint configuration.")
            else:
                st.session_state.blueprint_heatmap_points = generate_blueprint_heatmap_points(
                    bounds["center_lat"], 
                    bounds["center_lng"], 
                    bounds, 
                    num_points=100
                )
                st.success("Analysis refreshed!")
                st.rerun()
    except Exception as e:
        st.error(f"Error calculating bounds: {str(e)}")
