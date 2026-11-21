"""
Google OAuth 2.0 (Authorization Code flow) — asli Google login, stdlib se.

Kaam karne ke liye apni GOOGLE_CLIENT_ID aur GOOGLE_CLIENT_SECRET
app/config.py mein ya environment variable se set karo.

Free credentials lene ke steps (5 minute):
1. https://console.cloud.google.com/apis/credentials kholo
2. "Create Credentials" -> "OAuth client ID" -> Application type: "Web application"
3. Authorized redirect URI mein daalo: http://localhost:8000/auth/google/callback
4. Client ID aur Client Secret copy karke config.py mein paste kar do
"""
import json
import secrets
import urllib.parse
import urllib.request

from app import config

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"

_pending_states = set()


def is_configured():
    return bool(config.GOOGLE_CLIENT_ID and config.GOOGLE_CLIENT_SECRET)


def login_url():
    state = secrets.token_urlsafe(16)
    _pending_states.add(state)
    params = {
        "client_id": config.GOOGLE_CLIENT_ID,
        "redirect_uri": config.GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "prompt": "select_account",
    }
    return AUTH_URL + "?" + urllib.parse.urlencode(params)


def handle_callback(code, state):
    """Code ko token se exchange karke Google se user profile le aao."""
    if state not in _pending_states:
        return None
    _pending_states.discard(state)

    body = urllib.parse.urlencode({
        "code": code,
        "client_id": config.GOOGLE_CLIENT_ID,
        "client_secret": config.GOOGLE_CLIENT_SECRET,
        "redirect_uri": config.GOOGLE_REDIRECT_URI,
        "grant_type": "authorization_code",
    }).encode()
    req = urllib.request.Request(TOKEN_URL, data=body, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            tok = json.loads(r.read().decode())
    except Exception as e:
        print("Google token exchange failed:", e)
        return None

    access_token = tok.get("access_token")
    if not access_token:
        return None

    req2 = urllib.request.Request(USERINFO_URL, headers={"Authorization": f"Bearer {access_token}"})
    try:
        with urllib.request.urlopen(req2, timeout=10) as r:
            profile = json.loads(r.read().decode())
    except Exception as e:
        print("Google userinfo failed:", e)
        return None

    return {
        "email": profile.get("email"),
        "name": profile.get("name"),
        "picture": profile.get("picture", ""),
    }
