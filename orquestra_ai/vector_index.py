from __future__ import annotations

import math
import os
import uuid
from dataclasses import dataclass
from typing import Any

from .config import OrquestraSettings

try:  # pragma: no cover - depende do ambiente local
    from qdrant_client import QdrantClient
    from qdrant_client.http import models as qmodels
except Exception:  # pragma: no cover - fallback sem qdrant
    QdrantClient = None
    qmodels = None


@dataclass
class VectorHit:
    point_id: str
    score: float
    payload: dict[str, Any]


class OrquestraVectorIndex:
    def __init__(self, settings: OrquestraSettings) -> None:
        self.settings = settings
        self._client = None
        self._vector_size = None
        self._embedder = None

    @property
    def available(self) -> bool:
        return QdrantClient is not None and qmodels is not None

    def _client_or_none(self):
        if not self.available:
            return None
        if self._client is None:
            try:
                if self.settings.qdrant_url:
                    self._client = QdrantClient(url=self.settings.qdrant_url)
                else:
                    self.settings.qdrant_path.mkdir(parents=True, exist_ok=True)
                    self._client = QdrantClient(path=str(self.settings.qdrant_path))
            except RuntimeError:
                self._client = None
        return self._client

    def _ensure_collection(self, collection_name: str) -> bool:
        client = self._client_or_none()
        if client is None:
            return False
        vector_size = self._resolve_vector_size()
        if vector_size <= 0:
            return False
        collections = {item.name for item in client.get_collections().collections}
        if collection_name not in collections:
            client.create_collection(
                collection_name=collection_name,
                vectors_config=qmodels.VectorParams(size=vector_size, distance=qmodels.Distance.COSINE),
            )
        return True

    def _resolve_vector_size(self) -> int:
        if self._vector_size is not None:
            return self._vector_size
        embedder = self._get_embedder()
        if embedder is None:
            self._vector_size = 0
            return self._vector_size
        sample = embedder.encode(["orquestra-memory-probe"], normalize_embeddings=True)
        vector = sample.tolist()[0]
        self._vector_size = len(vector)
        return self._vector_size

    def _embed(self, texts: list[str]) -> list[list[float]]:
        embedder = self._get_embedder()
        if embedder is None:
            return []
        vectors = embedder.encode(texts, normalize_embeddings=True)
        return vectors.tolist()

    def _get_embedder(self):
        if self._embedder is not None:
            return self._embedder
        try:  # pragma: no cover - depende do ambiente local
            from sentence_transformers import SentenceTransformer
        except Exception:
            return None
        cache_dir = self.settings.artifacts_root / "hf_cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        os.environ.setdefault("HF_HOME", str(cache_dir))
        os.environ.setdefault("SENTENCE_TRANSFORMERS_HOME", str(cache_dir / "sentence_transformers"))
        try:
            self._embedder = SentenceTransformer(
                self.settings.local_embedding_model,
                cache_folder=str(cache_dir / "sentence_transformers"),
                local_files_only=True,
            )
        except Exception:
            self._embedder = None
        return self._embedder

    def _normalize_point_id(self, raw_id: str) -> str:
        return str(uuid.uuid5(uuid.NAMESPACE_URL, raw_id))

    def close(self) -> None:
        if self._client is None:
            return
        try:
            self._client.close()
        except Exception:
            pass
        finally:
            self._client = None

    def upsert(self, collection_name: str, items: list[dict[str, Any]]) -> None:
        if not items or not self._ensure_collection(collection_name):
            return
        client = self._client_or_none()
        assert client is not None
        payloads: list[dict[str, Any]] = []
        vectors: list[list[float]] = []
        ids: list[str] = []
        texts: list[str] = []
        for item in items:
            text = str(item.get("text") or "").strip()
            point_id = str(item.get("id") or "").strip()
            if not text or not point_id:
                continue
            texts.append(text)
            ids.append(self._normalize_point_id(point_id))
            payloads.append(item.get("payload", {}))
        if not ids:
            return
        vectors = self._embed(texts)
        if not vectors:
            return
        client.upsert(
            collection_name=collection_name,
            points=[
                qmodels.PointStruct(id=ids[index], vector=vectors[index], payload=payloads[index])
                for index in range(len(ids))
            ],
        )

    def query(self, collection_name: str, text: str, limit: int = 5) -> list[VectorHit]:
        if not text.strip() or not self._ensure_collection(collection_name):
            return []
        client = self._client_or_none()
        assert client is not None
        vectors = self._embed([text])
        if not vectors:
            return []
        vector = vectors[0]
        points = client.query_points(collection_name=collection_name, query=vector, limit=limit).points
        return [
            VectorHit(
                point_id=str((point.payload or {}).get("original_id") or point.id),
                score=float(point.score) if point.score is not None else 0.0,
                payload=point.payload or {},
            )
            for point in points
        ]


def score_overlap(query: str, *parts: str) -> float:
    query_terms = {term for term in query.lower().split() if len(term) > 2}
    if not query_terms:
        return 0.0
    haystack_terms: set[str] = set()
    for part in parts:
        haystack_terms.update(term for term in part.lower().split() if len(term) > 2)
    if not haystack_terms:
        return 0.0
    overlap = len(query_terms & haystack_terms)
    return overlap / max(len(query_terms), 1)


def recency_bonus(hours_since_update: float) -> float:
    if hours_since_update <= 1:
        return 0.3
    if hours_since_update <= 24:
        return 0.18
    if hours_since_update <= 24 * 7:
        return 0.08
    return 0.0


def blend_scores(*scores: float) -> float:
    valid = [score for score in scores if not math.isnan(score)]
    if not valid:
        return 0.0
    return sum(valid) / len(valid)
