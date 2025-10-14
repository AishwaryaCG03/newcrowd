import os
import random
import smtplib
from email.mime.text import MIMEText

import bcrypt

try:
    import streamlit as st
except Exception:
    st = None

from db import get_user_by_email, create_user, save_otp, verify_otp, clear_otp


def is_test_mode() -> bool:
    try:
        if st is not None and "TEST_MODE" in st.secrets.get("app", {}):
            return bool(st.secrets["app"]["TEST_MODE"])
    except Exception:
        pass
    return os.environ.get("EVENTGUARD_TEST_MODE", "false").lower() in ["1", "true", "yes"]


def hash_password(password: str) -> bytes:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())


def check_password(password: str, hashed: bytes) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed)
    except Exception:
        return False


def _smtp_settings():
    user = ""
    app_password = ""
    if st is not None:
        try:
            user = st.secrets.get("gmail", {}).get("USER", "")
            app_password = st.secrets.get("gmail", {}).get("APP_PASSWORD", "")
        except Exception:
            # secrets.toml not present; fall back to env vars
            user = ""
            app_password = ""
    user = os.environ.get("GMAIL_USER", user)
    app_password = os.environ.get("GMAIL_APP_PASSWORD", app_password)
    return user, app_password


def send_otp_email(to_email: str, otp: str) -> bool:
    if is_test_mode():
        return True
    user, app_password = _smtp_settings()
    if not user or not app_password:
        return False
    msg = MIMEText(f"Your EventGuard AI OTP is: {otp}. It expires in 5 minutes.")
    msg["Subject"] = "EventGuard AI OTP"
    msg["From"] = user
    msg["To"] = to_email
    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(user, app_password)
            server.send_message(msg)
        return True
    except Exception:
        return False


def signup(email: str, password: str) -> bool:
    if get_user_by_email(email):
        return False
    hp = hash_password(password)
    create_user(email, hp)
    return True


def begin_login(email: str, password: str) -> bool:
    row = get_user_by_email(email)
    if not row:
        return False
    if not check_password(password, row["hashed_password"]):
        return False
    otp = str(random.randint(100000, 999999))
    save_otp(email, otp, 5)
    return send_otp_email(email, otp)


def complete_login(email: str, otp: str) -> bool:
    if is_test_mode():
        return True
    ok = verify_otp(email, otp)
    if ok:
        clear_otp(email)
    return ok
