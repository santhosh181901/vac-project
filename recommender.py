"""Simple content-based recommender: ranks 'To Read' books using what the reader liked."""
from collections import defaultdict


def _tokens(book):
    kw = [k.strip() for k in (book.get("keywords") or "").split(",") if k.strip()]
    return set(kw)


def recommend(books, top_n=5):
    """Score each unread book by genre affinity, author affinity and keyword overlap
    with highly rated (4-5 star) completed books. Returns list of (book, score, reason)."""
    liked = [b for b in books if b["status"] == "Completed" and (b.get("rating") or 0) >= 4]
    queue = [b for b in books if b["status"] == "To Read"]
    if not queue:
        return []

    genre_w, author_w = defaultdict(float), defaultdict(float)
    liked_kw = defaultdict(float)
    for b in liked:
        w = (b["rating"] - 3) / 2  # 4 -> 0.5, 5 -> 1.0
        genre_w[b["genre"].lower()] += w
        author_w[b["author"].lower()] += w
        for k in _tokens(b):
            liked_kw[k] += w

    results = []
    for b in queue:
        g = genre_w.get(b["genre"].lower(), 0)
        a = author_w.get(b["author"].lower(), 0)
        overlap = sum(liked_kw.get(k, 0) for k in _tokens(b))
        short_bonus = 0.2 if 0 < (b.get("pages") or 0) <= 250 else 0  # easy wins keep momentum
        score = 2 * g + 1.5 * a + 0.5 * overlap + short_bonus
        reasons = []
        if g:
            reasons.append(f"you rate {b['genre']} highly")
        if a:
            reasons.append(f"you enjoyed {b['author']}")
        if overlap:
            reasons.append("similar themes to books you liked")
        if short_bonus:
            reasons.append("a quick read")
        results.append((b, round(score, 2), ", ".join(reasons) or "add ratings to personalise"))
    results.sort(key=lambda r: r[1], reverse=True)
    return results[:top_n]
