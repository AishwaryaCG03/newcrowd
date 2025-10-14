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
