"""
Indexer: pages ke text se inverted index banata hai
(har word -> kis page mein kitni baar aaya) aur JSON mein save karta hai.
"""
import re
import json
import os
from collections import Counter

from app import config


def tokenize(text):
    return re.findall(r"\w+", text.lower())


def build_index(docs):
    inverted = {}
    for i, d in enumerate(docs):
        tokens = tokenize(d["title"] + " " + d["text"])
        d["len"] = len(tokens)
        for term, tf in Counter(tokens).items():
            inverted.setdefault(term, {})[i] = tf

    os.makedirs(config.DATA_DIR, exist_ok=True)
    with open(config.INDEX_FILE, "w", encoding="utf-8") as f:
        json.dump({"docs": docs, "index": inverted}, f)
