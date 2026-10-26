"""AI summarization: LLM-based (Mistral / Groq) with an offline extractive fallback."""
import json
import math
import re
from collections import Counter

import requests

PROVIDERS = {
    "Mistral": {"url": "https://api.mistral.ai/v1/chat/completions", "model": "mistral-small-latest"},
    "Groq": {"url": "https://api.groq.com/openai/v1/chat/completions", "model": "llama-3.3-70b-versatile"},
}

STOPWORDS = set("""a about above after again all also am an and any are as at be because been before being below
between both but by can could did do does doing down during each few for from further had has have having he her
here hers him his how i if in into is it its just me more most my no nor not now of off on once only or other our
out over own same she should so some such than that the their them then there these they this those through to too
under until up very was we were what when where which while who whom why will with would you your""".split())


def _sentences(text):
    text = re.sub(r"\s+", " ", text or "").strip()
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9\"'])", text)
    return [p.strip() for p in parts if len(p.split()) >= 5]


def _words(text):
    return [w for w in re.findall(r"[a-zA-Z']{3,}", (text or "").lower()) if w not in STOPWORDS]


def extract_keywords(text, n=8):
    """Top-n keywords by term frequency."""
    counts = Counter(_words(text))
    return [w for w, _ in counts.most_common(n)]


def extractive_summary(text, n_sentences=4):
    """Rank sentences by normalised word-frequency score; return top ones in original order."""
    sents = _sentences(text)
    if len(sents) <= n_sentences:
        return " ".join(sents)
    freq = Counter(_words(text))
    top = max(freq.values()) if freq else 1
    scored = []
    for i, s in enumerate(sents):
        ws = _words(s)
        if not ws:
            continue
        score = sum(freq[w] / top for w in ws) / math.sqrt(len(ws))
        if i == 0:
            score *= 1.15  # opening sentences usually frame the topic
        scored.append((score, i, s))
    best = sorted(scored, reverse=True)[:n_sentences]
    return " ".join(s for _, _, s in sorted(best, key=lambda x: x[1]))


def extractive_takeaways(text, n=5):
    sents = _sentences(text)
    if not sents:
        return []
    picked = extractive_summary(text, n_sentences=min(n, len(sents)))
    return [s for s in _sentences(picked)][:n]


def _prompt(title, author, text):
    base = (
        "You are a helpful reading assistant. Produce a concise summary and key takeaways.\n"
        f"Book: {title} by {author}\n"
    )
    if text and text.strip():
        base += f"Use ONLY this source material:\n\"\"\"\n{text[:12000]}\n\"\"\"\n"
    else:
        base += ("No source text was provided; summarize from general knowledge. "
                 "If you do not know this book, say so instead of inventing details.\n")
    base += ('Respond ONLY with JSON: {"summary": "<=120 words", "takeaways": ["3 to 5 short bullets"], '
             '"keywords": ["5 to 8 single words"]}')
    return base


def llm_summary(title, author, text, provider, api_key, timeout=60):
    cfg = PROVIDERS[provider]
    resp = requests.post(
        cfg["url"],
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={"model": cfg["model"], "temperature": 0.3,
              "response_format": {"type": "json_object"},
              "messages": [{"role": "user", "content": _prompt(title, author, text)}]},
        timeout=timeout,
    )
    resp.raise_for_status()
    content = resp.json()["choices"][0]["message"]["content"]
    data = json.loads(content)
    return {
        "summary": str(data.get("summary", "")).strip(),
        "takeaways": [str(t).strip() for t in data.get("takeaways", [])][:5],
        "keywords": [str(k).strip().lower() for k in data.get("keywords", [])][:8],
    }


def summarize(title, author="Unknown", text="", provider=None, api_key=None, n_sentences=4):
    """Return dict(summary, takeaways, keywords, method). Falls back to offline mode on any failure."""
    note = ""
    if provider and api_key:
        try:
            out = llm_summary(title, author, text, provider, api_key)
            if out["summary"]:
                out["method"] = f"AI ({provider})"
                return out
        except Exception as exc:  # network, auth, bad JSON...
            note = f" (AI unavailable: {type(exc).__name__}; used offline mode)"
    if text and text.strip():
        return {
            "summary": extractive_summary(text, n_sentences),
            "takeaways": extractive_takeaways(text, 5),
            "keywords": extract_keywords(text, 8),
            "method": "Offline extractive" + note,
        }
    return {
        "summary": "", "takeaways": [], "keywords": [],
        "method": "No source text and no AI key" + note,
    }
