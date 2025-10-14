import random
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

from db import add_incident, list_incidents
from maps import add_route_to_map, create_heatmap, directions_route


def incidents_dispatch_page():
    st.header("Incidents & Intelligent Dispatch")
    with st.form("incident_form"):
        type_ = st.selectbox("Type", ["medical", "security", "lost"]) 
        location = st.text_input("Location description (e.g., North Gate)")
        submit = st.form_submit_button("Report Incident")
    if submit:
        add_incident(type_, location)
        st.success("Incident recorded")

    st.subheader("Recent Incidents")
    rows = list_incidents(20)
    if rows:
        df = pd.DataFrame([dict(r) for r in rows])
        cols = ["id", "type", "location", "timestamp", "unit_assigned"]
        existing = [c for c in cols if c in df.columns]
        st.dataframe(df[existing] if existing else df)

    st.subheader("Dispatch Simulation")
    base = (28.6139, 77.2090)
    if "dispatch_state" not in st.session_state:
        st.session_state.dispatch_state = {}

    state = st.session_state.dispatch_state
    if not state.get("initialized"):
        dest = (
            base[0] + random.uniform(-0.01, 0.01),
            base[1] + random.uniform(-0.01, 0.01),
        )
        units = [
            ("Unit A", (base[0] + 0.003, base[1] - 0.003)),
            ("Unit B", (base[0] - 0.004, base[1] + 0.002)),
            ("Unit C", (base[0] + 0.005, base[1] + 0.004)),
        ]
        unit_name, origin = random.choice(units)
        route, eta = directions_route(origin, dest)
        state.update({
            "base": base,
            "dest": dest,
            "unit_name": unit_name,
            "origin": origin,
            "route": route,
            "eta": eta,
            "initialized": True,
        })

    cols = st.columns([1, 1])
    with cols[0]:
        if st.button("New Dispatch"):
            dest = (
                base[0] + random.uniform(-0.01, 0.01),
                base[1] + random.uniform(-0.01, 0.01),
            )
            units = [
                ("Unit A", (base[0] + 0.003, base[1] - 0.003)),
                ("Unit B", (base[0] - 0.004, base[1] + 0.002)),
                ("Unit C", (base[0] + 0.005, base[1] + 0.004)),
            ]
            unit_name, origin = random.choice(units)
            route, eta = directions_route(origin, dest)
            state.update({
                "dest": dest,
                "unit_name": unit_name,
                "origin": origin,
                "route": route,
                "eta": eta,
            })

    m = create_heatmap(base, [])
    add_route_to_map(m, state.get("route", []), color="red")
    st_folium(m, width=800, height=500, key="dispatch_map")

    eta_min = state.get("eta") if state.get("eta") is not None else 4
    st.success(f"🚑 {state.get('unit_name', 'Unit')} dispatched – ETA {eta_min} mins")
