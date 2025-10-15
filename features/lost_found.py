import streamlit as st
import pandas as pd
import base64
import io
from PIL import Image
import cv2
import numpy as np
from datetime import datetime

from db import add_lost_found_report, list_lost_found_reports, update_lost_found_report
from ai import gemini_vision_analyze, detect_lost_person_in_image


def detect_person_in_media(image_bytes: bytes, person_description: str = None) -> dict:
    """
    Use AI to detect if a person matching the description is in the uploaded media
    """
    return detect_lost_person_in_image(image_bytes, person_description)


def lost_found_page():
    st.header("Lost & Found Management")
    
    # Tab interface for different functions
    tab1, tab2, tab3 = st.tabs(["📝 Report Lost/Found", "🔍 Commander Review", "📋 Active Reports"])
    
    with tab1:
        st.subheader("Report Lost or Found Person")
        
        with st.form("lost_found_form"):
            report_type = st.selectbox("Report Type", ["lost", "found"])
            
            col1, col2 = st.columns(2)
            with col1:
                person_name = st.text_input("Person Name (if known)")
                person_age = st.number_input("Age", min_value=0, max_value=120, value=None, step=1)
                person_gender = st.selectbox("Gender", ["", "male", "female", "other", "prefer not to say"])
            
            with col2:
                last_seen_location = st.text_input("Last Seen Location", placeholder="e.g., Main Stage, Food Court, Parking Lot")
                last_seen_time = st.text_input("Last Seen Time", placeholder="e.g., 2:30 PM, 1 hour ago")
                reporter_name = st.text_input("Your Name")
                reporter_contact = st.text_input("Your Contact Info", placeholder="Phone or Email")
            
            person_description = st.text_area(
                "Physical Description", 
                placeholder="Describe clothing, height, hair color, distinctive features, etc."
            )
            
            additional_details = st.text_area(
                "Additional Details", 
                placeholder="Any other relevant information about the situation..."
            )
            
            # File upload for user reports (optional)
            uploaded_file = st.file_uploader(
                "Upload Photo (Optional)", 
                type=['jpg', 'jpeg', 'png'],
                help="Upload a photo if you found someone or have a photo of the lost person"
            )
            
            submit = st.form_submit_button("Submit Report", type="primary")
        
        if submit:
            if not reporter_name.strip():
                st.error("Please provide your name")
            elif report_type == "lost" and not person_description.strip():
                st.error("Please provide a description of the lost person")
            else:
                media_files = None
                if uploaded_file:
                    media_files = f"user_upload_{uploaded_file.name}"
                    # Store the file (in a real app, you'd save it to a proper file system)
                
                add_lost_found_report(
                    report_type=report_type,
                    person_name=person_name if person_name.strip() else None,
                    person_age=person_age,
                    person_gender=person_gender if person_gender else None,
                    person_description=person_description if person_description.strip() else None,
                    last_seen_location=last_seen_location if last_seen_location.strip() else None,
                    last_seen_time=last_seen_time if last_seen_time.strip() else None,
                    reporter_name=reporter_name,
                    reporter_contact=reporter_contact if reporter_contact.strip() else None,
                    additional_details=additional_details if additional_details.strip() else None,
                    media_files=media_files
                )
                
                st.success(f"✅ {report_type.capitalize()} person report submitted successfully!")
                st.info("Commanders will review your report and take appropriate action.")
    
    with tab2:
        st.subheader("Commander Review & AI Analysis")
        st.write("Upload surveillance footage or photos to check for lost persons")
        
        # Get active lost person reports
        lost_reports = list_lost_found_reports(status="active")
        lost_reports = [r for r in lost_reports if r["report_type"] == "lost"]
        
        if not lost_reports:
            st.info("No active lost person reports to review.")
        else:
            st.write("**Active Lost Person Reports:**")
            for report in lost_reports[:5]:  # Show top 5
                st.write(f"• {report['person_name'] or 'Unknown'} - {report['person_description']}")
        
        # Media upload for commanders
        uploaded_media = st.file_uploader(
            "Upload Surveillance Footage or Photo", 
            type=['jpg', 'jpeg', 'png', 'mp4', 'avi', 'mov'],
            help="Upload surveillance footage or photos to check for lost persons"
        )
        
        if uploaded_media:
            # Display uploaded media
            if uploaded_media.type.startswith('image'):
                image = Image.open(uploaded_media)
                st.image(image, caption="Uploaded Image", use_column_width=True)
                
                # AI analysis
                st.subheader("AI Analysis")
                with st.spinner("Analyzing image for lost persons..."):
                    image_bytes = uploaded_media.read()
                    uploaded_media.seek(0)  # Reset file pointer
                    
                    # Get the first lost report for comparison
                    if lost_reports:
                        first_report = lost_reports[0]
                        detection_result = detect_person_in_media(
                            image_bytes, 
                            first_report['person_description'] if first_report['person_description'] else ''
                        )
                        
                        col1, col2 = st.columns(2)
                        with col1:
                            st.metric("Person Detected", "Yes" if detection_result["person_detected"] else "No")
                            st.metric("Confidence", f"{detection_result['confidence']:.1%}")
                        
                        with col2:
                            st.write("**AI Analysis:**")
                            st.write(detection_result["ai_analysis"])
                        
                        st.write("**Detection Details:**")
                        st.write(detection_result["details"])
                        
                        # Update report with AI results
                        if st.button("Update Report with AI Results"):
                            report_id = first_report['id']
                            ai_results = f"Person detected: {detection_result['person_detected']}, Confidence: {detection_result['confidence']:.1%}, Details: {detection_result['details']}"
                            update_lost_found_report(
                                report_id=report_id,
                                ai_detection_results=ai_results
                            )
                            st.success("Report updated with AI analysis results!")
                    else:
                        st.warning("No active lost person reports to compare against.")
            
            else:
                st.info("Video analysis feature would be implemented here for uploaded videos.")
    
    with tab3:
        st.subheader("Active Reports")
        
        # Filter options
        col1, col2 = st.columns(2)
        with col1:
            filter_type = st.selectbox("Filter by Type", ["all", "lost", "found"])
        with col2:
            filter_status = st.selectbox("Filter by Status", ["all", "active", "resolved", "closed"])
        
        # Get reports based on filters
        if filter_status == "all":
            reports = list_lost_found_reports(limit=50)
        else:
            reports = list_lost_found_reports(limit=50, status=filter_status)
        
        if filter_type != "all":
            reports = [r for r in reports if r["report_type"] == filter_type]
        
        if reports:
            st.write(f"**Found {len(reports)} reports**")
            
            for report in reports:
                with st.expander(f"🔍 {report['report_type'].upper()} - {report['person_name'] or 'Unknown Person'} ({report['status']})"):
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        st.write(f"**Type:** {report['report_type']}")
                        st.write(f"**Name:** {report['person_name'] or 'Not provided'}")
                        st.write(f"**Age:** {report['person_age'] or 'Not provided'}")
                        st.write(f"**Gender:** {report['person_gender'] or 'Not provided'}")
                    
                    with col2:
                        st.write(f"**Description:** {report['person_description'] or 'Not provided'}")
                        st.write(f"**Last Seen Location:** {report['last_seen_location'] or 'Not provided'}")
                        st.write(f"**Last Seen Time:** {report['last_seen_time'] or 'Not provided'}")
                        st.write(f"**Reporter:** {report['reporter_name']}")
                    
                    with col3:
                        st.write(f"**Contact:** {report['reporter_contact'] or 'Not provided'}")
                        st.write(f"**Status:** {report['status']}")
                        st.write(f"**Reported:** {report['timestamp']}")
                        if report['commander_notes']:
                            st.write(f"**Commander Notes:** {report['commander_notes']}")
                        if report['ai_detection_results']:
                            st.write(f"**AI Results:** {report['ai_detection_results']}")
                    
                    # Commander actions
                    if report['status'] == 'active':
                        col_btn1, col_btn2, col_btn3 = st.columns(3)
                        with col_btn1:
                            if st.button(f"Mark Found", key=f"found_{report['id']}"):
                                update_lost_found_report(report['id'], status="resolved")
                                st.success(f"Report {report['id']} marked as resolved!")
                                st.rerun()
                        
                        with col_btn2:
                            if st.button(f"Add Notes", key=f"notes_{report['id']}"):
                                notes = st.text_area(f"Commander Notes for Report {report['id']}", key=f"notes_text_{report['id']}")
                                if st.button(f"Save Notes", key=f"save_notes_{report['id']}"):
                                    update_lost_found_report(report['id'], commander_notes=notes)
                                    st.success("Notes saved!")
                                    st.rerun()
                        
                        with col_btn3:
                            if st.button(f"Close Report", key=f"close_{report['id']}"):
                                update_lost_found_report(report['id'], status="closed")
                                st.success(f"Report {report['id']} closed!")
                                st.rerun()
        else:
            st.info("No reports found matching the current filters.")
