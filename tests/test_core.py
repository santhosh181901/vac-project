import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import database as db
from recommender import recommend
from summarizer import extract_keywords, extractive_summary, summarize

SAMPLE = (
    "Machine learning is a field of artificial intelligence that lets computers learn from data. "
    "Supervised learning uses labelled data to train models that predict outcomes. "
    "Unsupervised learning finds hidden patterns in data without labels. "
    "Deep learning uses neural networks with many layers to learn complex patterns. "
    "Models must be evaluated on unseen data to avoid overfitting. "
    "Good data quality matters more than model complexity in most real projects."
)


@pytest.fixture()
def path(tmp_path):
    p = tmp_path / "t.db"
    db.init_db(p)
    return p


def test_add_and_get(path):
    bid = db.add_book("Deep Work", "Cal Newport", "Self-Help", "To Read", 296, db_path=path)
    b = db.get_book(bid, path)
    assert b["title"] == "Deep Work" and b["status"] == "To Read" and b["finished_on"] is None


def test_title_required(path):
    with pytest.raises(ValueError):
        db.add_book("  ", db_path=path)


def test_invalid_status_and_rating(path):
    with pytest.raises(ValueError):
        db.add_book("X", status="Maybe", db_path=path)
    bid = db.add_book("X", db_path=path)
    with pytest.raises(ValueError):
        db.update_book(bid, db_path=path, rating=9)


def test_completed_sets_finish_date(path):
    bid = db.add_book("A", db_path=path)
    db.update_book(bid, db_path=path, status="Completed", rating=5)
    b = db.get_book(bid, path)
    assert b["finished_on"] and b["rating"] == 5


def test_search_filter_delete(path):
    a = db.add_book("Atomic Habits", "James Clear", "Self-Help", db_path=path)
    db.add_book("Dune", "Frank Herbert", "Fiction", db_path=path)
    assert len(db.list_books(search="habits", db_path=path)) == 1
    assert len(db.list_books(genre="Fiction", db_path=path)) == 1
    db.delete_book(a, path)
    assert len(db.list_books(db_path=path)) == 1


def test_stats(path):
    a = db.add_book("A", genre="Science", status="Completed", pages=100, db_path=path)
    db.update_book(a, db_path=path, rating=4)
    db.add_book("B", genre="Science", db_path=path)
    s = db.get_stats(path)
    assert s["total"] == 2 and s["completed"] == 1 and s["avg_rating"] == 4 and s["pages_read"] == 100


def test_extractive_summary_and_keywords():
    out = extractive_summary(SAMPLE, 2)
    assert 0 < len(out) < len(SAMPLE)
    assert "data" in extract_keywords(SAMPLE)


def test_summarize_offline_and_empty():
    r = summarize("ML Book", text=SAMPLE)
    assert r["summary"] and r["takeaways"] and r["method"].startswith("Offline")
    assert summarize("Nothing")["summary"] == ""


def test_summarize_falls_back_on_bad_key(monkeypatch):
    import summarizer
    def boom(*a, **k):
        raise RuntimeError("no network")
    monkeypatch.setattr(summarizer, "llm_summary", boom)
    r = summarize("ML Book", text=SAMPLE, provider="Mistral", api_key="bad")
    assert r["summary"] and "AI unavailable" in r["method"]


def test_recommender_prefers_liked_genre(path):
    a = db.add_book("Liked", "Auth", "Science", "Completed", db_path=path)
    db.update_book(a, db_path=path, rating=5)
    db.add_book("Sci next", "Other", "Science", db_path=path)
    db.add_book("Fic next", "Other", "Fiction", db_path=path)
    recs = recommend(db.list_books(db_path=path))
    assert recs[0][0]["title"] == "Sci next"
