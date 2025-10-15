import random
import pandas as pd
import streamlit as st
import folium
from streamlit_folium import st_folium

from db import add_incident, list_incidents
from maps import add_route_to_map, create_heatmap, create_map_with_blueprint, directions_route


def incidents_dispatch_page():
    st.header("Incidents & Intelligent Dispatch")
    
    # Enhanced incident reporting form
    with st.form("incident_form"):
        st.subheader("Report New Incident")
        
        col1, col2 = st.columns(2)
        with col1:
            type_ = st.selectbox("Incident Type", ["medical", "security", "fire", "crowd control", "technical", "other"])
            severity = st.selectbox("Severity", ["low", "medium", "high", "critical"])
            priority = st.selectbox("Priority", ["low", "normal", "high", "urgent"])
        
        with col2:
            location = st.text_input("Location Description", placeholder="e.g., North Gate, Stage Area, Parking Lot")
            reporter_name = st.text_input("Reporter Name (Optional)")
            reporter_contact = st.text_input("Contact Info (Optional)", placeholder="Phone or Email")
        
        description = st.text_area("Incident Description", placeholder="Provide detailed description of what happened...")
        additional_notes = st.text_area("Additional Notes (Optional)", placeholder="Any additional information...")
        
        submit = st.form_submit_button("Report Incident", type="primary")
    
    if submit:
        if not location.strip():
            st.error("Please provide a location description")
        else:
            add_incident(
                type_=type_,
                location=location,
                severity=severity,
                description=description if description.strip() else None,
                reporter_name=reporter_name if reporter_name.strip() else None,
                reporter_contact=reporter_contact if reporter_contact.strip() else None,
                priority=priority,
                additional_notes=additional_notes if additional_notes.strip() else None
            )
            st.success(f"✅ {severity.upper()} priority {type_} incident recorded at {location}")

    st.subheader("Recent Incidents")
    rows = list_incidents(20)
    if rows:
        df = pd.DataFrame([dict(r) for r in rows])
        
        # Display incidents with enhanced information
        for _, incident in df.iterrows():
            with st.expander(f"🔴 {incident['type'].upper()} - {incident['location']} ({incident['severity']} severity)"):
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.write(f"**Type:** {incident['type']}")
                    st.write(f"**Severity:** {incident['severity']}")
                    st.write(f"**Priority:** {incident['priority']}")
                    st.write(f"**Status:** {incident['status'] if incident['status'] else 'open'}")
                
                with col2:
                    st.write(f"**Location:** {incident['location']}")
                    st.write(f"**Time:** {incident['timestamp']}")
                    if incident['reporter_name']:
                        st.write(f"**Reporter:** {incident['reporter_name']}")
                    if incident['unit_assigned']:
                        st.write(f"**Unit Assigned:** {incident['unit_assigned']}")
                
                with col3:
                    if incident['description']:
                        st.write(f"**Description:** {incident['description']}")
                    if incident['additional_notes']:
                        st.write(f"**Notes:** {incident['additional_notes']}")
                
                # Action buttons for commanders
                if st.button(f"Assign Unit", key=f"assign_{incident['id']}"):
                    st.info(f"Unit assignment feature would be implemented here for incident {incident['id']}")
                
                if st.button(f"Mark Resolved", key=f"resolve_{incident['id']}"):
                    st.success(f"Incident {incident['id']} marked as resolved")
    
    else:
        st.info("No incidents reported yet.")

    st.subheader("Dispatch Simulation")
    
    # Get user's current location
    with st.form("location_form"):
        st.write("### Enter Your Current Location")
        location_options = ["Main Stage", "North Gate", "South Gate", "Food Court", "Parking Lot A", "First Aid Station"]
        user_location = st.selectbox("Select your current location:", location_options, key="user_location")
        submit_location = st.form_submit_button("Find Best Route")
    
    if 'user_location' in st.session_state and st.session_state.user_location:
        base = (28.6139, 77.2090)  # Default coordinates (can be adjusted based on venue)
        
        # Define known locations on the blueprint
        location_coords = {
            "Main Stage": (base[0] + 0.001, base[1] - 0.001),
            "North Gate": (base[0] + 0.002, base[1] + 0.002),
            "South Gate": (base[0] - 0.001, base[1] - 0.002),
            "Food Court": (base[0] - 0.002, base[1] + 0.001),
            "Parking Lot A": (base[0] + 0.002, base[1] - 0.003),
            "First Aid Station": (base[0] - 0.002, base[1] - 0.001)
        }
        
        # Get user's location coordinates
        user_coords = location_coords.get(st.session_state.user_location, base)
        
        # Simulate available units with their positions
        units = {
            "Security Team 1": (base[0] + 0.003, base[1] - 0.003),
            "Medical Team A": (base[0] - 0.004, base[1] + 0.002),
            "Crowd Control": (base[0] + 0.005, base[1] + 0.004),
        }
        
        # Find nearest available unit
        def calculate_distance(coord1, coord2):
            # Simple distance calculation for demo purposes
            return ((coord1[0] - coord2[0])**2 + (coord1[1] - coord2[1])**2)**0.5
        
        # Find the nearest unit
        nearest_unit = min(units.items(), key=lambda x: calculate_distance(x[1], user_coords))
        unit_name, unit_coords = nearest_unit
        
        # Create a simple route (just a straight line for demo)
        route = [unit_coords, user_coords]
        
        # Calculate ETA based on distance (simplified)
        distance = calculate_distance(unit_coords, user_coords)
        eta_min = max(1, int(distance * 1000))  # Scale factor to get reasonable ETA
        
        # Get blueprint bounds from the map
        from maps import get_current_event_blueprint
        blueprint = get_current_event_blueprint()
        
        if blueprint and 'venue_bounds_north' in blueprint and blueprint['venue_bounds_north'] is not None:
            # Use blueprint bounds to create the map
            bounds = [
                [blueprint['venue_bounds_south'], blueprint['venue_bounds_west']],
                [blueprint['venue_bounds_north'], blueprint['venue_bounds_east']]
            ]
            center_lat = (blueprint['venue_bounds_north'] + blueprint['venue_bounds_south']) / 2
            center_lng = (blueprint['venue_bounds_east'] + blueprint['venue_bounds_west']) / 2
            
            # Create map centered on blueprint with constrained bounds
            m = folium.Map(
                location=[center_lat, center_lng],
                zoom_start=18,
                tiles=None,
                max_bounds=True,
                min_zoom=15,
                max_zoom=20,
                min_lat=blueprint['venue_bounds_south'] - 0.001,
                max_lat=blueprint['venue_bounds_north'] + 0.001,
                min_lon=blueprint['venue_bounds_west'] - 0.001,
                max_lon=blueprint['venue_bounds_east'] + 0.001
            )
            
            # Add blueprint overlay if file_path exists
            if 'file_path' in blueprint and blueprint['file_path']:
                img_overlay = folium.raster_layers.ImageOverlay(
                    image=blueprint['file_path'],
                    bounds=bounds,
                    opacity=0.9,
                    interactive=True,
                    cross_origin=False
                )
                img_overlay.add_to(m)
            
            # Add blueprint bounds rectangle
            blueprint_name = blueprint['blueprint_name'] if 'blueprint_name' in blueprint else 'Venue'
            folium.Rectangle(
                bounds=bounds,
                color='red',
                weight=2,
                fill=False,
                popup=f"Blueprint: {blueprint_name}"
            ).add_to(m)
            
            # Ensure route points are within blueprint bounds
            def constrain_point_to_bounds(point, bounds):
                lat = max(bounds[0][0], min(bounds[1][0], point[0]))
                lng = max(bounds[0][1], min(bounds[1][1], point[1]))
                return [lat, lng]
            
            # Constrain route points to blueprint bounds
            constrained_route = [constrain_point_to_bounds(p, bounds) for p in route]
            
            # Add the route line
            folium.PolyLine(
                constrained_route,
                color='#FF4500',
                weight=6,
                opacity=0.9,
                line_cap='round',
                line_join='round'
            ).add_to(m)
            
            # Add arrow markers along the route (only if they're within bounds)
            for i in range(1, len(constrained_route)):
                if (bounds[0][0] <= constrained_route[i][0] <= bounds[1][0] and 
                    bounds[0][1] <= constrained_route[i][1] <= bounds[1][1]):
                    folium.RegularPolygonMarker(
                        location=constrained_route[i],
                        number_of_sides=3,
                        radius=6,
                        rotation=0,
                        color='#FF4500',
                        fill_color='#FF4500',
                        fill_opacity=0.8,
                        weight=1
                    ).add_to(m)
            
            # Add markers (ensuring they're within bounds)
            def add_marker_if_in_bounds(m, location, **kwargs):
                if (bounds[0][0] <= location[0] <= bounds[1][0] and 
                    bounds[0][1] <= location[1] <= bounds[1][1]):
                    folium.Marker(location=location, **kwargs).add_to(m)
            
            # Add user location marker with custom icon
            add_marker_if_in_bounds(
                m,
                user_coords,
                popup=f"Your Location: {st.session_state.user_location}",
                icon=folium.Icon(
                    color='blue',
                    icon='user',
                    prefix='fa',
                    icon_color='white'
                )
            )
            
            # Add unit marker with custom icon
            add_marker_if_in_bounds(
                m,
                unit_coords,
                popup=f"{unit_name}",
                icon=folium.Icon(
                    color='green',
                    icon='ambulance',
                    prefix='fa',
                    icon_color='white'
                )
            )
            
            # Add a circle to show the unit's current position more clearly
            if (bounds[0][0] <= unit_coords[0] <= bounds[1][0] and 
                bounds[0][1] <= unit_coords[1] <= bounds[1][1]):
                folium.CircleMarker(
                    location=unit_coords,
                    radius=8,
                    color='white',
                    weight=2,
                    fill_color='#2ecc71',
                    fill_opacity=1.0
                ).add_to(m)
            
            # Fit the map to show the blueprint bounds with some padding
            m.fit_bounds(bounds, padding=(20, 20))
            
        else:
            # Fallback if no blueprint is available
            m = create_map_with_blueprint(base, zoom_start=18, tiles=None)
            folium.PolyLine(route, color='#FF4500', weight=6, opacity=0.9).add_to(m)
            m.fit_bounds([user_coords, unit_coords], padding=(30, 30))
        
        # Display the map with a larger size
        st_folium(m, width=900, height=600, key="dispatch_map")
        
        # Show dispatch information
        st.success(f"🚑 {unit_name} has been dispatched to your location")
        st.info(f"📍 Your location: {st.session_state.user_location}")
        st.info(f"⏱️ Estimated time of arrival: {eta_min} minutes")
        
        # Add a refresh button
        if st.button("Update Dispatch Status"):
            st.experimental_rerun()
    else:
        st.info("Please select your current location and click 'Find Best Route' to see the dispatch information.")
