# NEXORA Search Engine

A full-featured college project search engine: web crawler, inverted index,
BM25 ranking, a Google-style UI with dark mode, voice search, multiple
search modes, and a real login system.

## Folder Structure
```
NEXORA/
├── main.py                 # entry point (run this)
├── app/
│   ├── config.py            # settings + API keys (edit this)
│   ├── crawler.py           # web crawler
│   ├── indexer.py           # builds inverted index
│   ├── ranker.py            # BM25 search/ranking
│   ├── server.py            # web server, routes, search modes
│   ├── auth.py              # login, sessions, password hashing, 2FA
│   ├── google_oauth.py      # Google OAuth 2.0 login
│   └── ai.py                # optional AI-powered modes
├── static/
│   ├── style.css            # all styling, dark mode + color themes
│   ├── theme.js              # theme switcher
│   ├── voice.js              # voice search + voice answer
│   └── weather.js            # free weather widget (Open-Meteo, no key)
├── templates/
│   └── page.html            # HTML page template
├── data/                     # generated at runtime (index.json, users.json)
├── README.md
└── NEXORA_Project_Report.md  # for presentation
```

## How to Run
1. Python 3, no extra packages needed (standard library only).
2. Open this folder in a terminal / VS Code terminal.
3. Build the search index (edit `app/config.py` to change which sites it crawls):
   ```
   python main.py crawl
   ```
4. Start the server:
   ```
   python main.py serve
   ```
5. Open `http://localhost:8000`.

## Features Included (work immediately, no setup)
- **Dashboard-style home page** — dark hero section, shortcut tiles, and widgets
- **Sidebar navigation** — Home, Bookmarks, History, Security, Help, plus
  Dark Mode switch and accent color, on every page
- **Web / My Index / Deep Search / Fact Check / Project Ideas / Ask AI** tabs
- **Voice Search** — click the mic in the search box and speak (Chrome recommended)
- **Voice Answer** — click "Listen" on a results page to hear the top result read aloud
- **Deep Search Mode** — runs several related queries and combines the results
- **Trending Searches widget** — real, built from everyone's search history
  (not hardcoded), so it starts empty and fills in as the app is used
- **Weather widget** — fully working, free, no API key (uses the browser's
  location + Open-Meteo); click "Show my local weather" on the home page
- **Login system** — Email+Password signup/login, Forgot/Reset password,
  Email verification, Profile page, Search history, Bookmarks
- **Security** — Active sessions, Logout from all devices, Login activity, real TOTP 2FA
- **Dark mode + 3 accent colors** — in the sidebar

> Password reset and email verification links are **shown in the server's
> terminal window** (printed as `[NEXORA] ...`) instead of being emailed,
> since no real email service (SMTP) is configured. This is normal for a
> local/offline project — see "Optional setup" below to send real emails.

## Optional Setup (free, you do this yourself — 5-10 minutes each)

### 1. Continue with Google (real OAuth 2.0 login)
1. Go to https://console.cloud.google.com/apis/credentials
2. "Create Credentials" → "OAuth client ID" → Application type: "Web application"
3. Add this Authorized redirect URI: `http://localhost:8000/auth/google/callback`
4. Copy the Client ID and Client Secret into `app/config.py`:
   ```python
   GOOGLE_CLIENT_ID = "your-client-id"
   GOOGLE_CLIENT_SECRET = "your-client-secret"
   ```
5. Restart the server. "Continue with Google" on the login page will now work.

### 2. AI-powered Fact-Check verdicts, Project Ideas & Ask AI
Without a key, Fact Check shows multiple sources (no automatic verdict),
Project Ideas shows plain web results, and the "Ask AI" tab / home page
assistant falls back to web results — all clearly labeled as such, nothing
is faked.
1. Get a key from https://console.anthropic.com
2. In `app/config.py`:
   ```python
   ANTHROPIC_API_KEY = "your-api-key"
   ```
3. Restart the server. Fact Check will now show a Supported/Contradicted/Unclear
   verdict, Project Ideas will show difficulty, concepts, GitHub/paper
   hints and use cases, and Ask AI will answer directly.

### 3. Live Web results from Brave Search (optional, improves on the free DuckDuckGo fallback)
Get a free key from https://brave.com/search/api, then set the
`BRAVE_API_KEY` environment variable before running `python main.py serve`.

### 4. Real email sending (for verification/reset emails)
Not wired up by default (no SMTP library used, to keep it dependency-free).
To add it: use Python's built-in `smtplib` in `app/auth.py` wherever the
code currently does `print(f"[NEXORA] ... link: {link}")`, pointing at your
email provider's SMTP server.

### 5. Multi-device Cloud Sync
Right now the server runs on `localhost`, so data only syncs across browser
tabs on this one computer. To make it truly reachable from other devices,
host `main.py` on a server with a public address (e.g. a cloud VM or a
platform like Render/Railway) — the same `data/users.json`-based storage
would then work as shared cloud storage for every device that logs in.

## Customization
In the sidebar, use the Dark mode switch and the 3 accent color dots
(Blue, Purple, Green). Saved in your browser automatically.
