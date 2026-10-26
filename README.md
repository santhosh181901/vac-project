# AI Reading List and Book Summary Manager

A Streamlit app to manage a personal reading list and generate AI-powered book summaries.

## Features
- Add, edit, delete books with genre, status (To Read / Reading / Completed), rating, pages and notes
- Dashboard: totals, status and genre charts, overall and per-book progress
- Search and filter the library; export it to CSV
- **Summary Studio**: paste text or upload a .txt/.pdf and get a summary, key takeaways and keywords
  - With a Mistral or Groq API key: LLM summaries (JSON-structured output)
  - Without a key: built-in offline extractive NLP summarizer (word-frequency sentence ranking)
  - Automatic fallback to offline mode if the AI call fails
- Recommendations: ranks the "To Read" list using genres, authors and themes of books you rated 4-5 stars
- SQLite storage (no setup needed)

## Run
```bash
pip install -r requirements.txt
streamlit run app.py
```

## Test
```bash
python -m pytest -q
```

## Structure
| File | Purpose |
|---|---|
| `app.py` | Streamlit user interface (5 pages) |
| `database.py` | SQLite CRUD, validation, statistics |
| `summarizer.py` | LLM + offline extractive summarization |
| `recommender.py` | Content-based "read next" ranking |
| `tests/test_core.py` | Unit tests (10) |
