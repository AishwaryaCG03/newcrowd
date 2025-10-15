import streamlit as st

from auth import is_test_mode
from db import list_alerts, list_incidents, list_geo_alerts, list_zones


def dashboard_page():
    st.header("EventGuard AI Dashboard")
    ev = st.session_state.current_event or "(no event selected)"
    st.write(f"Current Event: {ev}")
    
    # Main metrics
    cols = st.columns(4)
    
    with cols[0]:
        incidents = list_incidents()
        st.metric("Active Incidents", len(incidents))
    
    with cols[1]:
        alerts = list_alerts()
        st.metric("Predictive Alerts", len(alerts))
    
    with cols[2]:
        geo_alerts = list_geo_alerts(unresolved_only=True)
        st.metric("Geo-Fencing Alerts", len(geo_alerts))
    
    with cols[3]:
        zones = list_zones(active_only=True)
        st.metric("Active Zones", len(zones))
    
    # Recent geo-fencing alerts
    if geo_alerts:
        st.subheader("🚨 Recent Geo-Fencing Alerts")
        
        # Show critical alerts first
        critical_alerts = [a for a in geo_alerts if a['severity'] == 'critical']
        high_alerts = [a for a in geo_alerts if a['severity'] == 'high']
        
        if critical_alerts:
            st.error("🔴 **CRITICAL ALERTS**")
            for alert in critical_alerts[:3]:  # Show top 3
                st.error(f"• {alert['message']} - {alert['zone_name']}")
        
        if high_alerts:
            st.warning("🟠 **HIGH PRIORITY ALERTS**")
            for alert in high_alerts[:3]:  # Show top 3
                st.warning(f"• {alert['message']} - {alert['zone_name']}")
        
        # Show other alerts
        other_alerts = [a for a in geo_alerts if a['severity'] in ['medium', 'low']]
        if other_alerts:
            with st.expander(f"View {len(other_alerts)} other alerts"):
                for alert in other_alerts[:5]:
                    st.info(f"• {alert['message']} - {alert['zone_name']}")
    
    # Zone status overview
    if zones:
        st.subheader("🗺️ Zone Status Overview")
        
        zone_cols = st.columns(min(len(zones), 4))
        for i, zone in enumerate(zones[:4]):  # Show up to 4 zones
            with zone_cols[i]:
                zone_icon = "🟢" if zone['zone_type'] == 'safe' else \
                           "🟠" if zone['zone_type'] == 'warning' else \
                           "🔴" if zone['zone_type'] == 'danger' else "⚫"
                
                st.metric(
                    f"{zone_icon} {zone['name']}", 
                    zone['zone_type'].title(),
                    help=f"Radius: {zone['radius_meters']}m, Threshold: {zone['density_threshold']}"
                )
    
    # System status
    st.subheader("System Status")
    status_cols = st.columns(3)
    
    with status_cols[0]:
        st.metric("Test Mode", "ON" if is_test_mode() else "OFF")
    
    with status_cols[1]:
        st.metric("Database", "Connected")
    
    with status_cols[2]:
        st.metric("AI Services", "Active" if not is_test_mode() else "Test Mode")
