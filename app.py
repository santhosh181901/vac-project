"""AI Reading List and Book Summary Manager - Streamlit app.

Run:  streamlit run app.py
"""
import io

import pandas as pd
import streamlit as st

import database as db
from recommender import recommend
from summarizer import PROVIDERS, summarize

st.set_page_config(page_title="AI Reading List Manager", page_icon="📚", layout="wide")
db.init_db()

STATUS_ICON = {"To Read": "📌", "Reading": "📖", "Completed": "✅"}
GENRES = ["Fiction", "Non-Fiction", "Science", "Technology", "AI & Data", "Self-Help",
          "Business", "History", "Biography", "Philosophy", "Fantasy", "Other"]


def stars(r):
    return "⭐" * int(r) if r else "—"


def read_upload(file):
    """Extract text from an uploaded .txt or .pdf file."""
    if file is None:
        return ""
    if file.name.lower().endswith(".pdf"):
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(file.read()))
        return "\n".join((p.extract_text() or "") for p in reader.pages)
    return file.read().decode("utf-8", errors="ignore")


# ------------------------------------------------------------------ sidebar
st.sidebar.title("📚 Reading Manager")
page = st.sidebar.radio("Navigate", ["Dashboard", "Add Book", "My Library", "Summary Studio", "Recommendations"])

st.sidebar.divider()
st.sidebar.subheader("🤖 AI Settings")
provider = st.sidebar.selectbox("AI provider", ["Offline (no key)"] + list(PROVIDERS))
api_key = ""
if provider != "Offline (no key)":
    api_key = st.sidebar.text_input(f"{provider} API key", type="password",
                                    help="Kept only in this browser session, never saved.")
st.sidebar.caption("Without a key, summaries use a built-in extractive NLP engine on text you provide.")
active_provider = provider if provider != "Offline (no key)" and api_key else None


# ------------------------------------------------------------------ dashboard
def page_dashboard():
    st.title("📊 Reading Dashboard")
    s = db.get_stats()
    c = st.columns(5)
    c[0].metric("Total books", s["total"])
    c[1].metric("To read", s["to_read"])
    c[2].metric("Reading", s["reading"])
    c[3].metric("Completed", s["completed"])
    c[4].metric("Avg rating", s["avg_rating"] or "—")

    if s["total"] == 0:
        st.info("Your library is empty. Add your first book from the sidebar.")
        return

    left, right = st.columns(2)
    with left:
        st.subheader("Books by status")
        st.bar_chart(pd.Series({"To Read": s["to_read"], "Reading": s["reading"],
                                "Completed": s["completed"]}))
    with right:
        st.subheader("Books by genre")
        st.bar_chart(pd.Series(s["genres"]))

    done = s["completed"] / s["total"]
    st.subheader("Overall progress")
    st.progress(done, text=f"{s['completed']} of {s['total']} books completed ({done:.0%})")
    st.caption(f"📄 Pages read so far: {s['pages_read']:,}  •  📝 Books with AI summaries: {s['summarized']}")

    current = db.list_books(status="Reading")
    if current:
        st.subheader("Currently reading")
        for b in current:
            frac = min(b["pages_read"] / b["pages"], 1.0) if b["pages"] else 0
            st.progress(frac, text=f"{b['title']} — {b['author']} ({b['pages_read']}/{b['pages']} pages)")


# ------------------------------------------------------------------ add book
def page_add():
    st.title("➕ Add a Book")
    with st.form("add_book", clear_on_submit=True):
        c1, c2 = st.columns(2)
        title = c1.text_input("Title *")
        author = c2.text_input("Author")
        c3, c4, c5 = st.columns(3)
        genre = c3.selectbox("Genre", GENRES)
        status = c4.selectbox("Status", db.STATUSES)
        pages = c5.number_input("Total pages", min_value=0, step=10, value=0)
        notes = st.text_area("Personal notes (optional)")
        if st.form_submit_button("Add to library", type="primary"):
            try:
                bid = db.add_book(title, author or "Unknown", genre, status, pages, notes)
                st.success(f"Added “{title}” (ID {bid}).")
            except ValueError as e:
                st.error(str(e))


# ------------------------------------------------------------------ library
def page_library():
    st.title("📖 My Library")
    f1, f2, f3 = st.columns([2, 1, 1])
    search = f1.text_input("🔎 Search title, author, notes, summary, keywords")
    status = f2.selectbox("Status", ["All"] + db.STATUSES)
    all_genres = sorted({b["genre"] for b in db.list_books()})
    genre = f3.selectbox("Genre", ["All"] + all_genres)

    books = db.list_books(status, search, genre)
    st.caption(f"{len(books)} book(s) shown")
    if books:
        df = pd.DataFrame(books)[["title", "author", "genre", "status", "rating", "pages"]]
        st.download_button("⬇️ Export CSV", df.to_csv(index=False), "reading_list.csv", "text/csv")

    for b in books:
        label = f"{STATUS_ICON[b['status']]} {b['title']} — {b['author']}  |  {b['genre']}  |  {stars(b['rating'])}"
        with st.expander(label):
            if b["summary"]:
                st.markdown(f"**Summary:** {b['summary']}")
                if b["takeaways"]:
                    st.markdown("**Key takeaways:**")
                    for t in b["takeaways"].split("\n"):
                        if t.strip():
                            st.markdown(f"- {t.strip()}")
                if b["keywords"]:
                    st.caption("🏷️ " + b["keywords"])
            else:
                st.caption("No summary yet — generate one in Summary Studio.")

            with st.form(f"edit_{b['id']}"):
                c1, c2, c3 = st.columns(3)
                new_status = c1.selectbox("Status", db.STATUSES, index=db.STATUSES.index(b["status"]))
                new_rating = c2.slider("Rating", 0, 5, b["rating"] or 0, help="0 = unrated")
                new_read = c3.number_input("Pages read", 0, max(b["pages"], 0) or 100000, b["pages_read"] or 0)
                new_notes = st.text_area("Notes", b["notes"] or "")
                save, remove = st.columns(2)
                if save.form_submit_button("💾 Save changes"):
                    db.update_book(b["id"], status=new_status, rating=new_rating or None,
                                   pages_read=new_read, notes=new_notes)
                    st.rerun()
                if remove.form_submit_button("🗑️ Delete"):
                    db.delete_book(b["id"])
                    st.rerun()


# ------------------------------------------------------------------ summary studio
def page_summary():
    st.title("🧠 Summary Studio")
    books = db.list_books()
    if not books:
        st.info("Add a book first.")
        return
    choice = st.selectbox("Choose a book", books, format_func=lambda b: f"{b['title']} — {b['author']}")
    st.write("Provide source material (article, chapter text, notes, or a PDF) for the most accurate summary.")
    tab_paste, tab_file = st.tabs(["Paste text", "Upload .txt / .pdf"])
    text = ""
    with tab_paste:
        text = st.text_area("Source text", height=220, key="src_text")
    with tab_file:
        up = st.file_uploader("Upload file", type=["txt", "pdf"])
        if up:
            text = read_upload(up)
            st.caption(f"Loaded {len(text.split()):,} words from {up.name}")
    n = st.slider("Summary length (offline mode, sentences)", 2, 8, 4)

    if st.button("✨ Generate summary", type="primary"):
        with st.spinner("Summarizing…"):
            out = summarize(choice["title"], choice["author"], text, active_provider, api_key, n)
        if not out["summary"]:
            st.warning("Nothing to summarize. Paste text or enter an AI key (it will use the model's knowledge).")
        else:
            st.session_state["draft"] = (choice["id"], out)

    draft = st.session_state.get("draft")
    if draft and draft[0] == choice["id"]:
        out = draft[1]
        st.success(f"Generated using: {out['method']}")
        st.markdown(f"**Summary**\n\n{out['summary']}")
        st.markdown("**Key takeaways**")
        for t in out["takeaways"]:
            st.markdown(f"- {t}")
        st.caption("🏷️ " + ", ".join(out["keywords"]))
        if st.button("💾 Save to book"):
            db.update_book(choice["id"], summary=out["summary"],
                           takeaways="\n".join(out["takeaways"]),
                           keywords=", ".join(out["keywords"]))
            st.session_state.pop("draft")
            st.success("Saved. View it in My Library.")


# ------------------------------------------------------------------ recommendations
def page_reco():
    st.title("🎯 What should I read next?")
    st.caption("Ranks your 'To Read' list using genres, authors and themes of books you rated 4★ or higher.")
    recs = recommend(db.list_books())
    if not recs:
        st.info("Add some books to your 'To Read' list to get recommendations.")
        return
    for rank, (b, score, why) in enumerate(recs, 1):
        st.markdown(f"**{rank}. {b['title']}** — {b['author']}  \n"
                    f"_{b['genre']}_ • score {score} • because {why}")


{"Dashboard": page_dashboard, "Add Book": page_add, "My Library": page_library,
 "Summary Studio": page_summary, "Recommendations": page_reco}[page]()
