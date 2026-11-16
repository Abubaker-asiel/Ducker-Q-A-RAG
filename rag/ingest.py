"""Load course files (PDF, DOCX, CSV, TXT), clean them and cut them into chunks."""
from __future__ import annotations

import csv
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

SUPPORTED = {".pdf", ".docx", ".csv", ".txt"}


@dataclass
class Chunk:
    id: str
    text: str
    meta: dict


# ---------- cleaning & chunking ----------

def clean(text: str) -> str:
    text = text.replace("\x00", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n", text)
    return text.strip()


def split_text(text: str, size: int = 900, overlap: int = 150) -> list[str]:
    """Pack lines into chunks of ~size characters, carrying a short overlap forward."""
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    chunks, cur = [], ""
    for line in lines:
        if len(cur) + len(line) + 1 <= size:
            cur = f"{cur}\n{line}".strip()
            continue
        if cur:
            chunks.append(cur)
        tail = cur[-overlap:] if cur and overlap else ""
        if " " in tail:
            tail = tail[tail.find(" ") + 1:]
        cur = f"{tail}\n{line}".strip() if len(line) <= size else line
        while len(cur) > size:
            chunks.append(cur[:size])
            cur = cur[size - overlap:]
    if cur:
        chunks.append(cur)
    return chunks


# ---------- per-format loaders: each returns a list of units ----------
# unit = {"text": str, "page": int|None, "section": str|None, "row": int|None}

def _repeated_lines(pages: list[str]) -> list[str]:
    counts = Counter()
    for p in pages:
        counts.update({l.strip() for l in p.split("\n") if len(l.strip()) >= 8})
    need = max(3, int(0.4 * len(pages)))
    return [l for l, c in counts.items() if c >= need]


def _pdf_units(path: Path):
    from pypdf import PdfReader

    pages = [p.extract_text() or "" for p in PdfReader(str(path)).pages]
    repeated = _repeated_lines(pages)
    units, section = [], None
    for i, raw in enumerate(pages, 1):
        for line in repeated:  # running headers, even when glued to other text
            raw = raw.replace(line, "")
        raw = re.sub(r"(?m)^\s*Page\s+\d+\s*$", "", raw)
        for part in re.split(r"(?m)^(?=MODULE\s+\d+\s*$)", raw):
            m = re.match(r"MODULE\s+(\d+)\s*\n\s*(.+)", part)
            if m:
                section = f"Module {m.group(1)}: {m.group(2).strip()}"
            units.append({"text": part, "page": i, "section": section})
    return units


def _docx_units(path: Path):
    from docx import Document

    doc = Document(str(path))
    units, section, buf = [], None, []

    def flush():
        if buf:
            units.append({"text": "\n".join(buf), "section": section})
            buf.clear()

    for p in doc.paragraphs:
        if p.style.name.lower().startswith("heading") and p.text.strip():
            flush()
            section = p.text.strip()
        elif p.text.strip():
            buf.append(p.text)
    flush()
    for t in doc.tables:
        rows = [" | ".join(c.text.strip() for c in r.cells) for r in t.rows]
        units.append({"text": "\n".join(rows), "section": "Table"})
    return units


def _csv_units(path: Path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        return [
            {"text": "; ".join(f"{k}: {v}" for k, v in row.items() if v), "row": i}
            for i, row in enumerate(csv.DictReader(f), 1)
        ]


def _txt_units(path: Path):
    return [{"text": path.read_text(encoding="utf-8", errors="replace")}]


LOADERS = {".pdf": _pdf_units, ".docx": _docx_units, ".csv": _csv_units, ".txt": _txt_units}


# ---------- public API ----------

def load_file(path: Path, course: str, size: int = 900, overlap: int = 150) -> list[Chunk]:
    out, n = [], 0
    for unit in LOADERS[path.suffix.lower()](path):
        text = clean(unit["text"])
        if len(text) < 20:
            continue
        for piece in split_text(text, size, overlap):
            meta = {"course": course, "file": path.name, "type": path.suffix[1:].lower()}
            for key in ("page", "section", "row"):
                if unit.get(key) is not None:
                    meta[key] = unit[key]
            out.append(Chunk(f"{course}/{path.name}#{n}", piece, meta))
            n += 1
    return out


def load_all(root: Path, size: int = 900, overlap: int = 150) -> list[Chunk]:
    """Each sub-folder of `root` is one course; every supported file inside it is indexed."""
    chunks: list[Chunk] = []
    for course_dir in sorted(p for p in Path(root).iterdir() if p.is_dir()):
        for f in sorted(course_dir.rglob("*")):
            if f.is_file() and f.suffix.lower() in SUPPORTED:
                chunks += load_file(f, course_dir.name, size, overlap)
    return chunks
