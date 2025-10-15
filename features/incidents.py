import pandas as pd
import streamlit as st
from db import add_incident, list_incidents


def incidents_page():
    st.header("Incident Reporting")
    
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
    
    else:
        st.info("No incidents reported yet.")
