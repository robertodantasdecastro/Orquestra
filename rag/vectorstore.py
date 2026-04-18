from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import chromadb
from sentence_transformers import SentenceTransformer

from .common import RagChunk, RagPaths, sanitize_metadata

_EMBEDDER_CACHE: dict[str, SentenceTransformer] = {}


@dataclass
class RetrievedChunk:
    chunk_id: str
    text: str
    metadata: dict[str, Any]
    distance: float | None


def embedding_model_name() -> str:
    import os

    return os.getenv("RAG_EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")


def get_embedder(paths: RagPaths) -> SentenceTransformer:
    paths.apply_runtime_env()
    model_name = embedding_model_name()
    embedder = _EMBEDDER_CACHE.get(model_name)
    if embedder is None:
        embedder = SentenceTransformer(model_name)
        _EMBEDDER_CACHE[model_name] = embedder
    return embedder


def get_client(paths: RagPaths) -> chromadb.PersistentClient:
    paths.ensure()
    return chromadb.PersistentClient(path=str(paths.chroma_dir))


def get_collection(paths: RagPaths, collection_name: str):
    client = get_client(paths)
    return client.get_or_create_collection(collection_name)


def upsert_chunks(paths: RagPaths, collection_name: str, chunks: list[RagChunk]) -> dict[str, Any]:
    if not chunks:
        return {"count": 0, "collection_name": collection_name}

    embedder = get_embedder(paths)
    collection = get_collection(paths, collection_name)
    texts = [chunk.text for chunk in chunks]
    embeddings = embedder.encode(texts, normalize_embeddings=True).tolist()
    ids = [chunk.chunk_id for chunk in chunks]
    metadatas = [sanitize_metadata(chunk.metadata | {"document_id": chunk.document_id}) for chunk in chunks]
    collection.upsert(
        ids=ids,
        embeddings=embeddings,
        documents=texts,
        metadatas=metadatas,
    )
    return {"count": len(chunks), "collection_name": collection_name}


def query_collection(paths: RagPaths, collection_name: str, query_text: str, top_k: int = 4) -> list[RetrievedChunk]:
    collection = get_collection(paths, collection_name)
    count = collection.count()
    if count <= 0:
        return []
    embedder = get_embedder(paths)
    vector = embedder.encode([query_text], normalize_embeddings=True).tolist()
    result = collection.query(query_embeddings=vector, n_results=min(top_k, count))

    ids = result.get("ids", [[]])[0]
    documents = result.get("documents", [[]])[0]
    metadatas = result.get("metadatas", [[]])[0]
    distances = result.get("distances", [[]])[0] if result.get("distances") else []

    payload: list[RetrievedChunk] = []
    for index, chunk_id in enumerate(ids):
        payload.append(
            RetrievedChunk(
                chunk_id=chunk_id,
                text=documents[index],
                metadata=metadatas[index] or {},
                distance=distances[index] if index < len(distances) else None,
            )
        )
    return payload
