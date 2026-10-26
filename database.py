"""SQLite storage layer for the AI Reading List and Book Summary Manager."""
import sqlite3
from datetime import date
from pathlib import Path

DB_PATH = Path(__file__).parent / "reading_list.db"
STATUSES = ["To Read", "Reading", "Completed"]

SCHEMA = """
CREATE TABLE IF NOT EXISTS books (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    title         TEXT NOT NULL,
    author        TEXT NOT NULL DEFAULT 'Unknown',
    genre         TEXT NOT NULL DEFAULT 'General',
    status        TEXT NOT NULL DEFAULT 'To Read',
    rating        INTEGER,
    pages         INTEGER DEFAULT 0,
    pages_read    INTEGER DEFAULT 0,
    notes         TEXT DEFAULT '',
    summary       TEXT DEFAULT '',
    takeaways     TEXT DEFAULT '',
    keywords      TEXT DEFAULT '',
    added_on      TEXT NOT NULL,
    finished_on   TEXT
);
"""


def get_conn(db_path=None):
    conn = sqlite3.connect(str(db_path or DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path=None):
    with get_conn(db_path) as conn:
        conn.executescript(SCHEMA)


def add_book(title, author="Unknown", genre="General", status="To Read",
             pages=0, notes="", db_path=None):
    title = (title or "").strip()
    if not title:
        raise ValueError("Title is required")
    if status not in STATUSES:
        raise ValueError(f"Status must be one of {STATUSES}")
    finished = date.today().isoformat() if status == "Completed" else None
    with get_conn(db_path) as conn:
        cur = conn.execute(
            "INSERT INTO books (title, author, genre, status, pages, notes, added_on, finished_on) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (title, author.strip() or "Unknown", genre.strip() or "General", status,
             int(pages or 0), notes, date.today().isoformat(), finished),
        )
        return cur.lastrowid


def get_book(book_id, db_path=None):
    with get_conn(db_path) as conn:
        row = conn.execute("SELECT * FROM books WHERE id=?", (book_id,)).fetchone()
        return dict(row) if row else None


def list_books(status=None, search=None, genre=None, db_path=None):
    query, params = "SELECT * FROM books WHERE 1=1", []
    if status and status != "All":
        query += " AND status=?"
        params.append(status)
    if genre and genre != "All":
        query += " AND genre=?"
        params.append(genre)
    if search:
        like = f"%{search.strip()}%"
        query += " AND (title LIKE ? OR author LIKE ? OR notes LIKE ? OR summary LIKE ? OR keywords LIKE ?)"
        params += [like] * 5
    query += " ORDER BY id DESC"
    with get_conn(db_path) as conn:
        return [dict(r) for r in conn.execute(query, params).fetchall()]


_ALLOWED = {"title", "author", "genre", "status", "rating", "pages", "pages_read",
            "notes", "summary", "takeaways", "keywords", "finished_on"}


def update_book(book_id, db_path=None, **fields):
    fields = {k: v for k, v in fields.items() if k in _ALLOWED}
    if not fields:
        return
    if "status" in fields:
        if fields["status"] not in STATUSES:
            raise ValueError(f"Status must be one of {STATUSES}")
        if fields["status"] == "Completed":
            fields.setdefault("finished_on", date.today().isoformat())
        else:
            fields.setdefault("finished_on", None)
    if "rating" in fields and fields["rating"] is not None:
        if not 1 <= int(fields["rating"]) <= 5:
            raise ValueError("Rating must be between 1 and 5")
    sets = ", ".join(f"{k}=?" for k in fields)
    with get_conn(db_path) as conn:
        conn.execute(f"UPDATE books SET {sets} WHERE id=?", [*fields.values(), book_id])


def delete_book(book_id, db_path=None):
    with get_conn(db_path) as conn:
        conn.execute("DELETE FROM books WHERE id=?", (book_id,))


def get_stats(db_path=None):
    books = list_books(db_path=db_path)
    done = [b for b in books if b["status"] == "Completed"]
    rated = [b["rating"] for b in done if b["rating"]]
    genres = {}
    for b in books:
        genres[b["genre"]] = genres.get(b["genre"], 0) + 1
    return {
        "total": len(books),
        "to_read": sum(b["status"] == "To Read" for b in books),
        "reading": sum(b["status"] == "Reading" for b in books),
        "completed": len(done),
        "avg_rating": round(sum(rated) / len(rated), 2) if rated else 0,
        "pages_read": sum((b["pages"] if b["status"] == "Completed" else b["pages_read"]) or 0 for b in books),
        "genres": genres,
        "summarized": sum(bool(b["summary"]) for b in books),
    }
