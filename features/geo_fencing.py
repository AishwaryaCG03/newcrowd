import streamlit as st
import pandas as pd
import time
import random
from datetime import datetime, timedelta
from streamlit_folium import st_folium

from db import (create_zone, list_zones, add_geo_alert, list_geo_alerts, 
               resolve_geo_alert, add_tracking_entity, update_tracking_entity_location,
               list_tracking_entities, get_entity_location)
from geo_utils import (haversine_distance, is_point_in_circle, create_geo_fence_map,
                      simulate_crowd_movement, generate_zone_alerts, format_alert_message,
                      get_zone_statistics, get_zone_color, get_zone_icon)


def geo_fencing_page():
    st.header("Geo-Fencing Alert System")
    
    # Initialize session state
    if "geo_fencing_state" not in st.session_state:
        st.session_state.geo_fencing_state = {
            "simulation_running": False,
            "last_update": None,
            "simulated_entities": [],
            "base_lat": 28.6139,
            "base_lng": 77.2090
        }
    
    # Tab interface
    tab1, tab2 = st.tabs(["🗺️ Zone Management", "📍 Real-Time Tracking"])
    
    with tab1:
        zone_management_tab()
    
    with tab2:
        tracking_tab()


def zone_management_tab():
    st.subheader("Zone Creation & Management")
    
    # Zone creation form
    with st.expander("➕ Create New Zone", expanded=True):
        with st.form("zone_creation_form"):
            col1, col2 = st.columns(2)
            
            with col1:
                zone_name = st.text_input("Zone Name", placeholder="e.g., Main Stage, VIP Area")
                zone_type = st.selectbox("Zone Type", ["safe", "warning", "danger", "restricted"])
                radius = st.number_input("Radius (meters)", min_value=10, max_value=1000, value=100, step=10)
            
            with col2:
                center_lat = st.number_input("Center Latitude", value=28.6139, format="%.6f", step=0.000001)
                center_lng = st.number_input("Center Longitude", value=77.2090, format="%.6f", step=0.000001)
                density_threshold = st.number_input("Density Threshold", min_value=1, max_value=1000, value=100)
            
            description = st.text_area("Description (Optional)", placeholder="Describe the purpose of this zone...")
            
            if st.form_submit_button("Create Zone", type="primary"):
                if zone_name.strip():
                    create_zone(
                        name=zone_name,
                        zone_type=zone_type,
                        center_lat=center_lat,
                        center_lng=center_lng,
                        radius_meters=radius,
                        description=description if description.strip() else None,
                        density_threshold=density_threshold
                    )
                    st.success(f"✅ Zone '{zone_name}' created successfully!")
                    st.rerun()
                else:
                    st.error("Please provide a zone name")
    
    # Display existing zones
    st.subheader("Active Zones")
    zones = list_zones(active_only=True)
    
    if zones:
        # Zone overview
        zone_stats = {}
        for zone in zones:
            zone_type = zone['zone_type']
            if zone_type not in zone_stats:
                zone_stats[zone_type] = 0
            zone_stats[zone_type] += 1
        
        # Display zone statistics
        cols = st.columns(len(zone_stats))
        for i, (zone_type, count) in enumerate(zone_stats.items()):
            with cols[i]:
                icon = get_zone_icon(zone_type)
                color = get_zone_color(zone_type)
                st.metric(f"{icon} {zone_type.title()}", count)
        
        # Zone details
        for zone in zones:
            with st.expander(f"{get_zone_icon(zone['zone_type'])} {zone['name']} ({zone['zone_type']})"):
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.write(f"**Type:** {zone['zone_type']}")
                    st.write(f"**Radius:** {zone['radius_meters']}m")
                    st.write(f"**Density Threshold:** {zone['density_threshold']}")
                
                with col2:
                    st.write(f"**Center:** ({zone['center_lat']:.6f}, {zone['center_lng']:.6f})")
                    st.write(f"**Created:** {zone['created_at'][:19]}")
                    if zone['description']:
                        st.write(f"**Description:** {zone['description']}")
                
                with col3:
                    if st.button(f"Delete Zone", key=f"delete_{zone['id']}"):
                        st.warning(f"Zone deletion feature would be implemented here for zone {zone['id']}")
                    
                    if st.button(f"Edit Zone", key=f"edit_{zone['id']}"):
                        st.info(f"Zone editing feature would be implemented here for zone {zone['id']}")
    else:
        st.info("No zones created yet. Create your first zone above!")
    
    # Zone visualization
    if zones:
        st.subheader("Zone Map")
        entities = st.session_state.geo_fencing_state.get("simulated_entities", [])
        alerts = list_geo_alerts(unresolved_only=True)
        
        map_obj = create_geo_fence_map(
            zones=zones,
            entities=entities,
            alerts=alerts,
            center_lat=st.session_state.geo_fencing_state["base_lat"],
            center_lng=st.session_state.geo_fencing_state["base_lng"]
        )
        
        st_folium(map_obj, width=800, height=500, key="zone_map")


def tracking_tab():
    st.subheader("Real-Time Entity Tracking")
    
    # Simulation controls
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("🎬 Start Simulation", disabled=st.session_state.geo_fencing_state["simulation_running"]):
            st.session_state.geo_fencing_state["simulation_running"] = True
            st.session_state.geo_fencing_state["simulated_entities"] = simulate_crowd_movement(
                st.session_state.geo_fencing_state["base_lat"],
                st.session_state.geo_fencing_state["base_lng"],
                num_entities=50
            )
            st.success("Simulation started!")
            st.rerun()
    
    with col2:
        if st.button("⏹️ Stop Simulation", disabled=not st.session_state.geo_fencing_state["simulation_running"]):
            st.session_state.geo_fencing_state["simulation_running"] = False
            st.success("Simulation stopped!")
            st.rerun()
    
    with col3:
        if st.button("🔄 Update Positions"):
            if st.session_state.geo_fencing_state["simulation_running"]:
                # Simulate movement
                for entity in st.session_state.geo_fencing_state["simulated_entities"]:
                    # Add small random movement
                    entity["lat"] += random.uniform(-0.0001, 0.0001)
                    entity["lng"] += random.uniform(-0.0001, 0.0001)
                    entity["timestamp"] = datetime.utcnow().isoformat()
                
                # Check for zone violations and generate alerts
                zones = list_zones(active_only=True)
                new_alerts = generate_zone_alerts(st.session_state.geo_fencing_state["simulated_entities"], zones)
                
                for alert in new_alerts:
                    add_geo_alert(
                        zone_id=alert['zone_id'],
                        alert_type=alert['alert_type'],
                        entity_id=alert.get('entity_id'),
                        entity_lat=alert.get('entity_lat'),
                        entity_lng=alert.get('entity_lng'),
                        message=alert['message'],
                        severity=alert['severity']
                    )
                
                st.session_state.geo_fencing_state["last_update"] = datetime.utcnow()
                st.success("Positions updated!")
                st.rerun()
            else:
                st.warning("Please start simulation first")
    
    # Display current status
    status_col1, status_col2, status_col3 = st.columns(3)
    with status_col1:
        status = "🟢 Running" if st.session_state.geo_fencing_state["simulation_running"] else "🔴 Stopped"
        st.metric("Simulation Status", status)
    
    with status_col2:
        entity_count = len(st.session_state.geo_fencing_state.get("simulated_entities", []))
        st.metric("Tracked Entities", entity_count)
    
    with status_col3:
        last_update = st.session_state.geo_fencing_state.get("last_update")
        if last_update:
            st.metric("Last Update", last_update.strftime("%H:%M:%S"))
        else:
            st.metric("Last Update", "Never")
    
    # Entity tracking table
    if st.session_state.geo_fencing_state["simulated_entities"]:
        st.subheader("Entity Positions")
        
        # Create DataFrame for display
        df = pd.DataFrame(st.session_state.geo_fencing_state["simulated_entities"])
        df = df[['id', 'name', 'lat', 'lng', 'timestamp']]
        df.columns = ['ID', 'Name', 'Latitude', 'Longitude', 'Last Update']
        
        st.dataframe(df, use_container_width=True)
        
        # Zone analysis
        zones = list_zones(active_only=True)
        if zones:
            st.subheader("Zone Analysis")
            
            for zone in zones:
                density = calculate_zone_density(
                    st.session_state.geo_fencing_state["simulated_entities"],
                    zone['center_lat'],
                    zone['center_lng'],
                    zone['radius_meters']
                )
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.write(f"**{zone['name']}**")
                with col2:
                    st.write(f"Current Density: {density}")
                with col3:
                    threshold = zone['density_threshold']
                    if density > threshold:
                        st.error(f"⚠️ Exceeds threshold ({threshold})")
                    else:
                        st.success(f"✅ Within threshold ({threshold})")
    else:
        st.info("No entities being tracked. Start the simulation to begin tracking.")


# alerts_tab function removed as requested


# analytics_tab function removed as requested
    
    # Get entities from session state
    entities = st.session_state.geo_fencing_state.get("simulated_entities", [])
    
    # Zone density heatmap
    if entities and zones:
        st.subheader("Zone Density Analysis")
        
        density_data = []
        for zone in zones:
            density = calculate_zone_density(entities, zone['center_lat'], 
                                           zone['center_lng'], zone['radius_meters'])
            density_data.append({
                'Zone': zone['name'],
                'Type': zone['zone_type'],
                'Current Density': density,
                'Threshold': zone['density_threshold'],
                'Status': 'Exceeded' if density > zone['density_threshold'] else 'Normal'
            })
        
        density_df = pd.DataFrame(density_data)
        st.dataframe(density_df, use_container_width=True)


def calculate_zone_density(entities, center_lat, center_lng, radius):
    """Helper function to calculate zone density"""
    from geo_utils import calculate_zone_density
    return calculate_zone_density(entities, center_lat, center_lng, radius)
