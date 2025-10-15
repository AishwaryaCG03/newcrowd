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
    
    # Create tables
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
            unit_assigned TEXT,
            severity TEXT DEFAULT 'medium',
            description TEXT,
            reporter_name TEXT,
            reporter_contact TEXT,
            status TEXT DEFAULT 'open',
            priority TEXT DEFAULT 'normal',
            additional_notes TEXT
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
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS lost_found_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            report_type TEXT NOT NULL,
            person_name TEXT,
            person_age INTEGER,
            person_gender TEXT,
            person_description TEXT,
            last_seen_location TEXT,
            last_seen_time TEXT,
            reporter_name TEXT,
            reporter_contact TEXT,
            additional_details TEXT,
            media_files TEXT,
            status TEXT DEFAULT 'active',
            timestamp TEXT NOT NULL,
            commander_notes TEXT,
            ai_detection_results TEXT
        );
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS zones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            zone_type TEXT NOT NULL,
            center_lat REAL NOT NULL,
            center_lng REAL NOT NULL,
            radius_meters REAL NOT NULL,
            description TEXT,
            density_threshold INTEGER DEFAULT 100,
            is_active BOOLEAN DEFAULT 1,
            created_at TEXT NOT NULL
        );
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS geo_alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            zone_id INTEGER NOT NULL,
            alert_type TEXT NOT NULL,
            entity_id TEXT,
            entity_lat REAL,
            entity_lng REAL,
            message TEXT NOT NULL,
            severity TEXT NOT NULL,
            is_resolved BOOLEAN DEFAULT 0,
            created_at TEXT NOT NULL,
            resolved_at TEXT,
            FOREIGN KEY (zone_id) REFERENCES zones(id)
        );
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS tracking_entities (
            id TEXT PRIMARY KEY,
            name TEXT,
            entity_type TEXT,
            current_lat REAL,
            current_lng REAL,
            last_seen TEXT,
            is_active BOOLEAN DEFAULT 1
        );
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS venue_blueprints (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER NOT NULL,
            blueprint_name TEXT NOT NULL,
            file_path TEXT NOT NULL,
            original_filename TEXT NOT NULL,
            file_size INTEGER,
            image_width INTEGER,
            image_height INTEGER,
            venue_bounds_north REAL,
            venue_bounds_south REAL,
            venue_bounds_east REAL,
            venue_bounds_west REAL,
            description TEXT,
            is_active BOOLEAN DEFAULT 1,
            uploaded_at TEXT NOT NULL,
            FOREIGN KEY (event_id) REFERENCES events(id)
        );
        """
    )
    
    # Add new columns to existing incidents table if they don't exist
    try:
        cur.execute("ALTER TABLE incidents ADD COLUMN severity TEXT DEFAULT 'medium'")
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    try:
        cur.execute("ALTER TABLE incidents ADD COLUMN description TEXT")
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    try:
        cur.execute("ALTER TABLE incidents ADD COLUMN reporter_name TEXT")
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    try:
        cur.execute("ALTER TABLE incidents ADD COLUMN reporter_contact TEXT")
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    try:
        cur.execute("ALTER TABLE incidents ADD COLUMN status TEXT DEFAULT 'open'")
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    try:
        cur.execute("ALTER TABLE incidents ADD COLUMN priority TEXT DEFAULT 'normal'")
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    try:
        cur.execute("ALTER TABLE incidents ADD COLUMN additional_notes TEXT")
    except sqlite3.OperationalError:
        pass  # Column already exists
    
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


def add_incident(type_: str, location: str, unit_assigned: str = None, severity: str = "medium", 
                description: str = None, reporter_name: str = None, reporter_contact: str = None,
                priority: str = "normal", additional_notes: str = None):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO incidents (type, location, timestamp, unit_assigned, severity, description, 
           reporter_name, reporter_contact, priority, additional_notes) 
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (type_, location, datetime.utcnow().isoformat(), unit_assigned, severity, description,
         reporter_name, reporter_contact, priority, additional_notes),
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


def add_lost_found_report(report_type: str, person_name: str = None, person_age: int = None,
                         person_gender: str = None, person_description: str = None,
                         last_seen_location: str = None, last_seen_time: str = None,
                         reporter_name: str = None, reporter_contact: str = None,
                         additional_details: str = None, media_files: str = None,
                         commander_notes: str = None, ai_detection_results: str = None):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO lost_found_reports (report_type, person_name, person_age, person_gender,
           person_description, last_seen_location, last_seen_time, reporter_name, reporter_contact,
           additional_details, media_files, commander_notes, ai_detection_results, timestamp)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (report_type, person_name, person_age, person_gender, person_description,
         last_seen_location, last_seen_time, reporter_name, reporter_contact,
         additional_details, media_files, commander_notes, ai_detection_results,
         datetime.utcnow().isoformat()),
    )
    conn.commit()
    conn.close()


def list_lost_found_reports(limit: int = 50, status: str = None):
    conn = get_conn()
    cur = conn.cursor()
    if status:
        cur.execute("SELECT * FROM lost_found_reports WHERE status = ? ORDER BY id DESC LIMIT ?", (status, limit))
    else:
        cur.execute("SELECT * FROM lost_found_reports ORDER BY id DESC LIMIT ?", (limit,))
    rows = cur.fetchall()
    conn.close()
    return rows


def update_lost_found_report(report_id: int, commander_notes: str = None, 
                           ai_detection_results: str = None, status: str = None):
    conn = get_conn()
    cur = conn.cursor()
    updates = []
    params = []
    
    if commander_notes is not None:
        updates.append("commander_notes = ?")
        params.append(commander_notes)
    if ai_detection_results is not None:
        updates.append("ai_detection_results = ?")
        params.append(ai_detection_results)
    if status is not None:
        updates.append("status = ?")
        params.append(status)
    
    if updates:
        params.append(report_id)
        query = f"UPDATE lost_found_reports SET {', '.join(updates)} WHERE id = ?"
        cur.execute(query, params)
        conn.commit()
    conn.close()


# Geo-fencing functions
def create_zone(name: str, zone_type: str, center_lat: float, center_lng: float, 
                radius_meters: float, description: str = None, density_threshold: int = 100):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO zones (name, zone_type, center_lat, center_lng, radius_meters, 
           description, density_threshold, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (name, zone_type, center_lat, center_lng, radius_meters, description, 
         density_threshold, datetime.utcnow().isoformat()),
    )
    conn.commit()
    conn.close()


def list_zones(active_only: bool = True):
    conn = get_conn()
    cur = conn.cursor()
    if active_only:
        cur.execute("SELECT * FROM zones WHERE is_active = 1 ORDER BY created_at DESC")
    else:
        cur.execute("SELECT * FROM zones ORDER BY created_at DESC")
    rows = cur.fetchall()
    conn.close()
    return rows


def get_zone_by_id(zone_id: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM zones WHERE id = ?", (zone_id,))
    row = cur.fetchone()
    conn.close()
    return row


def add_geo_alert(zone_id: int, alert_type: str, entity_id: str = None, 
                 entity_lat: float = None, entity_lng: float = None, 
                 message: str = "", severity: str = "medium"):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO geo_alerts (zone_id, alert_type, entity_id, entity_lat, 
           entity_lng, message, severity, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (zone_id, alert_type, entity_id, entity_lat, entity_lng, message, 
         severity, datetime.utcnow().isoformat()),
    )
    conn.commit()
    conn.close()


def list_geo_alerts(limit: int = 50, unresolved_only: bool = True):
    conn = get_conn()
    cur = conn.cursor()
    if unresolved_only:
        cur.execute("""SELECT ga.*, z.name as zone_name, z.zone_type 
                      FROM geo_alerts ga 
                      JOIN zones z ON ga.zone_id = z.id 
                      WHERE ga.is_resolved = 0 
                      ORDER BY ga.created_at DESC LIMIT ?""", (limit,))
    else:
        cur.execute("""SELECT ga.*, z.name as zone_name, z.zone_type 
                      FROM geo_alerts ga 
                      JOIN zones z ON ga.zone_id = z.id 
                      ORDER BY ga.created_at DESC LIMIT ?""", (limit,))
    rows = cur.fetchall()
    conn.close()
    return rows


def resolve_geo_alert(alert_id: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "UPDATE geo_alerts SET is_resolved = 1, resolved_at = ? WHERE id = ?",
        (datetime.utcnow().isoformat(), alert_id),
    )
    conn.commit()
    conn.close()


def add_tracking_entity(entity_id: str, name: str = None, entity_type: str = "person", 
                       lat: float = None, lng: float = None):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """INSERT OR REPLACE INTO tracking_entities 
           (id, name, entity_type, current_lat, current_lng, last_seen)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (entity_id, name, entity_type, lat, lng, datetime.utcnow().isoformat()),
    )
    conn.commit()
    conn.close()


def update_tracking_entity_location(entity_id: str, lat: float, lng: float):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """UPDATE tracking_entities 
           SET current_lat = ?, current_lng = ?, last_seen = ?
           WHERE id = ?""",
        (lat, lng, datetime.utcnow().isoformat(), entity_id),
    )
    conn.commit()
    conn.close()


def list_tracking_entities():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM tracking_entities WHERE is_active = 1")
    rows = cur.fetchall()
    conn.close()
    return rows


def get_entity_location(entity_id: str):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM tracking_entities WHERE id = ?", (entity_id,))
    row = cur.fetchone()
    conn.close()
    return row


# Blueprint management functions
def add_blueprint(event_id: int, blueprint_name: str, file_path: str, 
                 original_filename: str, file_size: int = None, 
                 image_width: int = None, image_height: int = None,
                 venue_bounds_north: float = None, venue_bounds_south: float = None,
                 venue_bounds_east: float = None, venue_bounds_west: float = None,
                 description: str = None):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO venue_blueprints (event_id, blueprint_name, file_path, original_filename,
           file_size, image_width, image_height, venue_bounds_north, venue_bounds_south,
           venue_bounds_east, venue_bounds_west, description, uploaded_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (event_id, blueprint_name, file_path, original_filename, file_size, 
         image_width, image_height, venue_bounds_north, venue_bounds_south,
         venue_bounds_east, venue_bounds_west, description, datetime.utcnow().isoformat()),
    )
    conn.commit()
    conn.close()


def get_blueprint_by_event(event_id: int, active_only: bool = True):
    conn = get_conn()
    cur = conn.cursor()
    if active_only:
        cur.execute("SELECT * FROM venue_blueprints WHERE event_id = ? AND is_active = 1 ORDER BY uploaded_at DESC", (event_id,))
    else:
        cur.execute("SELECT * FROM venue_blueprints WHERE event_id = ? ORDER BY uploaded_at DESC", (event_id,))
    row = cur.fetchone()
    conn.close()
    return row


def list_blueprints_by_user(user_id: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""SELECT vb.*, e.event_name 
                  FROM venue_blueprints vb 
                  JOIN events e ON vb.event_id = e.id 
                  WHERE e.organizer_id = ? AND vb.is_active = 1 
                  ORDER BY vb.uploaded_at DESC""", (user_id,))
    rows = cur.fetchall()
    conn.close()
    return rows


def update_blueprint_bounds(blueprint_id: int, north: float, south: float, east: float, west: float):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """UPDATE venue_blueprints 
           SET venue_bounds_north = ?, venue_bounds_south = ?, 
               venue_bounds_east = ?, venue_bounds_west = ?
           WHERE id = ?""",
        (north, south, east, west, blueprint_id),
    )
    conn.commit()
    conn.close()


def deactivate_blueprint(blueprint_id: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE venue_blueprints SET is_active = 0 WHERE id = ?", (blueprint_id,))
    conn.commit()
    conn.close()


# Initialize DB on import
init_db()
