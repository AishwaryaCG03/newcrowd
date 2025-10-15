import os
from typing import List, Tuple, Optional

try:
    import streamlit as st
except Exception:
    st = None

import requests


def is_test_mode() -> bool:
    try:
        if st is not None and "TEST_MODE" in st.secrets.get("app", {}):
            return bool(st.secrets["app"]["TEST_MODE"])
    except Exception:
        pass
    return os.environ.get("EVENTGUARD_TEST_MODE", "false").lower() in ["1", "true", "yes"]


def _gemini_api_key() -> str:
    key = ""
    if st is not None:
        key = st.secrets.get("gemini", {}).get("API_KEY", "")
    return os.environ.get("GEMINI_API_KEY", key)


# --- Gemini Text ---

def gemini_summarize(zone: str, crowd_density_series: List[float], incidents: List[str], tweets: List[str]) -> str:
    if is_test_mode() or not _gemini_api_key():
        # Simulated summary in test mode
        risk = "elevated" if (sum(crowd_density_series[-5:]) / max(1, len(crowd_density_series[-5:]))) > 3.5 else "moderate"
        return (
            f"Zone {zone}: Crowd pressure is {risk}. Recent incidents: {', '.join(incidents[-3:]) if incidents else 'none'}. "
            f"Social chatter indicates mild tension. Recommend staggered entry and 2 additional stewards."
        )
    try:
        import google.generativeai as genai

        genai.configure(api_key=_gemini_api_key())
        model = genai.GenerativeModel("gemini-1.5-flash")
        prompt = (
            "You are a crowd safety analyst. Summarize risks and recommended actions concisely (<=120 words).\n"
            f"Zone: {zone}\n"
            f"Recent densities: {crowd_density_series[-20:]} (people/m^2)\n"
            f"Incidents: {incidents[-5:]}\n"
            f"Tweets: {tweets[-5:]}\n"
        )
        resp = model.generate_content(prompt)
        return resp.text.strip()
    except Exception:
        return "AI summary unavailable. Using default guidance: maintain flow, monitor gates, and deploy additional stewards if density > 4/m^2."


# --- Gemini Vision ---

def gemini_vision_analyze(image_bytes: bytes, analyze_for: str = "anomalies") -> Optional[str]:
    if is_test_mode() or not _gemini_api_key():
        return None  # simulate 'no anomaly' by default
    try:
        import google.generativeai as genai
        from PIL import Image
        import io

        genai.configure(api_key=_gemini_api_key())
        model = genai.GenerativeModel("gemini-1.5-flash")
        img = Image.open(io.BytesIO(image_bytes))
        
        if analyze_for == "lost_person":
            prompt = """Analyze this image for people. Describe:
            1. How many people are visible
            2. Their approximate ages and genders
            3. What they are wearing (colors, clothing types)
            4. Any distinctive features
            5. Their activities or poses
            
            Focus on identifying individuals that could be lost persons in a crowd setting."""
        else:
            prompt = "Identify any safety anomalies like smoke, fire, stampede cues, or hazardous crowding. Respond 'none' if normal."
        
        resp = model.generate_content([prompt, img])
        text = (resp.text or "").lower()
        
        if analyze_for == "lost_person":
            return resp.text  # Return full analysis for lost person detection
        else:
            if any(k in text for k in ["smoke", "fire", "stampede", "fight", "hazard"]):
                return text
            return None
    except Exception:
        return None


def detect_lost_person_in_image(image_bytes: bytes, person_description: str = None) -> dict:
    """
    Enhanced function to detect lost persons in images using AI
    """
    if is_test_mode() or not _gemini_api_key():
        # Simulate detection in test mode
        return {
            "person_detected": bool(person_description and len(person_description) > 10),
            "confidence": 0.75 if person_description else 0.0,
            "details": "Simulated detection in test mode",
            "ai_analysis": "Test mode: Person detection simulation"
        }
    
    try:
        # Get AI analysis
        ai_analysis = gemini_vision_analyze(image_bytes, analyze_for="lost_person")
        
        result = {
            "person_detected": False,
            "confidence": 0.0,
            "details": "No matching person detected",
            "ai_analysis": ai_analysis or "No analysis available"
        }
        
        if ai_analysis and person_description:
            # Analyze the AI response for person matches
            ai_lower = ai_analysis.lower()
            desc_lower = person_description.lower()
            
            # Check for person presence
            if "person" in ai_lower or "people" in ai_lower:
                result["person_detected"] = True
                result["confidence"] = 0.6  # Base confidence for person detection
                
                # Try to match description keywords
                desc_keywords = desc_lower.split()
                matches = sum(1 for keyword in desc_keywords if keyword in ai_lower)
                if matches > 0:
                    result["confidence"] = min(0.95, 0.6 + (matches * 0.1))
                    result["details"] = f"Potential match found with {matches} description keywords"
                else:
                    result["details"] = "Person detected but no description match"
        
        return result
        
    except Exception as e:
        return {
            "person_detected": False,
            "confidence": 0.0,
            "details": f"Detection failed: {str(e)}",
            "ai_analysis": "Error in AI analysis"
        }


# --- Sentiment (optional extension) ---

def simple_sentiment(texts: List[str]) -> float:
    # naive score: negative keywords reduce score
    negatives = ["angry", "push", "stuck", "stampede", "scared", "panic"]
    score = 0.5
    for t in texts:
        t = t.lower()
        for w in negatives:
            if w in t:
                score -= 0.08
    return max(0.0, min(1.0, score))


# --- Heatmap Analysis and Commander Q&A ---

def analyze_heatmap_data(heatmap_points: List[Tuple], zones: List[dict] = None, 
                        incidents: List[str] = None) -> dict:
    """
    Analyze heatmap data and return structured insights
    """
    if not heatmap_points:
        return {"error": "No heatmap data available"}
    
    # Calculate basic statistics
    intensities = [point[2] for point in heatmap_points]
    avg_intensity = sum(intensities) / len(intensities)
    max_intensity = max(intensities)
    min_intensity = min(intensities)
    
    # Find hotspots (areas with high intensity)
    hotspot_threshold = avg_intensity + (max_intensity - avg_intensity) * 0.7
    hotspots = [(point[0], point[1], point[2]) for point in heatmap_points if point[2] > hotspot_threshold]
    
    # Analyze distribution
    high_density_areas = [point for point in heatmap_points if point[2] > 0.7]
    medium_density_areas = [point for point in heatmap_points if 0.3 < point[2] <= 0.7]
    low_density_areas = [point for point in heatmap_points if point[2] <= 0.3]
    
    # Zone analysis if zones provided
    zone_analysis = {}
    if zones:
        for zone in zones:
            zone_density = []
            for point in heatmap_points:
                # Simple distance check (in a real implementation, use proper zone boundary checking)
                distance = ((point[0] - zone['center_lat'])**2 + (point[1] - zone['center_lng'])**2)**0.5
                if distance < 0.001:  # Within zone area
                    zone_density.append(point[2])
            
            if zone_density:
                zone_analysis[zone['name']] = {
                    'avg_density': sum(zone_density) / len(zone_density),
                    'max_density': max(zone_density),
                    'point_count': len(zone_density),
                    'zone_type': zone.get('zone_type', 'unknown')
                }
    
    return {
        'total_points': len(heatmap_points),
        'average_intensity': avg_intensity,
        'max_intensity': max_intensity,
        'min_intensity': min_intensity,
        'hotspots': hotspots,
        'hotspot_count': len(hotspots),
        'distribution': {
            'high_density': len(high_density_areas),
            'medium_density': len(medium_density_areas),
            'low_density': len(low_density_areas)
        },
        'zone_analysis': zone_analysis,
        'recent_incidents': incidents or [],
        'risk_assessment': _assess_crowd_risk(avg_intensity, max_intensity, len(hotspots), incidents)
    }


def _assess_crowd_risk(avg_intensity: float, max_intensity: float, hotspot_count: int, incidents: List[str]) -> dict:
    """
    Assess crowd risk based on heatmap data
    """
    risk_score = 0
    
    # Intensity-based risk
    if avg_intensity > 0.7:
        risk_score += 3
    elif avg_intensity > 0.5:
        risk_score += 2
    elif avg_intensity > 0.3:
        risk_score += 1
    
    # Hotspot-based risk
    if hotspot_count > 5:
        risk_score += 3
    elif hotspot_count > 3:
        risk_score += 2
    elif hotspot_count > 1:
        risk_score += 1
    
    # Incident-based risk
    if incidents:
        high_risk_incidents = ['crowd control', 'security', 'medical', 'fire']
        incident_risk = sum(1 for incident in incidents if any(risk_word in incident.lower() for risk_word in high_risk_incidents))
        risk_score += incident_risk
    
    # Determine risk level
    if risk_score >= 6:
        risk_level = "HIGH"
        color = "red"
    elif risk_score >= 3:
        risk_level = "MEDIUM"
        color = "orange"
    else:
        risk_level = "LOW"
        color = "green"
    
    return {
        'risk_score': risk_score,
        'risk_level': risk_level,
        'color': color,
        'recommendations': _get_risk_recommendations(risk_level, avg_intensity, hotspot_count)
    }


def _get_risk_recommendations(risk_level: str, avg_intensity: float, hotspot_count: int) -> List[str]:
    """
    Generate risk-based recommendations
    """
    recommendations = []
    
    if risk_level == "HIGH":
        recommendations.extend([
            "Deploy additional security personnel immediately",
            "Consider crowd control measures in high-density areas",
            "Monitor hotspots closely for potential incidents",
            "Prepare emergency response teams"
        ])
    elif risk_level == "MEDIUM":
        recommendations.extend([
            "Increase monitoring in high-density areas",
            "Ensure security personnel are positioned near hotspots",
            "Prepare for potential crowd control needs"
        ])
    else:
        recommendations.extend([
            "Maintain current security levels",
            "Continue monitoring crowd movement",
            "Be prepared to respond to any incidents"
        ])
    
    if avg_intensity > 0.6:
        recommendations.append("Consider implementing crowd flow management")
    
    if hotspot_count > 3:
        recommendations.append("Investigate causes of multiple high-density areas")
    
    return recommendations


def gemini_commander_qa(question: str, heatmap_analysis: dict, event_context: dict = None) -> str:
    """
    Use Gemini AI to answer commander questions based on heatmap analysis
    """
    if is_test_mode() or not _gemini_api_key():
        # Simulated response in test mode
        return _generate_test_response(question, heatmap_analysis)
    
    try:
        import google.generativeai as genai
        
        genai.configure(api_key=_gemini_api_key())
        model = genai.GenerativeModel("gemini-1.5-flash")
        
        # Prepare context for AI
        context = f"""
        You are an AI assistant helping event security commanders analyze crowd density patterns and make informed decisions.
        
        Current Event Context:
        - Event: {event_context.get('event_name', 'Unknown') if event_context else 'Unknown'}
        - Venue: {event_context.get('venue_name', 'Unknown') if event_context else 'Unknown'}
        - Date: {event_context.get('date_time', 'Unknown') if event_context else 'Unknown'}
        
        Heatmap Analysis Data:
        - Total data points: {heatmap_analysis.get('total_points', 0)}
        - Average crowd density: {heatmap_analysis.get('average_intensity', 0):.2f}
        - Maximum density: {heatmap_analysis.get('max_intensity', 0):.2f}
        - Number of hotspots: {heatmap_analysis.get('hotspot_count', 0)}
        - Risk level: {heatmap_analysis.get('risk_assessment', {}).get('risk_level', 'Unknown')}
        
        Distribution Analysis:
        - High density areas: {heatmap_analysis.get('distribution', {}).get('high_density', 0)}
        - Medium density areas: {heatmap_analysis.get('distribution', {}).get('medium_density', 0)}
        - Low density areas: {heatmap_analysis.get('distribution', {}).get('low_density', 0)}
        
        Zone Analysis:
        {_format_zone_analysis(heatmap_analysis.get('zone_analysis', {}))}
        
        Recent Incidents:
        {', '.join(heatmap_analysis.get('recent_incidents', [])) if heatmap_analysis.get('recent_incidents') else 'None reported'}
        
        Risk Assessment:
        {_format_risk_assessment(heatmap_analysis.get('risk_assessment', {}))}
        
        Commander Question: {question}
        
        Please provide a detailed, actionable response based on the heatmap analysis. Focus on:
        1. Specific insights from the data
        2. Safety recommendations
        3. Resource allocation suggestions
        4. Potential concerns to monitor
        5. Immediate actions if needed
        
        Be concise but comprehensive, and prioritize safety and crowd management.
        """
        
        response = model.generate_content(context)
        return response.text.strip()
        
    except Exception as e:
        return f"AI analysis unavailable due to error: {str(e)}. Using fallback analysis."


def _format_zone_analysis(zone_analysis: dict) -> str:
    """Format zone analysis for AI context"""
    if not zone_analysis:
        return "No zone-specific data available"
    
    formatted = []
    for zone_name, data in zone_analysis.items():
        formatted.append(f"- {zone_name}: Avg density {data['avg_density']:.2f}, Max density {data['max_density']:.2f}, Type: {data['zone_type']}")
    
    return '\n'.join(formatted)


def _format_risk_assessment(risk_assessment: dict) -> str:
    """Format risk assessment for AI context"""
    if not risk_assessment:
        return "No risk assessment available"
    
    recommendations = '\n'.join([f"- {rec}" for rec in risk_assessment.get('recommendations', [])])
    
    return f"""
    Risk Level: {risk_assessment.get('risk_level', 'Unknown')}
    Risk Score: {risk_assessment.get('risk_score', 0)}
    Recommendations:
    {recommendations}
    """


def _generate_test_response(question: str, heatmap_analysis: dict) -> str:
    """Generate test response when AI is not available"""
    risk_level = heatmap_analysis.get('risk_assessment', {}).get('risk_level', 'LOW')
    avg_intensity = heatmap_analysis.get('average_intensity', 0)
    hotspot_count = heatmap_analysis.get('hotspot_count', 0)
    
    response = f"""
    **Test Mode Response for: "{question}"**
    
    Based on current heatmap analysis:
    - Average crowd density: {avg_intensity:.2f}
    - Number of hotspots: {hotspot_count}
    - Risk level: {risk_level}
    
    Recommendations:
    - Monitor high-density areas closely
    - Ensure adequate security coverage
    - Be prepared for crowd management if needed
    
    Note: This is a test mode response. Enable Gemini AI for detailed analysis.
    """
    
    return response
