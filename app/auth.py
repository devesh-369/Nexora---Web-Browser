"""
Auth: user accounts, sessions, password hashing, 2FA (TOTP), password reset.
Sab kuch standard library se — ek local JSON file database (data/users.json) mein store hota hai.

Note: ye ek college-project-grade local auth system hai (real security practices follow
karta hai — salted PBKDF2 hashing, random session tokens, TOTP), lekin production app
ke liye real database aur HTTPS chahiye hoga.
"""
import os
import json
import time
import hmac
import base64
import struct
import hashlib
import secrets
import threading

from app import config

_lock = threading.Lock()


def _load():
    if not os.path.exists(config.USERS_FILE):
        return {"users": {}, "sessions": {}, "reset_tokens": {}, "verify_tokens": {}}
    with open(config.USERS_FILE, encoding="utf-8") as f:
        return json.load(f)


def _save(data):
    os.makedirs(config.DATA_DIR, exist_ok=True)
    with open(config.USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


# ---------- password hashing (PBKDF2, stdlib only) ----------
def hash_password(password, salt=None):
    salt = salt or secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 200_000)
    return f"{salt}${dk.hex()}"


def verify_password(password, stored):
    salt, _ = stored.split("$")
    return hmac.compare_digest(hash_password(password, salt), stored)


# ---------- TOTP (RFC 6238) 2FA, stdlib only ----------
def new_totp_secret():
    return base64.b32encode(secrets.token_bytes(10)).decode().rstrip("=")


def _totp_code(secret, for_time=None, step=30, digits=6):
    key = base64.b32decode(secret + "=" * (-len(secret) % 8))
    counter = int((for_time or time.time()) // step)
    msg = struct.pack(">Q", counter)
    h = hmac.new(key, msg, hashlib.sha1).digest()
    offset = h[-1] & 0x0F
    code = (struct.unpack(">I", h[offset:offset + 4])[0] & 0x7FFFFFFF) % (10 ** digits)
    return str(code).zfill(digits)


def verify_totp(secret, code):
    # thoda clock drift allow karne ke liye pichla/agla window bhi check karo
    now = time.time()
    return any(_totp_code(secret, now + d) == code for d in (-30, 0, 30))


# ---------- users ----------
def get_user(email):
    data = _load()
    return data["users"].get(email.lower())


def create_user(email, password, name):
    email = email.lower()
    with _lock:
        data = _load()
        if email in data["users"]:
            return None, "Account already exists with this email."
        data["users"][email] = {
            "email": email,
            "name": name or email.split("@")[0],
            "password": hash_password(password),
            "provider": "password",
            "verified": False,
            "picture": "",
            "language": "English",
            "prefs": {"safe_search": True, "theme": "light", "accent": "blue"},
            "history": [],
            "bookmarks": [],
            "totp_secret": None,
            "totp_enabled": False,
            "login_activity": [],
            "created_at": time.time(),
        }
        _save(data)
        token = secrets.token_urlsafe(24)
        data = _load()
        data["verify_tokens"][token] = {"email": email, "created_at": time.time()}
        _save(data)
        return data["users"][email], token


def verify_email_token(token):
    with _lock:
        data = _load()
        info = data["verify_tokens"].pop(token, None)
        if not info:
            return False
        email = info["email"]
        if email in data["users"]:
            data["users"][email]["verified"] = True
            _save(data)
            return True
        _save(data)
        return False


def check_login(email, password):
    user = get_user(email)
    if not user or user["provider"] != "password":
        return None
    if not verify_password(password, user["password"]):
        return None
    return user


def google_login_or_create(google_profile):
    """Google OAuth se mile profile (email/name/picture) se user find ya create karo.
    Agar same email se pehle se password account hai, usi se link kar do (duplicate nahi banega)."""
    email = google_profile["email"].lower()
    with _lock:
        data = _load()
        if email not in data["users"]:
            data["users"][email] = {
                "email": email,
                "name": google_profile.get("name", email.split("@")[0]),
                "password": None,
                "provider": "google",
                "verified": True,
                "picture": google_profile.get("picture", ""),
                "language": "English",
                "prefs": {"safe_search": True, "theme": "light", "accent": "blue"},
                "history": [], "bookmarks": [],
                "totp_secret": None, "totp_enabled": False,
                "login_activity": [],
                "created_at": time.time(),
            }
        else:
            # existing account (password se bana hua ho sakta hai) ko google se link kar do
            data["users"][email]["provider"] = data["users"][email]["provider"] + "+google" \
                if "google" not in data["users"][email]["provider"] else data["users"][email]["provider"]
            data["users"][email]["picture"] = data["users"][email]["picture"] or google_profile.get("picture", "")
        _save(data)
        return data["users"][email]


def set_password_for_reset(email, new_password):
    with _lock:
        data = _load()
        if email in data["users"]:
            data["users"][email]["password"] = hash_password(new_password)
            if data["users"][email]["provider"] == "google":
                data["users"][email]["provider"] = "password+google"
            elif not data["users"][email]["provider"]:
                data["users"][email]["provider"] = "password"
            _save(data)
            return True
        return False


def create_reset_token(email):
    with _lock:
        data = _load()
        if email.lower() not in data["users"]:
            return None
        token = secrets.token_urlsafe(24)
        data["reset_tokens"][token] = {"email": email.lower(), "created_at": time.time()}
        _save(data)
        return token


def consume_reset_token(token):
    with _lock:
        data = _load()
        info = data["reset_tokens"].pop(token, None)
        _save(data)
        if not info or time.time() - info["created_at"] > 3600:
            return None
        return info["email"]


# ---------- sessions ----------
def create_session(email, device="Unknown device", ip="127.0.0.1"):
    with _lock:
        data = _load()
        token = secrets.token_urlsafe(32)
        data["sessions"][token] = {
            "email": email, "device": device, "ip": ip,
            "created_at": time.time(), "last_seen": time.time(),
        }
        data["users"][email]["login_activity"].insert(0, {
            "time": time.time(), "device": device, "ip": ip,
        })
        data["users"][email]["login_activity"] = data["users"][email]["login_activity"][:20]
        _save(data)
        return token


def get_session(token):
    data = _load()
    return data["sessions"].get(token)


def touch_session(token):
    with _lock:
        data = _load()
        if token in data["sessions"]:
            data["sessions"][token]["last_seen"] = time.time()
            _save(data)


def delete_session(token):
    with _lock:
        data = _load()
        data["sessions"].pop(token, None)
        _save(data)


def list_sessions(email):
    data = _load()
    return [(tok, s) for tok, s in data["sessions"].items() if s["email"] == email]


def delete_all_sessions(email, keep_token=None):
    with _lock:
        data = _load()
        data["sessions"] = {t: s for t, s in data["sessions"].items()
                             if s["email"] != email or t == keep_token}
        _save(data)


def current_user(token):
    sess = get_session(token) if token else None
    if not sess:
        return None
    return get_user(sess["email"])


# ---------- history / bookmarks / prefs ----------
def add_history(email, query, mode):
    with _lock:
        data = _load()
        if email not in data["users"]:
            return
        data["users"][email]["history"].insert(0, {"q": query, "mode": mode, "time": time.time()})
        data["users"][email]["history"] = data["users"][email]["history"][:50]
        _save(data)


def trending_searches(limit=5, since_hours=24 * 14):
    """Real trending queries — counted from everyone's search history,
    not hardcoded. Counts each query (case-insensitive) in the last
    `since_hours` hours across all accounts."""
    data = _load()
    cutoff = time.time() - since_hours * 3600
    counts = {}
    for u in data["users"].values():
        for h in u.get("history", []):
            if h.get("time", 0) < cutoff:
                continue
            key = h["q"].strip().lower()
            if not key:
                continue
            counts[key] = counts.get(key, 0) + 1
    ranked = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)[:limit]
    return [q for q, _ in ranked]


def add_bookmark(email, url, title):
    with _lock:
        data = _load()
        if email not in data["users"]:
            return
        bm = data["users"][email]["bookmarks"]
        if not any(b["url"] == url for b in bm):
            bm.insert(0, {"url": url, "title": title, "time": time.time()})
        _save(data)


def update_prefs(email, **kwargs):
    with _lock:
        data = _load()
        if email in data["users"]:
            data["users"][email]["prefs"].update(kwargs)
            _save(data)


def set_totp(email, secret, enabled):
    with _lock:
        data = _load()
        if email in data["users"]:
            data["users"][email]["totp_secret"] = secret
            data["users"][email]["totp_enabled"] = enabled
            _save(data)
