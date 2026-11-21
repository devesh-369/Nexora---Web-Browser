"""
NEXORA Settings
Yahan apni cheezein badal sakte ho.
"""
import os

# Yahan apni websites daalo (jo crawl karni hain)
SEEDS = [
    "https://en.wikipedia.org/wiki/Search_engine",
    "https://en.wikipedia.org/wiki/Information_retrieval",
]

MAX_PAGES = 50          # kitne pages crawl karne hain
DELAY = 1.0             # har request ke beech wait (seconds)
STAY_ON_DOMAIN = True   # sirf seed wali website ke andar rehna

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
STATIC_DIR = os.path.join(BASE_DIR, "static")
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
INDEX_FILE = os.path.join(DATA_DIR, "index.json")

UA = "NEXORABot/1.0 (college project)"
PORT = 8000

# Web (poore internet) ke results ke liye, free key: https://brave.com/search/api
BRAVE_API_KEY = os.environ.get("BRAVE_API_KEY", "")

USERS_FILE = os.path.join(DATA_DIR, "users.json")

# --- Login system ---
# Cookies session ke liye (koi setup nahi chahiye, already kaam karta hai)
COOKIE_NAME = "nexora_session"

# --- Google Login (OAuth 2.0) ---
# console.cloud.google.com/apis/credentials se free Client ID/Secret lo
# Redirect URI waha pe daalo: http://localhost:8000/auth/google/callback
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")
GOOGLE_REDIRECT_URI = f"http://localhost:{PORT}/auth/google/callback"

# --- AI-powered modes (Fact Check verdict, Project Ideas) ---
# console.anthropic.com se free/paid API key lo (optional - bina key ke in
# modes ka basic/non-AI version chalega)
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = "claude-sonnet-4-6"
