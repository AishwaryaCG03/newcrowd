import os
from datetime import datetime
import random
from typing import List, Tuple

import numpy as np
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

# Configure Streamlit FIRST, before any local imports that may access st.secrets
st.set_page_config(page_title="EventGuard AI", page_icon="🛡️", layout="wide")

from core.ui import ensure_session, header, nav
from features.auth_page import auth_page
from features.event_setup import event_setup_page
from features.dashboard import dashboard_page
from features.predictive import predictive_page
from features.ai_summaries import ai_summaries_page
from features.incidents import incidents_dispatch_page
from features.vision import vision_page


 


def main():
    ensure_session()
    header()
    if not st.session_state.auth.get("logged_in"):
        auth_page()
        return

    choice = nav() or "Dashboard"
    if choice == "Dashboard":
        dashboard_page()
    elif choice == "Event Setup":
        event_setup_page()
    elif choice == "Predictive Bottlenecks":
        predictive_page()
    elif choice == "AI Summaries":
        ai_summaries_page()
    elif choice == "Incidents & Dispatch":
        incidents_dispatch_page()
    elif choice == "Vision Anomaly Detection":
        vision_page()


if __name__ == "__main__":
    main()
