import os
from typing import List, Tuple, Optional

try:
    import streamlit as st
except Exception:
    st = None

import folium
from folium.plugins import HeatMap
import requests


def _maps_api_key() -> str:
    key = ""
    if st is not None:
        key = st.secrets.get("google", {}).get("MAPS_API_KEY", "")
    return os.environ.get("GOOGLE_MAPS_API_KEY", key)


def geocode_location(query: str):
    """Return (lat, lon) for a text location. Uses Google if API key set, else Nominatim.

    Returns None on failure.
    """
    if not query:
        return None
    key = _maps_api_key()
    # Allow forcing OSM-only via config
    use_osm_only = False
    try:
        if st is not None:
            use_osm_only = bool(st.secrets.get("maps", {}).get("USE_OSM_ONLY", False))
    except Exception:
        pass
    if os.environ.get("USE_OSM_ONLY", "").strip() in {"1", "true", "True"}:
        use_osm_only = True
    # Try Google Geocoding if key available
    if key and not use_osm_only:
        try:
            url = "https://maps.googleapis.com/maps/api/geocode/json"
            params = {"address": query, "key": key}
            r = requests.get(url, params=params, timeout=10)
            data = r.json()
            results = data.get("results", [])
            if results:
                loc = results[0]["geometry"]["location"]
                return float(loc["lat"]), float(loc["lng"])
        except Exception:
            pass
    # Fallback to OpenStreetMap Nominatim
    try:
        url = "https://nominatim.openstreetmap.org/search"
        params = {"q": query, "format": "json", "limit": 1}
        headers = {"User-Agent": "eventguard-ai/1.0"}
        r = requests.get(url, params=params, headers=headers, timeout=10)
        arr = r.json() if r.ok else []
        if arr:
            return float(arr[0]["lat"]), float(arr[0]["lon"])
    except Exception:
        pass
    return None


def create_heatmap(base_location: Tuple[float, float], points: List[Tuple[float, float, float]]):
    m = folium.Map(location=base_location, zoom_start=15, tiles="OpenStreetMap")
    if points:
        heat_data = [(lat, lon, weight) for lat, lon, weight in points]
        HeatMap(heat_data, radius=18).add_to(m)
    return m


def _simulate_route(origin: Tuple[float, float], dest: Tuple[float, float]) -> List[Tuple[float, float]]:
    lat1, lon1 = origin
    lat2, lon2 = dest
    steps = 12
    return [(
        lat1 + (lat2 - lat1) * i / steps,
        lon1 + (lon2 - lon1) * i / steps,
    ) for i in range(steps + 1)]


def directions_route(origin: Tuple[float, float], dest: Tuple[float, float]) -> Tuple[List[Tuple[float, float]], Optional[int]]:
    key = _maps_api_key()
    if not key:
        pts = _simulate_route(origin, dest)
        return pts, 240  # ~4 min default ETA
    try:
        url = "https://maps.googleapis.com/maps/api/directions/json"
        params = {
            "origin": f"{origin[0]},{origin[1]}",
            "destination": f"{dest[0]},{dest[1]}",
            "mode": "driving",
            "key": key,
        }
        r = requests.get(url, params=params, timeout=10)
        data = r.json()
        if data.get("routes"):
            route = data["routes"][0]
            legs = route.get("legs", [])
            eta = None
            if legs and legs[0].get("duration", {}).get("value") is not None:
                eta = int(legs[0]["duration"]["value"]) // 60
            # Decode polyline
            poly = route.get("overview_polyline", {}).get("points")
            if poly:
                pts = _decode_polyline(poly)
                return pts, eta
    except Exception:
        pass
    return _simulate_route(origin, dest), 240


def _decode_polyline(polyline_str: str) -> List[Tuple[float, float]]:
    index, lat, lng = 0, 0, 0
    coordinates = []
    length = len(polyline_str)
    while index < length:
        # Decode latitude
        shift, result = 0, 0
        while True:
            b = ord(polyline_str[index]) - 63
            index += 1
            result |= (b & 0x1f) << shift
            shift += 5
            if b < 0x20:
                break
        dlat = ~(result >> 1) if (result & 1) else (result >> 1)
        lat += dlat

        # Decode longitude
        shift, result = 0, 0
        while True:
            b = ord(polyline_str[index]) - 63
            index += 1
            result |= (b & 0x1f) << shift
            shift += 5
            if b < 0x20:
                break
        dlng = ~(result >> 1) if (result & 1) else (result >> 1)
        lng += dlng

        coordinates.append((lat / 1e5, lng / 1e5))
    return coordinates


def add_route_to_map(m: folium.Map, points: List[Tuple[float, float]], color: str = "blue"):
    folium.PolyLine(points, color=color, weight=5, opacity=0.8).add_to(m)
    if points:
        folium.Marker(points[0], tooltip="Origin").add_to(m)
        folium.Marker(points[-1], tooltip="Destination").add_to(m)
        try:
            m.fit_bounds(points)
        except Exception:
            pass
    return m


def get_current_event_blueprint():
    """Get blueprint for the current event"""
    if st is None:
        return None
    
    try:
        from db import list_events_by_user, get_blueprint_by_event
        
        user_id = st.session_state.auth.get("user_id")
        if not user_id:
            return None
        
        # Get current event
        current_event_name = st.session_state.get("current_event")
        if not current_event_name:
            return None
        
        # Find the event
        events = list_events_by_user(user_id)
        event = None
        for e in events:
            if e['event_name'] == current_event_name:
                event = e
                break
        
        if not event:
            return None
        
        # Get blueprint for this event
        blueprint = get_blueprint_by_event(event['id'])
        return blueprint
        
    except Exception:
        return None


def create_heatmap_with_blueprint(base_location: Tuple[float, float], points: List[Tuple[float, float, float]]):
    """Create heatmap with blueprint overlay if available"""
    # Get current event blueprint
    blueprint = get_current_event_blueprint()
    
    if blueprint and blueprint['venue_bounds_north']:
        # Create map with blueprint overlay
        bounds = {
            "center_lat": (blueprint['venue_bounds_north'] + blueprint['venue_bounds_south']) / 2,
            "center_lng": (blueprint['venue_bounds_east'] + blueprint['venue_bounds_west']) / 2,
            "north": blueprint['venue_bounds_north'],
            "south": blueprint['venue_bounds_south'],
            "east": blueprint['venue_bounds_east'],
            "west": blueprint['venue_bounds_west']
        }
        
        # Create map centered on blueprint
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
            opacity=0.8,
            interactive=True,
            cross_origin=False
        )
        img_overlay.add_to(m)
        
        # Add heatmap if points provided
        if points:
            heat_data = [(lat, lon, weight) for lat, lon, weight in points]
            HeatMap(heat_data, radius=18).add_to(m)
        
        # Add blueprint bounds rectangle
        folium.Rectangle(
            bounds=blueprint_bounds,
            color='red',
            weight=2,
            fill=False,
            popup=f"Blueprint: {blueprint['blueprint_name']}"
        ).add_to(m)
        
        # Add layer control
        folium.LayerControl().add_to(m)
        
        return m
    else:
        # Fallback to standard heatmap
        return create_heatmap(base_location, points)


def create_map_with_blueprint(base_location: Tuple[float, float], **kwargs):
    """Create map with blueprint overlay if available"""
    blueprint = get_current_event_blueprint()
    
    if blueprint and blueprint['venue_bounds_north']:
        bounds = {
            "center_lat": (blueprint['venue_bounds_north'] + blueprint['venue_bounds_south']) / 2,
            "center_lng": (blueprint['venue_bounds_east'] + blueprint['venue_bounds_west']) / 2,
            "north": blueprint['venue_bounds_north'],
            "south": blueprint['venue_bounds_south'],
            "east": blueprint['venue_bounds_east'],
            "west": blueprint['venue_bounds_west']
        }
        
        # Create map centered on blueprint
        m = folium.Map(
            location=[bounds["center_lat"], bounds["center_lng"]],
            zoom_start=kwargs.get('zoom_start', 16),
            tiles=kwargs.get('tiles', None)
        )
        
        # Add blueprint overlay
        blueprint_bounds = [
            [bounds["south"], bounds["west"]],
            [bounds["north"], bounds["east"]]
        ]
        
        img_overlay = folium.raster_layers.ImageOverlay(
            image=blueprint['file_path'],
            bounds=blueprint_bounds,
            opacity=kwargs.get('blueprint_opacity', 0.8),
            interactive=True,
            cross_origin=False
        )
        img_overlay.add_to(m)
        
        # Add blueprint bounds rectangle
        folium.Rectangle(
            bounds=blueprint_bounds,
            color='red',
            weight=2,
            fill=False,
            popup=f"Blueprint: {blueprint['blueprint_name']}"
        ).add_to(m)
        
        return m
    else:
        # Fallback to standard map
        return folium.Map(location=base_location, **kwargs)
