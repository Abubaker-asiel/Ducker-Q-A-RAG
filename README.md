# Ask the course

RAG system that answers student questions from course files (PDF, DOCX, CSV, TXT) and shows the exact passages it used.

**Stack:** pypdf / python-docx / csv loaders → cleaning + chunking → Chroma (local MiniLM embeddings) → retriever → Claude → Streamlit.

## Run

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # add your ANTHROPIC_API_KEY
python build_index.py       # first run downloads the small embedding model
streamlit run app.py
```

## Your courses

One folder per course under `data/courses/`. Any mix of `.pdf .docx .csv .txt` inside.
`api-fastapi-docker` is your real PDF; `python-basics` and `sql-fundamentals` are small samples
(CSV, TXT, DOCX) so all four formats are covered. Replace them with real material, then press **Rebuild index**.

## How it works

| Step | File | Notes |
|---|---|---|
| Extract + clean | `rag/ingest.py` | Strips repeated page headers and page numbers from PDFs; tracks `Module n` headings (PDF) and Heading styles (DOCX) |
| Chunk | `rag/ingest.py` | ~900 chars, 150 overlap, never crosses a page; CSV = one chunk per row |
| Embed + store | `rag/store.py` | Chroma persistent store in `storage/`, cosine distance, filter by course |
| Retrieve + generate | `rag/chain.py` | Top-k excerpts are numbered and sent to Claude with a "context only" prompt; answer cites `[n]` |
| Attribution | `app.py` | Cited excerpts shown under the answer with file / module / page |

## Tuning

- `CLAUDE_MODEL` in `.env` picks the model.
- `MAX_DISTANCE` (default 0.9): if the best match is farther than this, the app answers "not found" without calling Claude. Lower it for stricter answers.
- Chunk size and overlap: arguments of `load_all()` in `rag/ingest.py`.

## Known issues in the sample PDF

The quiz is numbered 9–18 but the answer key is 1–10, and the "Common Mistakes" table has a stray Flutter row. Fix the source PDF if you want the Q&A on those sections to be exact.
# Ducker-Q-A-RAG
