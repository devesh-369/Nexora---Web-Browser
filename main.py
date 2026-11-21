"""
NEXORA Search Engine
=====================
Use:
  python main.py crawl    -> websites crawl karke data/index.json banata hai
  python main.py serve    -> http://localhost:8000 pe search engine chalata hai

Poore internet ke live results ke liye (free key: brave.com/search/api):
  Windows : set BRAVE_API_KEY=apni_key
  Mac/Linux: export BRAVE_API_KEY=apni_key
"""
import sys

from app.crawler import crawl
from app.server import run as serve


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "crawl":
        crawl()
    elif cmd == "serve":
        serve()
    else:
        print(__doc__)
