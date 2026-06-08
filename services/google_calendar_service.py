"""
google_calendar_service.py
──────────────────────────
Google Calendar integration using OAuth2 + googleapis.
Stores tokens in session (passed in from app.py).

Required env vars:
    GOOGLE_CLIENT_ID
    GOOGLE_CLIENT_SECRET
    GOOGLE_REDIRECT_URI   (e.g. http://localhost:5000/gcal/callback)
"""

import os
import json
import urllib.parse
import urllib.request


SCOPES = "https://www.googleapis.com/auth/calendar"
AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
CALENDAR_API = "https://www.googleapis.com/calendar/v3"


class GoogleCalendarService:

    def __init__(self):
        self.client_id     = os.environ.get("GOOGLE_CLIENT_ID", "").strip()
        self.client_secret = os.environ.get("GOOGLE_CLIENT_SECRET", "").strip()
        self.redirect_uri  = os.environ.get(
            "GOOGLE_REDIRECT_URI", "http://localhost:5000/gcal/callback"
        ).strip()

    def is_configured(self):
        return bool(self.client_id and self.client_secret)

    def get_auth_url(self):
        params = {
            "client_id":     self.client_id,
            "redirect_uri":  self.redirect_uri,
            "response_type": "code",
            "scope":         SCOPES,
            "access_type":   "offline",
            "prompt":        "consent",
        }
        return AUTH_URL + "?" + urllib.parse.urlencode(params)

    def exchange_code(self, code):
        """Exchange auth code for access+refresh tokens."""
        data = urllib.parse.urlencode({
            "code":          code,
            "client_id":     self.client_id,
            "client_secret": self.client_secret,
            "redirect_uri":  self.redirect_uri,
            "grant_type":    "authorization_code",
        }).encode()
        req = urllib.request.Request(TOKEN_URL, data=data,
<<<<<<< HEAD
                                    headers={"Content-Type": "application/x-www-form-urlencoded"})
=======
                                     headers={"Content-Type": "application/x-www-form-urlencoded"})
>>>>>>> 0775f6f3439142a094b03eb2f2a4da54fcb7f3fe
        try:
            with urllib.request.urlopen(req) as resp:
                return True, json.loads(resp.read())
        except Exception as e:
            return False, str(e)

    def refresh_token(self, refresh_tok):
        data = urllib.parse.urlencode({
            "refresh_token": refresh_tok,
            "client_id":     self.client_id,
            "client_secret": self.client_secret,
            "grant_type":    "refresh_token",
        }).encode()
        req = urllib.request.Request(TOKEN_URL, data=data,
<<<<<<< HEAD
                                    headers={"Content-Type": "application/x-www-form-urlencoded"})
=======
                                     headers={"Content-Type": "application/x-www-form-urlencoded"})
>>>>>>> 0775f6f3439142a094b03eb2f2a4da54fcb7f3fe
        try:
            with urllib.request.urlopen(req) as resp:
                return True, json.loads(resp.read())
        except Exception as e:
            return False, str(e)

    def _api(self, access_token, method, path, body=None):
        url = CALENDAR_API + path
        data = json.dumps(body).encode() if body else None
        req = urllib.request.Request(url, data=data, method=method,
<<<<<<< HEAD
                                    headers={
                                        "Authorization": "Bearer " + access_token,
                                        "Content-Type": "application/json",
                                    })
=======
                                     headers={
                                         "Authorization": "Bearer " + access_token,
                                         "Content-Type": "application/json",
                                     })
>>>>>>> 0775f6f3439142a094b03eb2f2a4da54fcb7f3fe
        try:
            with urllib.request.urlopen(req) as resp:
                return True, json.loads(resp.read())
        except urllib.error.HTTPError as e:
            return False, json.loads(e.read())
        except Exception as e:
            return False, str(e)

    def create_event(self, access_token, contact_name, date, time_slot, title, notes=""):
        """Create a Google Calendar event and return (ok, event_id_or_error)."""
        start_dt = f"{date}T{time_slot}:00"
        # end = 30 min later
        from datetime import datetime, timedelta
        start = datetime.strptime(start_dt, "%Y-%m-%dT%H:%M:%S")
        end   = start + timedelta(minutes=30)
        end_dt = end.strftime("%Y-%m-%dT%H:%M:%S")

        summary = title if title else f"RDV – {contact_name}"
        body = {
            "summary":     summary,
            "description": f"Contact : {contact_name}\n{notes}".strip(),
            "start":       {"dateTime": start_dt, "timeZone": "Africa/Casablanca"},
            "end":         {"dateTime": end_dt,   "timeZone": "Africa/Casablanca"},
            "reminders": {
                "useDefault": False,
                "overrides": [
                    {"method": "email",  "minutes": 1440},  # 24h
                    {"method": "popup",  "minutes": 30},
                ],
            },
        }
        ok, resp = self._api(access_token, "POST", "/calendars/primary/events", body)
        if ok:
            return True, resp.get("id", "")
        return False, str(resp)

    def delete_event(self, access_token, event_id):
        if not event_id:
            return True, "no event"
        ok, resp = self._api(access_token, "DELETE", f"/calendars/primary/events/{event_id}")
        return ok, resp
