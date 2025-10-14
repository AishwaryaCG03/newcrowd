import sqlite3
import os
from datetime import datetime, timedelta

DB_PATH = os.environ.get("EVENTGUARD_DB", None)

try:
    import streamlit as st
    if "DATABASE" in st.secrets.get("app", {}):
        DB_PATH = st.secrets["app"]["DATABASE"]
except Exception:
    pass

if not DB_PATH:
    DB_PATH = "eventguard.db"


def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            hashed_password BLOB NOT NULL,
            otp TEXT,
            otp_expiry TEXT
        );
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            organizer_id INTEGER NOT NULL,
            event_name TEXT NOT NULL,
            goal TEXT NOT NULL,
            target_audience TEXT NOT NULL,
            date_time TEXT NOT NULL,
            venue_name TEXT NOT NULL,
            address TEXT NOT NULL,
            ticket_price REAL,
            sponsors TEXT,
            description TEXT NOT NULL,
            FOREIGN KEY (organizer_id) REFERENCES users(id)
        );
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS incidents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT NOT NULL,
            location TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            unit_assigned TEXT
        );
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            zone TEXT NOT NULL,
            risk_level TEXT NOT NULL,
            prediction_time TEXT NOT NULL
        );
        """
    )
    conn.commit()
    conn.close()


def create_user(email: str, hashed_password: bytes):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO users (email, hashed_password) VALUES (?, ?)",
        (email.lower(), hashed_password),
    )
    conn.commit()
    conn.close()


def get_user_by_email(email: str):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE email = ?", (email.lower(),))
    row = cur.fetchone()
    conn.close()
    return row


def save_otp(email: str, otp: str, expiry_minutes: int = 5):
    expiry = (datetime.utcnow() + timedelta(minutes=expiry_minutes)).isoformat()
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "UPDATE users SET otp = ?, otp_expiry = ? WHERE email = ?",
        (otp, expiry, email.lower()),
    )
    conn.commit()
    conn.close()


def clear_otp(email: str):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE users SET otp = NULL, otp_expiry = NULL WHERE email = ?", (email.lower(),))
    conn.commit()
    conn.close()


def verify_otp(email: str, otp: str) -> bool:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT otp, otp_expiry FROM users WHERE email = ?", (email.lower(),))
    row = cur.fetchone()
    conn.close()
    if not row:
        return False
    if not row["otp"] or not row["otp_expiry"]:
        return False
    try:
        expiry = datetime.fromisoformat(row["otp_expiry"])
    except ValueError:
        return False
    if datetime.utcnow() > expiry:
        return False
    return str(row["otp"]) == str(otp)


def create_event(organizer_id: int, data: dict):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO events (organizer_id, event_name, goal, target_audience, date_time, venue_name, address, ticket_price, sponsors, description)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            organizer_id,
            data.get("event_name"),
            data.get("goal"),
            data.get("target_audience"),
            data.get("date_time"),
            data.get("venue_name"),
            data.get("address"),
            data.get("ticket_price"),
            data.get("sponsors"),
            data.get("description"),
        ),
    )
    conn.commit()
    conn.close()


def list_events_by_user(user_id: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM events WHERE organizer_id = ? ORDER BY id DESC", (user_id,))
    rows = cur.fetchall()
    conn.close()
    return rows


def add_incident(type_: str, location: str, unit_assigned: str = None):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO incidents (type, location, timestamp, unit_assigned) VALUES (?, ?, ?, ?)",
        (type_, location, datetime.utcnow().isoformat(), unit_assigned),
    )
    conn.commit()
    conn.close()


def list_incidents(limit: int = 50):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM incidents ORDER BY id DESC LIMIT ?", (limit,))
    rows = cur.fetchall()
    conn.close()
    return rows


def add_alert(zone: str, risk_level: str, prediction_time: str):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO alerts (zone, risk_level, prediction_time) VALUES (?, ?, ?)",
        (zone, risk_level, prediction_time),
    )
    conn.commit()
    conn.close()


def list_alerts(limit: int = 50):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM alerts ORDER BY id DESC LIMIT ?", (limit,))
    rows = cur.fetchall()
    conn.close()
    return rows


# Initialize DB on import
init_db()
