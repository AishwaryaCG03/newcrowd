import os
import base64
import io
from typing import Tuple, Optional, List
from PIL import Image, ImageDraw, ImageFont
import numpy as np
import folium
from folium import plugins
import streamlit as st


def create_blueprint_directory():
    """Create directory for storing blueprint images"""
    blueprint_dir = "blueprints"
    if not os.path.exists(blueprint_dir):
        os.makedirs(blueprint_dir)
    return blueprint_dir


def save_uploaded_blueprint(uploaded_file, event_id: int, blueprint_name: str) -> dict:
    """
    Save uploaded blueprint image and return metadata
    """
    try:
        # Create blueprint directory
        blueprint_dir = create_blueprint_directory()
        
        # Generate unique filename
        file_extension = os.path.splitext(uploaded_file.name)[1]
        filename = f"event_{event_id}_{blueprint_name.replace(' ', '_')}{file_extension}"
        file_path = os.path.join(blueprint_dir, filename)
        
        # Save the file
        with open(file_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        
        # Get image metadata
        image = Image.open(uploaded_file)
        width, height = image.size
        file_size = len(uploaded_file.getbuffer())
        
        return {
            "file_path": file_path,
            "filename": filename,
            "original_filename": uploaded_file.name,
            "file_size": file_size,
            "image_width": width,
            "image_height": height
        }
        
    except Exception as e:
        st.error(f"Error saving blueprint: {str(e)}")
        return None


def get_image_bounds_from_coordinates(north: float, south: float, east: float, west: float) -> dict:
    """
    Calculate image bounds from coordinate bounds
    """
    return {
        "north": north,
        "south": south,
        "east": east,
        "west": west,
        "center_lat": (north + south) / 2,
        "center_lng": (east + west) / 2
    }


def create_blueprint_overlay_map(blueprint_path: str, bounds: dict, 
                                heatmap_points: List[Tuple] = None) -> folium.Map:
    """
    Create a map with blueprint overlay and optional heatmap
    """
    # Create base map centered on blueprint
    m = folium.Map(
        location=[bounds["center_lat"], bounds["center_lng"]],
        zoom_start=16,
        tiles=None
    )
    
    # Add blueprint image overlay
    blueprint_bounds = [
        [bounds["south"], bounds["west"]],  # Southwest corner
        [bounds["north"], bounds["east"]]   # Northeast corner
    ]
    
    # Create image overlay
    img_overlay = folium.raster_layers.ImageOverlay(
        image=blueprint_path,
        bounds=blueprint_bounds,
        opacity=0.8,
        interactive=True,
        cross_origin=False
    )
    img_overlay.add_to(m)
    
    # Add heatmap if provided
    if heatmap_points:
        # Convert heatmap points to blueprint coordinates
        blueprint_heatmap_points = []
        for lat, lng, intensity in heatmap_points:
            # Map geographic coordinates to blueprint coordinates
            blueprint_heatmap_points.append((lat, lng, intensity))
        
        # Add heatmap layer
        plugins.HeatMap(
            blueprint_heatmap_points,
            name="Crowd Density Heatmap",
            min_opacity=0.4,
            max_zoom=18,
            radius=25,
            blur=15,
            gradient={0.4: 'blue', 0.65: 'lime', 0.85: 'orange', 1.0: 'red'}
        ).add_to(m)
    
    # Add layer control
    folium.LayerControl().add_to(m)
    
    # Add blueprint bounds rectangle for reference
    folium.Rectangle(
        bounds=blueprint_bounds,
        color='red',
        weight=2,
        fill=False,
        popup="Blueprint Bounds"
    ).add_to(m)
    
    return m


def create_blueprint_heatmap_overlay(blueprint_path: str, bounds: dict, 
                                   heatmap_points: List[Tuple]) -> str:
    """
    Create a heatmap overlay directly on the blueprint image
    Returns base64 encoded image
    """
    try:
        # Open blueprint image
        blueprint_img = Image.open(blueprint_path).convert('RGBA')
        width, height = blueprint_img.size
        
        # Create heatmap overlay
        heatmap_overlay = Image.new('RGBA', (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(heatmap_overlay)
        
        # Convert heatmap points to image coordinates
        for lat, lng, intensity in heatmap_points:
            # Map geographic coordinates to image pixel coordinates
            x = int((lng - bounds["west"]) / (bounds["east"] - bounds["west"]) * width)
            y = int((bounds["north"] - lat) / (bounds["north"] - bounds["south"]) * height)
            
            # Ensure coordinates are within image bounds
            x = max(0, min(width - 1, x))
            y = max(0, min(height - 1, y))
            
            # Create heat point with intensity-based color and size
            radius = max(5, min(30, int(intensity * 25)))
            color_intensity = int(intensity * 255)
            
            # Color mapping: blue -> green -> yellow -> red
            if intensity < 0.3:
                color = (0, 0, color_intensity, 100)
            elif intensity < 0.6:
                color = (0, color_intensity, 0, 100)
            elif intensity < 0.8:
                color = (color_intensity, color_intensity, 0, 100)
            else:
                color = (color_intensity, 0, 0, 100)
            
            # Draw heat point
            draw.ellipse([x - radius, y - radius, x + radius, y + radius], 
                        fill=color, outline=None)
        
        # Blend blueprint with heatmap
        result_img = Image.alpha_composite(blueprint_img, heatmap_overlay)
        
        # Convert to base64 for display
        buffer = io.BytesIO()
        result_img.save(buffer, format='PNG')
        img_str = base64.b64encode(buffer.getvalue()).decode()
        
        return img_str
        
    except Exception as e:
        st.error(f"Error creating heatmap overlay: {str(e)}")
        return None


def map_geographic_to_blueprint(lat: float, lng: float, bounds: dict, 
                               img_width: int, img_height: int) -> Tuple[int, int]:
    """
    Map geographic coordinates to blueprint pixel coordinates
    """
    x = int((lng - bounds["west"]) / (bounds["east"] - bounds["west"]) * img_width)
    y = int((bounds["north"] - lat) / (bounds["north"] - bounds["south"]) * img_height)
    
    # Ensure coordinates are within image bounds
    x = max(0, min(img_width - 1, x))
    y = max(0, min(img_height - 1, y))
    
    return x, y


def map_blueprint_to_geographic(x: int, y: int, bounds: dict, 
                               img_width: int, img_height: int) -> Tuple[float, float]:
    """
    Map blueprint pixel coordinates to geographic coordinates
    """
    lng = bounds["west"] + (x / img_width) * (bounds["east"] - bounds["west"])
    lat = bounds["north"] - (y / img_height) * (bounds["north"] - bounds["south"])
    
    return lat, lng


def generate_blueprint_heatmap_points(center_lat: float, center_lng: float, 
                                    bounds: dict, num_points: int = 50) -> List[Tuple]:
    """
    Generate simulated heatmap points within blueprint bounds
    """
    import random
    
    points = []
    for _ in range(num_points):
        # Generate random point within bounds
        lat = random.uniform(bounds["south"], bounds["north"])
        lng = random.uniform(bounds["west"], bounds["east"])
        
        # Calculate distance from center for intensity
        distance = ((lat - center_lat) ** 2 + (lng - center_lng) ** 2) ** 0.5
        max_distance = ((bounds["north"] - bounds["south"]) ** 2 + 
                       (bounds["east"] - bounds["west"]) ** 2) ** 0.5
        
        # Intensity decreases with distance from center
        intensity = max(0.1, 1.0 - (distance / max_distance) * 0.8)
        intensity += random.uniform(-0.2, 0.2)  # Add some randomness
        intensity = max(0.0, min(1.0, intensity))
        
        points.append((lat, lng, intensity))
    
    return points


def validate_blueprint_bounds(north: float, south: float, east: float, west: float) -> bool:
    """
    Validate that blueprint bounds are logical
    """
    if north <= south:
        return False
    if east <= west:
        return False
    if abs(north - south) > 1.0:  # More than 1 degree
        return False
    if abs(east - west) > 1.0:  # More than 1 degree
        return False
    return True


def get_blueprint_preview_html(blueprint_path: str, bounds: dict, 
                             heatmap_points: List[Tuple] = None) -> str:
    """
    Generate HTML for blueprint preview with heatmap overlay
    """
    if heatmap_points:
        # Create heatmap overlay image
        overlay_img_str = create_blueprint_heatmap_overlay(blueprint_path, bounds, heatmap_points)
        if overlay_img_str:
            return f'<img src="data:image/png;base64,{overlay_img_str}" style="width: 100%; max-width: 800px;">'
    
    # Fallback to plain blueprint
    try:
        with open(blueprint_path, "rb") as f:
            img_data = base64.b64encode(f.read()).decode()
        return f'<img src="data:image/png;base64,{img_data}" style="width: 100%; max-width: 800px;">'
    except:
        return '<p>Error loading blueprint image</p>'
