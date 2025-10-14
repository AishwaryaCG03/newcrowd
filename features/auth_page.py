import pandas as pd
import streamlit as st

from auth import begin_login, complete_login, is_test_mode, signup
from db import get_user_by_email


def auth_page():
    tabs = st.tabs(["Login", "Sign up"])

    with tabs[0]:
        st.header("Login")
        with st.form("login_form"):
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Send OTP")
        if submitted:
            ok = begin_login(email, password)
            if ok:
                st.success("OTP sent to your email" if not is_test_mode() else "Test Mode: OTP bypass")
                st.session_state["pending_email"] = email
            else:
                st.error("Invalid credentials or email service unavailable")

        if st.session_state.get("pending_email"):
            with st.form("otp_form"):
                otp = st.text_input("Enter 6-digit OTP")
                verify = st.form_submit_button("Verify & Login")
            if verify:
                email = st.session_state.get("pending_email")
                if complete_login(email, otp):
                    user = get_user_by_email(email)
                    st.session_state.auth = {"logged_in": True, "email": email, "user_id": int(user["id"]) }
                    st.session_state.page = "event_setup"
                    st.success("Login successful")
                    st.rerun()
                else:
                    st.error("OTP invalid or expired")

    with tabs[1]:
        st.header("Sign up")
        with st.form("signup_form"):
            email = st.text_input("Email", key="s_email")
            password = st.text_input("Password", type="password", key="s_password")
            cpassword = st.text_input("Confirm Password", type="password", key="s_cpassword")
            submitted = st.form_submit_button("Create account")
        if submitted:
            if password != cpassword:
                st.error("Passwords do not match")
            elif not email or not password:
                st.error("Email and password required")
            else:
                if signup(email, password):
                    st.success("Account created. Please login.")
                else:
                    st.error("Email already exists")
