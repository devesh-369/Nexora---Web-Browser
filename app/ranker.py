"""
Ranker: BM25 algorithm se query ke hisaab se pages ko score aur sort karta hai.
BM25 TF-IDF ka improved version hai, jo modern search engines use karte hain.
"""
import json
import math

from app import config
from app.indexer import tokenize


class Engine:
    def __init__(self):
        with open(config.INDEX_FILE, encoding="utf-8") as f:
            data = json.load(f)
        self.docs = data["docs"]
        self.index = data["index"]
        self.avg = sum(d["len"] for d in self.docs) / max(len(self.docs), 1)

    def search(self, query, k=10):
        N = len(self.docs)
        scores = {}
        terms = tokenize(query)
        for t in terms:
            post = self.index.get(t, {})
            idf = math.log(1 + (N - len(post) + 0.5) / (len(post) + 0.5))
            for di, tf in post.items():
                dl = self.docs[int(di)]["len"]
                s = idf * tf * 2.2 / (tf + 1.2 * (0.25 + 0.75 * dl / self.avg))
                scores[int(di)] = scores.get(int(di), 0) + s
        top = sorted(scores, key=scores.get, reverse=True)[:k]
        return [(self.docs[i], self.snippet(self.docs[i]["text"], terms)) for i in top]

    def snippet(self, text, terms):
        low = text.lower()
        pos = [low.find(t) for t in terms if low.find(t) >= 0]
        i = max(min(pos) - 80, 0) if pos else 0
        return "..." + text[i:i + 240] + "..."
