"""
semantic_search.py
Part 3 — fully local, no-cost semantic search using sentence-transformers.

Uses sentence-transformers/all-MiniLM-L6-v2 (pinned in requirements.txt).
The model is downloaded and cached under ~/.cache/huggingface the FIRST
time it is loaded on any machine (requires internet, one time only).
Every run after that uses the cached weights and needs zero internet
access and zero API key.
"""
import math
from functools import lru_cache

_model = None


def _get_model():
    """Lazily load the model so importing this module doesn't require it."""
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer

        _model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
    return _model


def embed_text(text: str):
    model = _get_model()
    return model.encode(text)


def embed_texts(texts: list[str]):
    model = _get_model()
    return model.encode(texts)


def cosine_similarity(vec_a, vec_b) -> float:
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def rank_by_similarity(query: str, notes: list[dict], top_n: int = 3) -> list[dict]:
    """
    notes: list of dicts each with at least "id", "title", "content".
    Returns the top_n notes ranked by cosine similarity to the query,
    each with an added "similarity" score, highest first.
    """
    query_vec = embed_text(query)
    contents = [n["content"] for n in notes]
    note_vecs = embed_texts(contents)

    scored = []
    for note, vec in zip(notes, note_vecs):
        score = cosine_similarity(query_vec, vec)
        scored.append({**note, "similarity": round(float(score), 4)})

    scored.sort(key=lambda n: n["similarity"], reverse=True)
    return scored[:top_n]