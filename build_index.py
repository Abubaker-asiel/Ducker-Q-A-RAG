"""python build_index.py  ->  (re)build the vector index from data/courses/*"""
from collections import Counter
from pathlib import Path

from rag.ingest import load_all
from rag.store import rebuild_index

ROOT = Path(__file__).parent
chunks = load_all(ROOT / "data" / "courses")
if not chunks:
    raise SystemExit("No files found. Put each course in its own folder under data/courses/.")
rebuild_index(ROOT / "storage", chunks)

print(f"Indexed {len(chunks)} chunks")
for (course, ftype), n in sorted(Counter((c.meta["course"], c.meta["type"]) for c in chunks).items()):
    print(f"  {course:<24}{ftype:<6}{n}")
