import math
import random
import time
from typing import List, Tuple, Dict, Optional
from datetime import datetime, timedelta

import folium
from folium import plugins
import streamlit as st


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate the great circle distance between two points 
    on the earth (specified in decimal degrees)
    Returns distance in meters
    """
    # Convert decimal degrees to radians
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    
    # Haversine formula
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    
    # Radius of earth in meters
    r = 6371000
    return c * r


def is_point_in_circle(point_lat: float, point_lng: float, 
                      center_lat: float, center_lng: float, 
                      radius_meters: float) -> bool:
    """
    Check if a point is inside a circular zone
    """
    distance = haversine_distance(point_lat, point_lng, center_lat, center_lng)
    return distance <= radius_meters


def get_zone_color(zone_type: str) -> str:
    """
    Get color code for zone type
    """
    colors = {
        "safe": "#28a745",      # Green
        "warning": "#ffc107",   # Orange/Yellow
        "danger": "#dc3545",    # Red
        "restricted": "#6c757d" # Gray
    }
    return colors.get(zone_type.lower(), "#007bff")  # Default blue


def get_zone_icon(zone_type: str) -> str:
    """
    Get emoji icon for zone type
    """
    icons = {
        "safe": "🟢",
        "warning": "🟠", 
        "danger": "🔴",
        "restricted": "⚫"
    }
    return icons.get(zone_type.lower(), "🔵")


def simulate_crowd_movement(base_lat: float, base_lng: float, 
                           num_entities: int = 50) -> List[Dict]:
    """
    Simulate crowd movement around the event area
    Returns list of entities with current positions
    """
    entities = []
    for i in range(num_entities):
        # Generate random positions around the base location
        lat_offset = random.uniform(-0.01, 0.01)  # ~1km radius
        lng_offset = random.uniform(-0.01, 0.01)
        
        entities.append({
            "id": f"entity_{i:03d}",
            "name": f"Person {i+1}",
            "entity_type": "person",
            "lat": base_lat + lat_offset,
            "lng": base_lng + lng_offset,
            "timestamp": datetime.utcnow().isoformat()
        })
    
    return entities


def calculate_zone_density(entities: List[Dict], zone_center_lat: float, 
                          zone_center_lng: float, zone_radius: float) -> int:
    """
    Calculate crowd density in a zone
    Returns number of entities within the zone
    """
    count = 0
    for entity in entities:
        if is_point_in_circle(entity["lat"], entity["lng"], 
                            zone_center_lat, zone_center_lng, zone_radius):
            count += 1
    return count


def create_geo_fence_map(zones: List, entities: List[Dict] = None, 
                        alerts: List[Dict] = None, center_lat: float = 28.6139, 
                        center_lng: float = 77.2090, use_blueprint: bool = True) -> folium.Map:
    """
    Create an interactive map with geo-fenced zones, entities, and alerts
    """
    # Try to get blueprint for current event
    blueprint = None
    if use_blueprint:
        try:
            import streamlit as st
            from db import list_events_by_user, get_blueprint_by_event
            
            user_id = st.session_state.auth.get("user_id")
            current_event_name = st.session_state.get("current_event")
            
            if user_id and current_event_name:
                events = list_events_by_user(user_id)
                for event in events:
                    if event['event_name'] == current_event_name:
                        blueprint = get_blueprint_by_event(event['id'])
                        break
        except Exception:
            pass
    
    # Create base map
    if blueprint and blueprint['venue_bounds_north']:
        # Use blueprint bounds for centering
        bounds = {
            "center_lat": (blueprint['venue_bounds_north'] + blueprint['venue_bounds_south']) / 2,
            "center_lng": (blueprint['venue_bounds_east'] + blueprint['venue_bounds_west']) / 2,
            "north": blueprint['venue_bounds_north'],
            "south": blueprint['venue_bounds_south'],
            "east": blueprint['venue_bounds_east'],
            "west": blueprint['venue_bounds_west']
        }
        
        m = folium.Map(
            location=[bounds["center_lat"], bounds["center_lng"]],
            zoom_start=16,
            tiles=None
        )
        
        # Add blueprint overlay
        blueprint_bounds = [
            [bounds["south"], bounds["west"]],
            [bounds["north"], bounds["east"]]
        ]
        
        img_overlay = folium.raster_layers.ImageOverlay(
            image=blueprint['file_path'],
            bounds=blueprint_bounds,
            opacity=0.7,
            interactive=True,
            cross_origin=False
        )
        img_overlay.add_to(m)
    else:
        # Standard map
        m = folium.Map(
            location=[center_lat, center_lng],
            zoom_start=15,
            tiles='OpenStreetMap'
        )
    
    # Add zones
    for zone in zones:
        zone_lat = zone['center_lat']
        zone_lng = zone['center_lng']
        radius = zone['radius_meters']
        
        # Create circle for zone
        color = get_zone_color(zone['zone_type'])
        icon = get_zone_icon(zone['zone_type'])
        
        folium.Circle(
            location=[zone_lat, zone_lng],
            radius=radius,
            popup=f"{icon} {zone['name']}<br>Type: {zone['zone_type']}<br>Radius: {radius}m",
            color=color,
            weight=3,
            fill=True,
            fillColor=color,
            fillOpacity=0.3
        ).add_to(m)
        
        # Add zone center marker
        folium.Marker(
            location=[zone_lat, zone_lng],
            popup=f"{icon} {zone['name']}",
            icon=folium.Icon(color='white', icon_color=color, icon='circle', prefix='fa')
        ).add_to(m)
    
    # Add entities (if provided)
    if entities:
        for entity in entities:
            folium.CircleMarker(
                location=[entity['lat'], entity['lng']],
                radius=5,
                popup=f"Entity: {entity['name']}<br>ID: {entity['id']}",
                color='blue',
                fill=True,
                fillColor='blue',
                fillOpacity=0.7
            ).add_to(m)
    
    # Add alert markers (if provided)
    if alerts:
        for alert in alerts:
            if alert['entity_lat'] and alert['entity_lng']:
                severity_color = {
                    'low': 'green',
                    'medium': 'orange', 
                    'high': 'red',
                    'critical': 'darkred'
                }.get(alert['severity'], 'orange')
                
                folium.Marker(
                    location=[alert['entity_lat'], alert['entity_lng']],
                    popup=f"🚨 Alert: {alert['message']}<br>Severity: {alert['severity']}",
                    icon=folium.Icon(color=severity_color, icon='exclamation-triangle', prefix='fa')
                ).add_to(m)
    
    return m


def generate_zone_alerts(entities: List[Dict], zones: List) -> List[Dict]:
    """
    Generate alerts based on zone violations and density thresholds
    """
    alerts = []
    
    for zone in zones:
        # Calculate density in zone
        density = calculate_zone_density(entities, zone['center_lat'], 
                                       zone['center_lng'], zone['radius_meters'])
        
        # Check density threshold
        density_threshold = 100  # Default value
        if 'density_threshold' in zone:
            density_threshold = zone['density_threshold']
            
        if density > density_threshold:
            alerts.append({
                'zone_id': zone['id'],
                'alert_type': 'density_exceeded',
                'message': f"Density threshold exceeded in {zone['name']}: {density} people",
                'severity': 'high' if density > density_threshold * 1.5 else 'medium'
            })
        
        # Check for entities entering restricted/danger zones
        if zone['zone_type'] in ['restricted', 'danger']:
            for entity in entities:
                if is_point_in_circle(entity['lat'], entity['lng'], 
                                    zone['center_lat'], zone['center_lng'], 
                                    zone['radius_meters']):
                    alerts.append({
                        'zone_id': zone['id'],
                        'alert_type': 'unauthorized_entry',
                        'entity_id': entity['id'],
                        'entity_lat': entity['lat'],
                        'entity_lng': entity['lng'],
                        'message': f"{entity['name']} entered {zone['name']} ({zone['zone_type']} zone)",
                        'severity': 'critical' if zone['zone_type'] == 'danger' else 'high'
                    })
    
    return alerts


def format_alert_message(alert: Dict) -> str:
    """
    Format alert message for display
    """
    severity_icons = {
        'low': '🟢',
        'medium': '🟡',
        'high': '🟠',
        'critical': '🔴'
    }
    
    icon = severity_icons.get(alert['severity'], '🔵')
    timestamp = datetime.fromisoformat(alert['created_at']).strftime('%H:%M:%S')
    
    return f"{icon} [{timestamp}] {alert['message']}"


def get_zone_statistics(zones: List, entities: List[Dict]) -> Dict:
    """
    Get statistics for all zones
    """
    stats = {
        'total_zones': len(zones),
        'zone_breakdown': {},
        'total_entities': len(entities),
        'alerts_by_type': {}
    }
    
    for zone in zones:
        zone_type = zone['zone_type']
        if zone_type not in stats['zone_breakdown']:
            stats['zone_breakdown'][zone_type] = 0
        stats['zone_breakdown'][zone_type] += 1
        
        # Calculate density for this zone
        density = calculate_zone_density(entities, zone['center_lat'], 
                                       zone['center_lng'], zone['radius_meters'])
        
        # Use dictionary-style access with a fallback for sqlite3.Row objects
        density_threshold = 100  # Default value
        if 'density_threshold' in zone:
            density_threshold = zone['density_threshold']
            
        if density > density_threshold:
            alert_type = 'density_exceeded'
            if alert_type not in stats['alerts_by_type']:
                stats['alerts_by_type'][alert_type] = 0
            stats['alerts_by_type'][alert_type] += 1
    
    return stats
