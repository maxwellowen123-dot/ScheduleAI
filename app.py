import os, re, json
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, session, jsonify, url_for
from dotenv import load_dotenv
import dateparser

from werkzeug.middleware.proxy_fix import ProxyFix

load_dotenv()
app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "change-me-in-production")
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)
app.config.update(
    SESSION_COOKIE_SECURE=os.getenv("SESSION_COOKIE_SECURE", "1") == "1",
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
)

SCOPES = ["https://www.googleapis.com/auth/calendar.events"]

def parse_request(text: str):
    """
    Simple natural-language fallback parser.
    Examples:
      "Dentist tomorrow at 3pm for 1 hour"
      "Gym Friday at 5:30pm for 90 minutes"
      "Call John August 30 at 2pm for 30 minutes"
    """
    clean = text.strip()
    duration = 60

    m = re.search(r'for\s+(\d+)\s*(minutes?|mins?)', clean, re.I)
    if m:
        duration = int(m.group(1))
        clean = clean[:m.start()].strip()
    else:
        m = re.search(r'for\s+(\d+(?:\.\d+)?)\s*(hours?|hrs?)', clean, re.I)
        if m:
            duration = int(float(m.group(1)) * 60)
            clean = clean[:m.start()].strip()

    # Find a date/time phrase by trying progressively larger suffixes.
    words = clean.split()
    parsed_dt = None
    split_index = None
    for i in range(1, len(words)):
        candidate = " ".join(words[i:])
        dt = dateparser.parse(
            candidate,
            settings={
                "PREFER_DATES_FROM": "future",
                "RETURN_AS_TIMEZONE_AWARE": False
            }
        )
        if dt:
            parsed_dt = dt
            split_index = i
            break

    if not parsed_dt:
        # Try the entire text, in case it is mostly a time phrase.
        parsed_dt = dateparser.parse(
            clean,
            settings={"PREFER_DATES_FROM": "future", "RETURN_AS_TIMEZONE_AWARE": False}
        )

    title = " ".join(words[:split_index]).strip(" ,.-") if split_index else clean
    title = re.sub(r'\b(on|at)\s*$', '', title, flags=re.I).strip()
    if not title:
        title = "New event"

    if not parsed_dt:
        raise ValueError("I couldn't understand the date/time. Try: 'Dentist tomorrow at 3pm for 1 hour'.")

    return {
        "title": title,
        "start": parsed_dt.isoformat(timespec="minutes"),
        "end": (parsed_dt + timedelta(minutes=duration)).isoformat(timespec="minutes"),
        "duration_minutes": duration
    }

def creds_from_session():
    if "google_creds" not in session:
        return None
    from google.oauth2.credentials import Credentials
    return Credentials(**session["google_creds"])

@app.route("/health")
def health():
    return {"ok": True}

@app.route("/")
def index():
    return render_template("index.html", connected=("google_creds" in session))

@app.route("/connect-google")
def connect_google():
    if not os.path.exists("client_secret.json"):
        return (
            "Missing client_secret.json. Follow README.md to create Google OAuth credentials.",
            400
        )
    from google_auth_oauthlib.flow import Flow
    base_url = os.getenv("APP_BASE_URL", "").rstrip("/")
    redirect_uri = f"{base_url}/oauth2callback" if base_url else url_for("oauth2callback", _external=True)
    flow = Flow.from_client_secrets_file(
        "client_secret.json",
        scopes=SCOPES,
        redirect_uri=redirect_uri,
    )
    auth_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent"
    )
    session["oauth_state"] = state
    return redirect(auth_url)

@app.route("/oauth2callback")
def oauth2callback():
    from google_auth_oauthlib.flow import Flow
    base_url = os.getenv("APP_BASE_URL", "").rstrip("/")
    redirect_uri = f"{base_url}/oauth2callback" if base_url else url_for("oauth2callback", _external=True)
    flow = Flow.from_client_secrets_file(
        "client_secret.json",
        scopes=SCOPES,
        state=session.get("oauth_state"),
        redirect_uri=redirect_uri,
    )
    flow.fetch_token(authorization_response=request.url)
    creds = flow.credentials
    session["google_creds"] = {
        "token": creds.token,
        "refresh_token": creds.refresh_token,
        "token_uri": creds.token_uri,
        "client_id": creds.client_id,
        "client_secret": creds.client_secret,
        "scopes": creds.scopes,
    }
    return redirect("/")

@app.route("/disconnect-google")
def disconnect_google():
    session.pop("google_creds", None)
    return redirect("/")

@app.route("/api/preview", methods=["POST"])
def preview():
    data = request.get_json(force=True)
    text = data.get("text", "")
    try:
        parsed = parse_request(text)
        return jsonify({"ok": True, "event": parsed})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400

@app.route("/api/schedule", methods=["POST"])
def schedule():
    creds = creds_from_session()
    if not creds:
        return jsonify({"ok": False, "error": "Connect Google Calendar first."}), 401

    data = request.get_json(force=True)
    text = data.get("text", "")
    try:
        event = parse_request(text)
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400

    from googleapiclient.discovery import build
    service = build("calendar", "v3", credentials=creds)

    body = {
        "summary": event["title"],
        "start": {"dateTime": event["start"], "timeZone": os.getenv("CALENDAR_TIMEZONE", "America/Chicago")},
        "end": {"dateTime": event["end"], "timeZone": os.getenv("CALENDAR_TIMEZONE", "America/Chicago")},
    }
    created = service.events().insert(calendarId="primary", body=body).execute()

    # Refresh saved credentials after API use.
    session["google_creds"]["token"] = creds.token

    return jsonify({
        "ok": True,
        "event": event,
        "calendar_link": created.get("htmlLink")
    })

if __name__ == "__main__":
    app.run(debug=True, port=5000)
