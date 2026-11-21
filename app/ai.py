"""
AI module: agar ANTHROPIC_API_KEY config.py mein set hai, to ye Fact-Check
verdicts aur Project Ideas jaisa structured content generate karta hai.
Bina key ke, in modes ka honest "sources dikhao, verdict mat fake karo"
version chalega.
"""
import json
import urllib.request

from app import config


def is_available():
    return bool(config.ANTHROPIC_API_KEY)


def _call(prompt, max_tokens=1200):
    body = json.dumps({
        "model": config.ANTHROPIC_MODEL,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }).encode()
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=body,
        headers={
            "Content-Type": "application/json",
            "x-api-key": config.ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.loads(r.read().decode())
    return "".join(b.get("text", "") for b in data.get("content", []))


def ask(question):
    """General Q&A for the homepage AI Assistant widget. Returns text or None."""
    if not is_available():
        return None
    prompt = f"Answer the following question clearly and concisely (3-5 sentences):\n\n{question}"
    try:
        return _call(prompt, max_tokens=500).strip()
    except Exception as e:
        print("AI ask failed:", e)
        return None


def fact_check_verdict(claim, sources):
    """sources: list of (title, url, snippet). Returns dict or None on failure."""
    if not is_available():
        return None
    ctx = "\n".join(f"- {t}: {s}" for t, _, s in sources[:6])
    prompt = (
        f'Claim: "{claim}"\n\nSource snippets:\n{ctx}\n\n'
        'Based only on these snippets, classify the claim as one of: '
        '"Supported", "Contradicted", or "Unclear". '
        'Reply ONLY as JSON: {"verdict": "...", "reason": "one short sentence"}'
    )
    try:
        text = _call(prompt, max_tokens=200)
        text = text.strip().strip("`").replace("json\n", "")
        return json.loads(text)
    except Exception as e:
        print("AI fact-check failed:", e)
        return None


def project_ideas(topic, sources):
    """Returns list of idea dicts, or None on failure."""
    if not is_available():
        return None
    ctx = "\n".join(f"- {t}: {s}" for t, _, s in sources[:6])
    prompt = (
        f'Topic: "{topic}"\n\nContext from web search:\n{ctx}\n\n'
        'Suggest 5 project ideas related to this topic, suitable for a student. '
        'Reply ONLY as a JSON array, each item: '
        '{"title": "...", "difficulty": "Beginner|Intermediate|Advanced", '
        '"concepts": "key concepts/skills needed", "use_case": "real-world use case", '
        '"github_hint": "what to search on GitHub", "paper_hint": "what to search for research papers"}'
    )
    try:
        text = _call(prompt, max_tokens=1200)
        text = text.strip().strip("`").replace("json\n", "")
        return json.loads(text)
    except Exception as e:
        print("AI project-ideas failed:", e)
        return None
