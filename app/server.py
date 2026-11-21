"""
Server: NEXORA ka web server — search UI, login system, voice search,
deep search, fact-check mode, AI ask/project-ideas (optional key),
and a free (no-key) weather widget via Open-Meteo.
"""
import os
import re
import html
import json
import time
import http.cookies
import urllib.request
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer

from app import config, auth, ai, google_oauth
from app.ranker import Engine

with open(os.path.join(config.TEMPLATES_DIR, "page.html"), encoding="utf-8") as f:
    PAGE = f.read()

LOGO = '<a class="logo {c}" href="/">NEXORA</a>'
MIME = {".css": "text/css", ".js": "application/javascript"}

NAV_ITEMS = [
    ("home", "/", "&#8962;", "Home"),
    ("bookmarks", "/profile#bookmarks", "&#128278;", "Bookmarks"),
    ("history", "/profile#history", "&#128337;", "History"),
    ("security", "/security", "&#128274;", "Security"),
    ("help", "/search?q=NEXORA+help&mode=web", "&#10067;", "Help"),
]

SHORTCUTS = [
    ("/search?q=&mode=deep", "Deep Search", "DS", "#4285f4"),
    ("/search?q=&mode=factcheck", "Fact Check", "&#9989;", "#34a853"),
    ("/search?q=&mode=ideas", "Project Ideas", "&#128161;", "#fbbc05"),
    ("/profile#bookmarks", "Bookmarks", "&#128278;", "#ea4335"),
    ("/profile#history", "History", "&#128337;", "#8e44ec"),
    ("/security", "Security", "&#128274;", "#1e8e5a"),
]


# ---------------- small HTML helpers ----------------
def form(q, mode, placeholder="Search NEXORA"):
    mic = '<span class="mic" onclick="nxVoiceSearch()" title="Voice search">&#127908;</span>'
    return (f'<form action="/search" class="searchform"><input id="nx-q" name="q" '
            f'value="{html.escape(q, quote=True)}" placeholder="{placeholder}" autofocus>{mic}'
            f'<input type="hidden" name="mode" value="{mode}">'
            f'<button type="submit" title="Search">&#10148;</button></form>')


def mode_tabs(q, mode):
    tabs = [("web", "Web"), ("local", "My Index"), ("deep", "Deep Search"),
            ("factcheck", "Fact Check"), ("ideas", "Project Ideas"), ("ask", "Ask AI")]
    out = "".join(
        f'<a class="{"on" if mode == m else ""}" href="/search?q={urllib.parse.quote(q)}&mode={m}">{n}</a>'
        for m, n in tabs)
    return f'<div class="tabs">{out}</div>'


GOOGLE_ICON = ('<svg viewBox="0 0 48 48"><path fill="#FFC107" d="M43.6 20.5H42V20H24v8h11.3C33.7 32.9 29.3 36 24 36c-6.6 0-12-5.4-12-12s5.4-12 12-12c3.1 0 5.8 1.1 8 3l5.7-5.7C34.6 6 29.6 4 24 4 12.9 4 4 12.9 4 24s8.9 20 20 20 20-8.9 20-20c0-1.3-.1-2.7-.4-3.5z"/>'
                '<path fill="#FF3D00" d="M6.3 14.7l6.6 4.8C14.5 15.9 18.9 13 24 13c3.1 0 5.8 1.1 8 3l5.7-5.7C34.6 6 29.6 4 24 4 16.3 4 9.7 8.3 6.3 14.7z"/>'
                '<path fill="#4CAF50" d="M24 44c5.5 0 10.4-1.9 14.2-5.1l-6.6-5.6C29.6 35 26.9 36 24 36c-5.3 0-9.7-3.1-11.3-7.6l-6.5 5C9.6 39.6 16.3 44 24 44z"/>'
                '<path fill="#1976D2" d="M43.6 20.5H42V20H24v8h11.3c-.8 2.3-2.3 4.2-4.3 5.4l6.6 5.6C40.9 36.6 44 30.9 44 24c0-1.3-.1-2.7-.4-3.5z"/></svg>')


def google_btn():
    return f'<a class="google-btn" href="/auth/google">{GOOGLE_ICON} Continue with Google</a>'


def sidebar_html(user, active=""):
    nav = "".join(
        f'<a href="{href}" class="{"active" if key == active else ""}">'
        f'<span class="icon">{icon}</span><span>{label}</span></a>'
        for key, href, icon, label in NAV_ITEMS)

    theme_row = (
        '<div class="sidebar-darkrow"><span>Dark mode</span>'
        '<label class="switch"><input type="checkbox" id="nx-darkswitch" '
        'onchange="nxToggleDark(this.checked)"><span class="track"></span></label></div>'
        '<div class="sidebar-dots">'
        '<div class="dot blue" id="nx-blue" onclick="nxSet(\'accent\',\'blue\')"></div>'
        '<div class="dot purple" id="nx-purple" onclick="nxSet(\'accent\',\'purple\')"></div>'
        '<div class="dot green" id="nx-green" onclick="nxSet(\'accent\',\'green\')"></div>'
        '</div>'
    )

    if user:
        pic = (f'<img class="avatar" src="{html.escape(user["picture"])}">' if user.get("picture")
               else f'<span class="avatar-fallback">{html.escape(user["name"][:1].upper())}</span>')
        user_row = (f'<a class="sidebar-user" href="/profile">{pic}'
                     f'<div><div class="name">{html.escape(user["name"])}</div>'
                     f'<div class="sub">Logout</div></div></a>')
        user_row = (f'<a class="sidebar-user" href="/profile">{pic}'
                     f'<div><div class="name">{html.escape(user["name"])}</div>'
                     f'<div class="sub">{html.escape(user["email"][:22])}</div></div></a>'
                     f'<a class="authlink" style="justify-content:center" href="/logout">Logout</a>')
    else:
        user_row = '<a class="authlink primary" style="justify-content:center" href="/login">Login</a>'

    return (f'<a class="sidebar-brand" href="/"><span class="sidebar-mark">N</span>'
            f'<span class="word">NEXORA</span></a>'
            f'<nav class="sidebar-nav">{nav}</nav>'
            f'<div class="sidebar-bottom">{theme_row}{user_row}</div>')


# ---------------- search backends ----------------
def brave_search(q, k=10):
    if not config.BRAVE_API_KEY:
        return None
    url = "https://api.search.brave.com/res/v1/web/search?" + urllib.parse.urlencode({"q": q, "count": k})
    req = urllib.request.Request(url, headers={
        "X-Subscription-Token": config.BRAVE_API_KEY,
        "Accept": "application/json", "User-Agent": config.UA,
    })
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read().decode("utf-8"))
    except Exception as e:
        print("Brave error:", e)
        return None
    strip = lambda s: re.sub(r"<[^>]+>", "", s or "")
    return [({"url": x["url"], "title": strip(x.get("title"))}, strip(x.get("description")))
            for x in data.get("web", {}).get("results", [])]


DDG_RESULT_RE = re.compile(
    r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>.*?class="result__snippet"[^>]*>(.*?)</a>',
    re.S,
)


def duckduckgo_search(q, k=10):
    url = "https://html.duckduckgo.com/html/?" + urllib.parse.urlencode({"q": q})
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    })
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            raw = r.read().decode("utf-8", errors="ignore")
    except Exception as e:
        print("DuckDuckGo error:", e)
        return []
    strip = lambda s: html.unescape(re.sub(r"<[^>]+>", "", s or "")).strip()
    results = []
    for href, title_html, snippet_html in DDG_RESULT_RE.findall(raw):
        href = html.unescape(href)
        parsed = urllib.parse.urlparse(href)
        real_url = href
        if parsed.netloc.endswith("duckduckgo.com"):
            uddg = urllib.parse.parse_qs(parsed.query).get("uddg")
            if uddg:
                real_url = urllib.parse.unquote(uddg[0])
        results.append(({"url": real_url, "title": strip(title_html)}, strip(snippet_html)))
        if len(results) >= k:
            break
    return results


def web_search(q, k=10):
    res = brave_search(q, k)
    return res if res is not None else duckduckgo_search(q, k)


def render_results_list(res):
    return "".join(
        f'<div class="item"><div class="u">{html.escape(d["url"])}</div>'
        f'<a class="t" href="{html.escape(d["url"])}">{html.escape(d["title"])}</a>'
        f'<div class="s">{html.escape(s)}</div>'
        f'<a class="bm" href="/bookmark?url={urllib.parse.quote(d["url"])}&title={urllib.parse.quote(d["title"])}">'
        f'&#128278; Save</a></div>' for d, s in res)


# ---------------- special modes ----------------
def deep_search(q):
    angles = [("Overview", q), ("How it works / explained", f"{q} explained"),
              ("Examples & tutorials", f"{q} examples tutorial"),
              ("Pros, cons & alternatives", f"{q} pros cons alternatives")]
    sections = []
    for label, query in angles:
        res = web_search(query, k=4)
        if res:
            sections.append(f'<h3 class="deep-h">{html.escape(label)}</h3>' + render_results_list(res))
    return ('<div class="note">Deep Search runs several related queries and combines '
            'the results below, organized by angle.</div>' + "".join(sections)) if sections else \
        "<p>No results found.</p>"


def fact_check(q):
    sources = []
    for d, s in web_search(q, k=6):
        sources.append((d["title"], d["url"], s))
    verdict = ai.fact_check_verdict(q, sources)
    out = ""
    if verdict:
        cls = {"Supported": "v-good", "Contradicted": "v-bad"}.get(verdict.get("verdict"), "v-mid")
        out += (f'<div class="verdict {cls}">AI Verdict: <b>{html.escape(verdict.get("verdict", "Unclear"))}</b>'
                f'<div class="s">{html.escape(verdict.get("reason", ""))}</div></div>')
    else:
        out += ('<div class="note">Automatic verdicts need an AI key (see README). '
                'Here is what multiple sources say — read them and judge for yourself:</div>')
    out += "".join(
        f'<div class="item"><div class="u">{html.escape(u)}</div>'
        f'<div class="t" style="color:var(--text);font-size:18px">{html.escape(t)}</div>'
        f'<div class="s">{html.escape(s)}</div></div>' for t, u, s in sources)
    return out or "<p>No sources found.</p>"


def project_ideas_mode(q):
    sources = [(d["title"], d["url"], s) for d, s in web_search(q, k=6)]
    ideas = ai.project_ideas(q, sources)
    if not ideas:
        note = ('<div class="note">AI project-idea generation needs an API key '
                '(ANTHROPIC_API_KEY in app/config.py). Meanwhile, here are related resources:</div>')
        return note + render_results_list([(d, s) for d, s in web_search(q, k=8)])
    out = ""
    for idea in ideas:
        out += (f'<div class="idea-card"><h3>{html.escape(idea.get("title", ""))}</h3>'
                f'<div class="idea-row">📊 <b>Difficulty:</b> {html.escape(idea.get("difficulty", "-"))}</div>'
                f'<div class="idea-row">🧠 <b>Concepts:</b> {html.escape(idea.get("concepts", "-"))}</div>'
                f'<div class="idea-row">💰 <b>Use case:</b> {html.escape(idea.get("use_case", "-"))}</div>'
                f'<div class="idea-row">💻 <b>GitHub:</b> {html.escape(idea.get("github_hint", "-"))}</div>'
                f'<div class="idea-row">📚 <b>Papers:</b> {html.escape(idea.get("paper_hint", "-"))}</div></div>')
    return out


def ask_mode(q):
    if not ai.is_available():
        return ('<div class="note">The AI Assistant needs an API key '
                '(ANTHROPIC_API_KEY in app/config.py). Showing web results instead:</div>'
                + (render_results_list(web_search(q, k=6)) or "<p>No results found.</p>"))
    answer = ai.ask(q)
    if not answer:
        return '<div class="note">The AI Assistant could not answer right now — please try again.</div>'
    return (f'<div class="idea-card"><div class="s" style="font-size:15px;line-height:1.75;color:var(--text)">'
            f'{html.escape(answer)}</div></div>')


# ---------------- weather (Open-Meteo, free, no API key) ----------------
WEATHER_CODES = {
    0: "Clear sky", 1: "Mostly clear", 2: "Partly cloudy", 3: "Overcast",
    45: "Fog", 48: "Depositing rime fog",
    51: "Light drizzle", 53: "Drizzle", 55: "Dense drizzle",
    61: "Light rain", 63: "Rain", 65: "Heavy rain",
    71: "Light snow", 73: "Snow", 75: "Heavy snow",
    80: "Rain showers", 81: "Rain showers", 82: "Violent rain showers",
    95: "Thunderstorm", 96: "Thunderstorm with hail",
}


def fetch_weather(lat, lon):
    try:
        url = ("https://api.open-meteo.com/v1/forecast?"
               + urllib.parse.urlencode({"latitude": lat, "longitude": lon,
                                          "current": "temperature_2m,weather_code"}))
        with urllib.request.urlopen(url, timeout=8) as r:
            data = json.loads(r.read().decode())
        cur = data.get("current", {})
        temp, code = cur.get("temperature_2m"), cur.get("weather_code")
    except Exception as e:
        print("Weather fetch failed:", e)
        return {"error": "Couldn't fetch weather (check your internet connection)."}

    city = "Your location"
    try:
        geo_url = ("https://api.bigdatacloud.net/data/reverse-geocode-client?"
                   + urllib.parse.urlencode({"latitude": lat, "longitude": lon, "localityLanguage": "en"}))
        with urllib.request.urlopen(geo_url, timeout=8) as r:
            geo = json.loads(r.read().decode())
        city = geo.get("city") or geo.get("locality") or city
    except Exception as e:
        print("Reverse geocode failed:", e)

    return {"temp": round(temp) if temp is not None else "-",
            "condition": WEATHER_CODES.get(code, "—"), "city": city}


# ---------------- auth page template ----------------
def field_html(f):
    name, ftype, placeholder = f
    if ftype == "password":
        return (f'<div class="pwrow"><input name="{name}" type="password" id="pw-{name}" '
                f'placeholder="{placeholder}" required>'
                f'<button type="button" class="pwtoggle" onclick="nxTogglePw(\'pw-{name}\')">Show</button></div>')
    if ftype == "hidden":
        return f'<input name="{name}" type="hidden" value="">'
    return f'<input name="{name}" type="{ftype}" placeholder="{placeholder}" required>'


def auth_form_page(title, sub, fields, action, submit_label, footer_links, error="", show_google=True):
    rows = "".join(field_html(f) for f in fields)
    err = f'<div class="note">{html.escape(error)}</div>' if error else ""
    google = (f'<div class="divider">or</div>{google_btn()}' if show_google else "")
    pane = (f'<div class="authpane"><a class="logo" href="/">NEXORA</a>'
            f'<h2>{html.escape(title)}</h2><div class="sub">{html.escape(sub)}</div>{err}'
            f'<form method="POST" action="{action}" class="authform">{rows}'
            f'<button class="authsubmit" type="submit">{html.escape(submit_label)}</button></form>'
            f'{google}<div class="authfoot">{footer_links}</div></div>')
    return f'<div class="authwrap"><div class="authbox"><div class="authring"></div>{pane}</div></div>'


def auth_message_page(message, link_href, link_text):
    pane = (f'<div class="authpane"><a class="logo" href="/">NEXORA</a><p>{message}</p>'
            f'<a class="authlink primary" style="justify-content:center;display:flex" '
            f'href="{link_href}">{link_text}</a></div>')
    return f'<div class="authwrap"><div class="authbox"><div class="authring"></div>{pane}</div></div>'


# ---------------- HTTP handler ----------------
class Handler(BaseHTTPRequestHandler):
    engine = None

    def get_user(self):
        cookie_header = self.headers.get("Cookie", "")
        c = http.cookies.SimpleCookie()
        c.load(cookie_header)
        if config.COOKIE_NAME not in c:
            return None, None
        token = c[config.COOKIE_NAME].value
        user = auth.current_user(token)
        if user:
            auth.touch_session(token)
        return user, token

    def set_cookie(self, token):
        self.send_header("Set-Cookie", f"{config.COOKIE_NAME}={token}; Path=/; HttpOnly; SameSite=Lax")

    def clear_cookie(self):
        self.send_header("Set-Cookie", f"{config.COOKIE_NAME}=; Path=/; Max-Age=0")

    def read_form(self):
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length).decode()
        return {k: v[0] for k, v in urllib.parse.parse_qs(raw).items()}

    def redirect(self, location, cookie_token=None, clear=False):
        self.send_response(303)
        self.send_header("Location", location)
        if cookie_token:
            self.set_cookie(cookie_token)
        if clear:
            self.clear_cookie()
        self.end_headers()

    def send_page(self, title, body, active=""):
        user, _ = self.get_user()
        data = (PAGE.replace("{{TITLE}}", html.escape(title))
                .replace("{{SIDEBAR}}", sidebar_html(user, active))
                .replace("{{BODY}}", body)).encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(data)

    def send_json(self, obj):
        data = json.dumps(obj).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *a):
        pass

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        user, token = self.get_user()

        if path.startswith("/static/"):
            return self.serve_static()
        if path in ("/", ""):
            return self.render_home(user)
        if path == "/search":
            return self.render_search(qs, user)
        if path == "/weather":
            try:
                lat, lon = float(qs.get("lat", ["0"])[0]), float(qs.get("lon", ["0"])[0])
            except ValueError:
                return self.send_json({"error": "Invalid location."})
            return self.send_json(fetch_weather(lat, lon))
        if path == "/login":
            return self.send_page("Login - NEXORA", self.login_body())
        if path == "/register":
            return self.send_page("Sign up - NEXORA", self.register_body())
        if path == "/forgot":
            return self.send_page("Reset password - NEXORA", self.forgot_body())
        if path == "/reset":
            return self.send_page("Set new password - NEXORA", self.reset_body(qs.get("token", [""])[0]))
        if path == "/verify":
            ok = auth.verify_email_token(qs.get("token", [""])[0])
            msg = "Your email is verified! You can log in now." if ok else "Invalid or expired verification link."
            return self.send_page("Verify - NEXORA", auth_message_page(msg, "/login", "Go to Login"))
        if path == "/logout":
            auth.delete_session(token)
            return self.redirect("/", clear=True)
        if path == "/logout-all":
            if user:
                auth.delete_all_sessions(user["email"])
            return self.redirect("/security", clear=True)
        if path == "/profile":
            if not user:
                return self.redirect("/login")
            return self.send_page("Profile - NEXORA", self.profile_body(user), active="bookmarks")
        if path == "/security":
            if not user:
                return self.redirect("/login")
            return self.send_page("Security - NEXORA", self.security_body(user, token), active="security")
        if path == "/bookmark":
            if user:
                auth.add_bookmark(user["email"], qs.get("url", [""])[0], qs.get("title", [""])[0])
            ref = self.headers.get("Referer", "/")
            return self.redirect(ref)
        if path == "/auth/google":
            if not google_oauth.is_configured():
                return self.send_page("Google Login - NEXORA", auth_message_page(
                    "Google login isn't configured yet. Add GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET "
                    "in app/config.py (see README for steps).", "/login", "Back to Login"))
            return self.redirect(google_oauth.login_url())
        if path == "/auth/google/callback":
            return self.handle_google_callback(qs)

        self.send_response(404)
        self.end_headers()

    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path
        fields = self.read_form()
        user, token = self.get_user()

        if path == "/register":
            return self.handle_register(fields, user)
        if path == "/login":
            return self.handle_login(fields)
        if path == "/forgot":
            return self.handle_forgot(fields)
        if path == "/reset":
            return self.handle_reset(fields)
        if path == "/profile":
            return self.handle_profile_update(fields, user)
        if path == "/security/2fa/setup":
            return self.handle_2fa_setup(user)
        if path == "/security/2fa/verify":
            return self.handle_2fa_verify(fields, user)
        if path == "/security/2fa/disable":
            if user:
                auth.set_totp(user["email"], None, False)
            return self.redirect("/security")

        self.send_response(404)
        self.end_headers()

    def render_home(self, user):
        shortcuts = "".join(
            f'<a class="shortcut" href="{href}"><span class="sicon" style="background:{color}">{icon}</span>'
            f'<span>{label}</span></a>' for href, label, icon, color in SHORTCUTS)

        trending = auth.trending_searches(limit=5)
        if trending:
            trend_html = "".join(
                f'<li><span class="num">{i + 1}</span>'
                f'<a href="/search?q={urllib.parse.quote(t)}&mode=web">{html.escape(t)}</a></li>'
                for i, t in enumerate(trending))
        else:
            trend_html = '<div class="trend-empty">No trends yet — be the first to search!</div>'

        if ai.is_available():
            ask_widget = (f'<form class="ask-box" action="/search">'
                          f'<input type="hidden" name="mode" value="ask">'
                          f'<input name="q" placeholder="Ask me anything...">'
                          f'<button type="submit">&#10148;</button></form>')
        else:
            ask_widget = ('<div class="ask-note">Add ANTHROPIC_API_KEY in app/config.py to enable the '
                          'AI Assistant (see README). Falls back to web results until then.</div>'
                          f'<form class="ask-box" action="/search" style="margin-top:10px">'
                          f'<input type="hidden" name="mode" value="ask">'
                          f'<input name="q" placeholder="Ask me anything...">'
                          f'<button type="submit">&#10148;</button></form>')

        body = (
            '<div class="home-hero"><div class="home-glow"></div>'
            '<div class="home-content">'
            '<a class="logo xl" href="/">NEXORA</a>'
            '<div class="home-tagline">Search Smarter. Explore More.</div>'
            f'{form("", "web", placeholder="Search anything on NEXORA...")}'
            f'<div class="shortcuts">{shortcuts}</div>'
            '<div class="widgets">'
            f'<div class="widget"><h4>&#128200; Trending Searches</h4><ul class="trend-list">{trend_html}</ul></div>'
            f'<div class="widget"><h4>&#10024; NEXORA AI Assistant</h4>{ask_widget}</div>'
            '<div class="widget" id="weather-widget"><h4>&#127780; Weather</h4>'
            '<div id="weather-body"><button class="authsubmit" style="padding:9px 14px;font-size:12px;width:auto" '
            'onclick="nxGetWeather()">Show my local weather</button>'
            '<div class="ask-note">Uses your browser location (Open-Meteo, free) — nothing is stored.</div></div></div>'
            '</div></div></div>'
        )
        self.send_page("NEXORA", body, active="home")

    def render_search(self, qs, user):
        q = qs.get("q", [""])[0].strip()
        mode = qs.get("mode", ["web"])[0]
        if not q:
            return self.render_home(user)

        t0, note, res, custom = time.time(), "", None, None
        if mode == "web":
            res = web_search(q)
            if not res:
                note = "Couldn't fetch web results (check your internet connection) — try 'My Index'."
        elif mode == "local":
            res = self.engine.search(q) if self.engine else []
            if not self.engine:
                note = "index.json not found. Run 'python main.py crawl' first."
        elif mode == "deep":
            custom = deep_search(q)
        elif mode == "factcheck":
            custom = fact_check(q)
        elif mode == "ideas":
            custom = project_ideas_mode(q)
        elif mode == "ask":
            custom = ask_mode(q)
        else:
            res = []

        if user:
            auth.add_history(user["email"], q, mode)

        count_line = "" if custom is not None else \
            (f'<div class="st">About {len(res or [])} results ({time.time() - t0:.2f} seconds) '
             f'<button class="listen-btn" onclick="nxSpeakTop()">&#128266; Listen</button></div>')
        body_items = custom if custom is not None else \
            ((f'<div class="note">{note}</div><br>' if note else "") + (render_results_list(res) or "<p>No results found.</p>"))

        inner = (f'<div class="top">{form(q, mode)}</div>'
                 + mode_tabs(q, mode) + f'<div class="res">{count_line}{body_items}</div>')
        self.send_page(q + " - NEXORA", inner, active="")

    def login_body(self):
        return auth_form_page(
            "Welcome back", "Login to continue to NEXORA",
            [("email", "email", "Email"), ("password", "password", "Password")],
            "/login", "Login",
            '<a href="/register">Create account</a> · <a href="/forgot">Forgot password?</a>')

    def register_body(self):
        return auth_form_page(
            "Create your account", "It only takes a minute",
            [("name", "text", "Full name"), ("email", "email", "Email"), ("password", "password", "Password")],
            "/register", "Sign up",
            '<a href="/login">Already have an account? Login</a>')

    def forgot_body(self):
        return auth_form_page(
            "Reset your password", "We'll create a reset link for your account",
            [("email", "email", "Your account email")],
            "/forgot", "Send reset link", '<a href="/login">Back to Login</a>', show_google=False)

    def reset_body(self, token):
        return auth_form_page(
            "Set a new password", "Choose a new password for your account",
            [("token", "hidden", ""), ("password", "password", "New password")],
            "/reset", "Update password", '<a href="/login">Back to Login</a>', show_google=False
        ).replace('value=""', f'value="{html.escape(token)}"', 1)

    def profile_body(self, user):
        pic = (f'<img class="avatar-lg" src="{html.escape(user["picture"])}">' if user.get("picture")
               else f'<span class="avatar-lg-fallback">{html.escape(user["name"][:1].upper())}</span>')
        hist = "".join(f'<li>{html.escape(h["q"])} <span class="s">({html.escape(h["mode"])})</span></li>'
                        for h in user["history"][:10]) or "<li class='s'>No searches yet</li>"
        bms = "".join(f'<li><a href="{html.escape(b["url"])}">{html.escape(b["title"])}</a></li>'
                       for b in user["bookmarks"][:10]) or "<li class='s'>No bookmarks yet</li>"
        return (f'<div class="profilewrap"><div class="profilecard">{pic}'
                f'<h2>{html.escape(user["name"])}</h2><div class="s">{html.escape(user["email"])}</div>'
                f'<div class="s">Signed in via: {html.escape(user["provider"])} '
                f'{"&#10003; verified" if user["verified"] else "&#9888; not verified"}</div>'
                f'<form method="POST" action="/profile" class="authform" style="margin-top:18px">'
                f'<input name="name" value="{html.escape(user["name"])}" placeholder="Name">'
                f'<select name="language"><option {"selected" if user["language"] == "English" else ""}>English</option>'
                f'<option {"selected" if user["language"] == "Hindi" else ""}>Hindi</option></select>'
                f'<button class="authsubmit" type="submit">Save profile</button></form>'
                f'</div>'
                f'<div class="profilecard" id="bookmarks"><h3>Bookmarks</h3><ul class="plainlist">{bms}</ul></div>'
                f'<div class="profilecard" id="history"><h3>Recent searches</h3><ul class="plainlist">{hist}</ul></div></div>')

    def security_body(self, user, current_token):
        sessions = auth.list_sessions(user["email"])
        sess_rows = "".join(
            f'<li>{html.escape(s["device"])} — {html.escape(s["ip"])} '
            f'<span class="s">last seen {time.strftime("%d %b %H:%M", time.localtime(s["last_seen"]))}</span>'
            f'{" <b>(this device)</b>" if tok == current_token else ""}</li>' for tok, s in sessions)
        activity = "".join(
            f'<li>{time.strftime("%d %b %Y, %H:%M", time.localtime(a["time"]))} — {html.escape(a["device"])}</li>'
            for a in user["login_activity"][:10]) or "<li class='s'>No activity yet</li>"
        twofa = user.get("totp_enabled")
        twofa_block = (
            '<div class="s">2FA is <b>enabled</b> on your account.</div>'
            '<form method="POST" action="/security/2fa/disable"><button class="authsubmit" type="submit">Disable 2FA</button></form>'
            if twofa else
            '<div class="s">2FA is currently off.</div>'
            '<form method="POST" action="/security/2fa/setup"><button class="authsubmit" type="submit">Set up 2FA</button></form>'
        )
        return (f'<div class="profilewrap">'
                f'<div class="profilecard"><h3>Two-Factor Authentication</h3>{twofa_block}</div>'
                f'<div class="profilecard"><h3>Active sessions</h3><ul class="plainlist">{sess_rows}</ul>'
                f'<a class="authlink primary" href="/logout-all">Logout from all devices</a></div>'
                f'<div class="profilecard"><h3>Login activity</h3><ul class="plainlist">{activity}</ul></div>'
                f'</div>')

    def handle_register(self, fields, user):
        name, email, password = fields.get("name", ""), fields.get("email", ""), fields.get("password", "")
        if not email or not password:
            return self.send_page("Sign up - NEXORA", auth_form_page(
                "Create your account", "It only takes a minute",
                [("name", "text", "Full name"), ("email", "email", "Email"), ("password", "password", "Password")],
                "/register", "Sign up", '<a href="/login">Already have an account? Login</a>',
                error="Please fill all fields."))
        new_user, token_or_err = auth.create_user(email, password, name)
        if not new_user:
            return self.send_page("Sign up - NEXORA", auth_form_page(
                "Create your account", "It only takes a minute",
                [("name", "text", "Full name"), ("email", "email", "Email"), ("password", "password", "Password")],
                "/register", "Sign up", '<a href="/login">Already have an account? Login</a>',
                error=token_or_err))
        verify_link = f"http://localhost:{config.PORT}/verify?token={token_or_err}"
        print(f"[NEXORA] Verification link for {email}: {verify_link}")
        session_token = auth.create_session(email.lower(), device=self.headers.get("User-Agent", "Unknown")[:60],
                                             ip=self.client_address[0])
        self.send_response(303)
        self.send_header("Location", "/profile")
        self.set_cookie(session_token)
        self.end_headers()

    def handle_login(self, fields):
        email, password = fields.get("email", ""), fields.get("password", "")
        u = auth.check_login(email, password)
        if not u:
            return self.send_page("Login - NEXORA", auth_form_page(
                "Welcome back", "Login to continue to NEXORA",
                [("email", "email", "Email"), ("password", "password", "Password")],
                "/login", "Login", '<a href="/register">Create account</a>',
                error="Incorrect email or password."))
        session_token = auth.create_session(email.lower(), device=self.headers.get("User-Agent", "Unknown")[:60],
                                             ip=self.client_address[0])
        self.send_response(303)
        self.send_header("Location", "/profile")
        self.set_cookie(session_token)
        self.end_headers()

    def handle_forgot(self, fields):
        email = fields.get("email", "")
        token = auth.create_reset_token(email)
        if token:
            link = f"http://localhost:{config.PORT}/reset?token={token}"
            print(f"[NEXORA] Password reset link for {email}: {link}")
        msg = ('If that email exists, a reset link was created. '
               '(No real email service is configured — check the server terminal for the link.)')
        return self.send_page("Reset password - NEXORA", auth_message_page(msg, "/login", "Back to Login"))

    def handle_reset(self, fields):
        token, password = fields.get("token", ""), fields.get("password", "")
        email = auth.consume_reset_token(token)
        if not email or not password:
            return self.send_page("Reset password - NEXORA", auth_message_page(
                "This reset link is invalid or expired.", "/forgot", "Request a new link"))
        auth.set_password_for_reset(email, password)
        return self.send_page("Reset password - NEXORA", auth_message_page(
            "Password updated! You can log in now.", "/login", "Go to Login"))

    def handle_profile_update(self, fields, user):
        if not user:
            return self.redirect("/login")
        with auth._lock:
            data = auth._load()
            data["users"][user["email"]]["name"] = fields.get("name", user["name"])
            data["users"][user["email"]]["language"] = fields.get("language", user["language"])
            auth._save(data)
        return self.redirect("/profile")

    def handle_2fa_setup(self, user):
        if not user:
            return self.redirect("/login")
        secret = auth.new_totp_secret()
        auth.set_totp(user["email"], secret, False)
        body = (f'<div class="authwrap"><div class="authbox"><div class="authring"></div>'
                f'<div class="authpane"><a class="logo" href="/">NEXORA</a><h2>Set up 2FA</h2>'
                f'<p class="sub">Add this key to Google Authenticator (or any TOTP app) manually:</p>'
                f'<div class="totp-secret">{secret}</div>'
                f'<form method="POST" action="/security/2fa/verify" class="authform">'
                f'<input name="code" placeholder="Enter the 6-digit code">'
                f'<button class="authsubmit" type="submit">Verify &amp; enable</button></form>'
                f'<div class="authfoot"><a href="/security">Cancel</a></div></div></div></div>')
        return self.send_page("Set up 2FA - NEXORA", body, active="security")

    def handle_2fa_verify(self, fields, user):
        if not user:
            return self.redirect("/login")
        secret = user.get("totp_secret")
        code = fields.get("code", "")
        if secret and auth.verify_totp(secret, code):
            auth.set_totp(user["email"], secret, True)
        return self.redirect("/security")

    def handle_google_callback(self, qs):
        code, state = qs.get("code", [""])[0], qs.get("state", [""])[0]
        profile = google_oauth.handle_callback(code, state)
        if not profile or not profile.get("email"):
            return self.send_page("Google Login - NEXORA", auth_message_page(
                "Google login failed or was cancelled.", "/login", "Back to Login"))
        u = auth.google_login_or_create(profile)
        session_token = auth.create_session(u["email"], device=self.headers.get("User-Agent", "Unknown")[:60],
                                             ip=self.client_address[0])
        self.send_response(303)
        self.send_header("Location", "/profile")
        self.set_cookie(session_token)
        self.end_headers()

    def serve_static(self):
        rel = self.path[len("/static/"):].split("?")[0]
        path = os.path.join(config.STATIC_DIR, rel)
        ext = os.path.splitext(path)[1]
        if not os.path.abspath(path).startswith(os.path.abspath(config.STATIC_DIR)) or not os.path.isfile(path):
            self.send_response(404)
            self.end_headers()
            return
        with open(path, "rb") as f:
            data = f.read()
        self.send_response(200)
        self.send_header("Content-Type", MIME.get(ext, "application/octet-stream"))
        self.end_headers()
        self.wfile.write(data)


def run():
    try:
        Handler.engine = Engine()
    except FileNotFoundError:
        print("index.json not found (only the 'Web' tab will work)")
    print(f"Running at: http://localhost:{config.PORT}  (press Ctrl+C to stop)")
    HTTPServer(("", config.PORT), Handler).serve_forever()
