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

def gemini_vision_analyze(image_bytes: bytes) -> Optional[str]:
    if is_test_mode() or not _gemini_api_key():
        return None  # simulate 'no anomaly' by default
    try:
        import google.generativeai as genai
        from PIL import Image
        import io

        genai.configure(api_key=_gemini_api_key())
        model = genai.GenerativeModel("gemini-1.5-flash")
        img = Image.open(io.BytesIO(image_bytes))
        prompt = "Identify any safety anomalies like smoke, fire, stampede cues, or hazardous crowding. Respond 'none' if normal."
        resp = model.generate_content([prompt, img])
        text = (resp.text or "").lower()
        if any(k in text for k in ["smoke", "fire", "stampede", "fight", "hazard"]):
            return text
        return None
    except Exception:
        return None


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
