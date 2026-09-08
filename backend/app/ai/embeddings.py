"""Sentence embeddings for FAQ retrieval (docs plan §9.2), via
BAAI/bge-small-en-v1.5 (384-dim) through sentence-transformers. The model is
loaded lazily and cached at module scope — it's tens of MB and slow to load,
so every caller (the seeding script and live query embedding) shares one
instance instead of reloading it per call.

BGE's own model card recommends prefixing *queries* (not passages) with an
instruction string for asymmetric retrieval — matching a short question
against a bank of canonical FAQ questions is exactly that asymmetric case.
"""

from functools import lru_cache
from typing import cast

from sentence_transformers import SentenceTransformer

from app.core.config import get_settings

settings = get_settings()

QUERY_INSTRUCTION = "Represent this sentence for searching relevant passages: "


@lru_cache(maxsize=1)
def _get_model() -> SentenceTransformer:
    return SentenceTransformer(settings.embedding_model)


def embed_query(text: str) -> list[float]:
    """Embeds an incoming user question for similarity search against passages."""
    model = _get_model()
    vector = model.encode(f"{QUERY_INSTRUCTION}{text}", normalize_embeddings=True, convert_to_numpy=True)
    # numpy's .tolist() stub can't express "always floats here" from a bare
    # ndarray, but sentence-transformers always returns float embeddings.
    return cast(list[float], vector.tolist())


def embed_passage(text: str) -> list[float]:
    """Embeds a single stored FAQ question (no query instruction prefix)."""
    model = _get_model()
    vector = model.encode(text, normalize_embeddings=True, convert_to_numpy=True)
    return cast(list[float], vector.tolist())


def embed_passages(texts: list[str]) -> list[list[float]]:
    model = _get_model()
    vectors = model.encode(texts, normalize_embeddings=True, convert_to_numpy=True)
    return cast(list[list[float]], vectors.tolist())
