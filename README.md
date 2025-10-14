# EventGuard AI (MVP)

An AI-powered situational awareness and crowd safety platform for large-scale events. Built with Streamlit, SQLite, and Google Gemini APIs.

## Quickstart

1. Create a virtual environment and install dependencies:

```bash
pip install -r requirements.txt
```

2. Configure secrets:
- Copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml` and fill values.
- For local development without OTP/email and without external APIs, set `TEST_MODE=true`.

3. Run the app:

```bash
streamlit run app.py
```

## Features
- Email/password auth with OTP (Test Mode bypass)
- Organizer Event Setup form saved to SQLite
- Predictive bottleneck analysis with simulated crowd data
- AI situational summaries (Gemini text)
- Folium heatmap map for risk zones
- Incident reporting and simulated resource dispatch
- Vision anomaly checks via OpenCV and optional Gemini Vision

## Environment & Secrets
Create `.streamlit/secrets.toml`:

```toml
[app]
TEST_MODE = true
DATABASE = "eventguard.db"

[gmail]
USER = "you@gmail.com"
APP_PASSWORD = "your_gmail_app_password"

[gemini]
API_KEY = ""

[google]
MAPS_API_KEY = ""
```

- If `TEST_MODE=true`, OTP is bypassed and external API calls are simulated.
- If keys are provided, real APIs will be used where available.

## Tables
- `users(id, email, hashed_password, otp, otp_expiry)`
- `events(id, organizer_id, event_name, goal, target_audience, date_time, venue_name, address, ticket_price, sponsors, description)`
- `incidents(id, type, location, timestamp, unit_assigned)`
- `alerts(id, zone, risk_level, prediction_time)`
