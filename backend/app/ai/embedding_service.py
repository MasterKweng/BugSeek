"""Embedding service."""
from __future__ import annotations

from typing import List
import numpy as np
from pathlib import Path

from app.platform.vector.base import VectorBase


class EmbeddingService:
    """Embedding service based on sentence-transformers."""

    def __init__(self, cache_dir: str | None = None):
        base_dir = Path(cache_dir) if cache_dir else Path(__file__).resolve().parents[2] / "data"
        self.vector = VectorBase(cache_dir=base_dir)

    def encode(self, texts: List[str]) -> List[List[float]]:
        vectors = self.vector.encode(texts)
        return vectors.astype(float).tolist()

    def similarity(self, a: List[float], b: List[float]) -> float:
        va = np.array(a, dtype=float)
        vb = np.array(b, dtype=float)
        if va.size == 0 or vb.size == 0:
            return 0.0
        return float(np.dot(va, vb) / (np.linalg.norm(va) * np.linalg.norm(vb) + 1e-10))
