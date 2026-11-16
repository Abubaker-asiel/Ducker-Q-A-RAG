"""Vector store: Chroma with its built-in MiniLM embeddings (runs locally, no extra key)."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import chromadb
from chromadb.utils.embedding_functions import DefaultEmbeddingFunction

NAME = "courses"


@dataclass
class Hit:
    text: str
    meta: dict
    distance: float


def _client(path: Path):
    return chromadb.PersistentClient(path=str(path))


def get_collection(path: Path):
    return _client(path).get_or_create_collection(
        NAME, embedding_function=DefaultEmbeddingFunction(), metadata={"hnsw:space": "cosine"}
    )


def rebuild_index(path: Path, chunks):
    client = _client(path)
    try:
        client.delete_collection(NAME)
    except Exception:
        pass
    col = client.create_collection(
        NAME, embedding_function=DefaultEmbeddingFunction(), metadata={"hnsw:space": "cosine"}
    )
    for i in range(0, len(chunks), 64):
        batch = chunks[i : i + 64]
        col.add(
            ids=[c.id for c in batch],
            documents=[c.text for c in batch],
            metadatas=[c.meta for c in batch],
        )
    return col


def search(col, question: str, k: int = 4, courses: list[str] | None = None) -> list[Hit]:
    where = {"course": {"$in": courses}} if courses else None
    res = col.query(query_texts=[question], n_results=k, where=where)
    return [
        Hit(doc, meta, dist)
        for doc, meta, dist in zip(res["documents"][0], res["metadatas"][0], res["distances"][0])
    ]
