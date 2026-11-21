"""
Crawler: seed websites se shuru hoke links follow karta hai aur pages
download karta hai. robots.txt ki respect karta hai.
"""
import time
import urllib.request
import urllib.parse
import urllib.robotparser
from collections import deque
from html.parser import HTMLParser

from app import config
from app.indexer import build_index


class PageParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.title, self.text, self.links = "", [], []
        self.skip, self.in_title = 0, False

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript"):
            self.skip += 1
        elif tag == "title":
            self.in_title = True
        elif tag == "a":
            for k, v in attrs:
                if k == "href" and v:
                    self.links.append(v)

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript") and self.skip:
            self.skip -= 1
        elif tag == "title":
            self.in_title = False

    def handle_data(self, d):
        if self.skip:
            return
        if self.in_title:
            self.title += d
        else:
            self.text.append(d)


def crawl():
    queue = deque(config.SEEDS)
    seen = set(config.SEEDS)
    docs, robots = [], {}
    domains = {urllib.parse.urlparse(u).netloc for u in config.SEEDS}

    while queue and len(docs) < config.MAX_PAGES:
        url = queue.popleft()
        host = urllib.parse.urlparse(url).netloc

        if host not in robots:
            rp = urllib.robotparser.RobotFileParser(f"https://{host}/robots.txt")
            try:
                rp.read()
            except Exception:
                rp = None
            robots[host] = rp
        if robots[host] and not robots[host].can_fetch(config.UA, url):
            continue

        try:
            req = urllib.request.Request(url, headers={"User-Agent": config.UA})
            with urllib.request.urlopen(req, timeout=10) as r:
                if "text/html" not in r.headers.get("Content-Type", ""):
                    continue
                raw = r.read(2_000_000).decode("utf-8", errors="ignore")
        except Exception as e:
            print("skip", url, e)
            continue

        p = PageParser()
        p.feed(raw)
        text = " ".join(" ".join(p.text).split())
        docs.append({"url": url, "title": p.title.strip() or url, "text": text[:20000]})
        print(f"[{len(docs)}/{config.MAX_PAGES}] {url}")

        for link in p.links:
            link = urllib.parse.urldefrag(urllib.parse.urljoin(url, link))[0]
            u = urllib.parse.urlparse(link)
            if u.scheme not in ("http", "https") or link in seen:
                continue
            if config.STAY_ON_DOMAIN and u.netloc not in domains:
                continue
            seen.add(link)
            queue.append(link)

        time.sleep(config.DELAY)

    build_index(docs)
    print(f"Done! {len(docs)} pages index hue -> {config.INDEX_FILE}")
