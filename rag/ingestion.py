from __future__ import annotations

import csv
import hashlib
import json
import time
from pathlib import Path
from typing import Any

from training.local.common import WebCrawlSource
from training.local.web_ingest import (
    domain_allowed,
    extract_links,
    extract_text_bs4,
    extract_text_builtin,
    fetch_url,
    normalize_url,
    pattern_allowed,
    pattern_blocked,
    robot_allowed,
)

from .common import (
    RagChunk,
    RagPaths,
    append_jsonl,
    chunk_text,
    default_collection_name,
    read_json,
    sanitize_metadata,
    slugify,
    utc_now,
    write_json,
)
from .vectorstore import upsert_chunks

TEXT_EXTENSIONS = {".md", ".txt", ".json", ".jsonl", ".py", ".sh", ".yaml", ".yml", ".toml", ".csv"}


def _read_text_file(path: Path) -> str:
    if path.suffix == ".json":
        payload = read_json(path)
        return json.dumps(payload, ensure_ascii=False, indent=2)
    return path.read_text(encoding="utf-8", errors="ignore")


def _build_chunks(
    *,
    collection_name: str,
    document_id: str,
    text: str,
    base_metadata: dict[str, Any],
    chunk_size: int,
    overlap: int,
) -> list[RagChunk]:
    chunks: list[RagChunk] = []
    for index, piece in enumerate(chunk_text(text, chunk_size=chunk_size, overlap=overlap)):
        chunks.append(
            RagChunk(
                chunk_id=f"{document_id}:{index:04d}",
                document_id=document_id,
                collection_name=collection_name,
                text=piece,
                metadata=sanitize_metadata(base_metadata | {"chunk_index": index}),
            )
        )
    return chunks


def ingest_local_directory(
    paths: RagPaths,
    source_dir: Path,
    *,
    collection_name: str = "knowledge_base",
    glob_pattern: str = "**/*",
    chunk_size: int = 800,
    overlap: int = 120,
) -> dict[str, Any]:
    paths.ensure()
    source_dir = source_dir.resolve()
    documents = 0
    chunks: list[RagChunk] = []

    for path in sorted(source_dir.glob(glob_pattern)):
        if not path.is_file() or path.suffix.lower() not in TEXT_EXTENSIONS:
            continue
        text = _read_text_file(path).strip()
        if not text:
            continue
        documents += 1
        document_id = slugify(str(path.relative_to(source_dir)))
        chunks.extend(
            _build_chunks(
                collection_name=collection_name,
                document_id=document_id,
                text=text,
                base_metadata={
                    "source_type": "local_file",
                    "source_path": str(path),
                    "title": path.name,
                },
                chunk_size=chunk_size,
                overlap=overlap,
            )
        )

    upsert_result = upsert_chunks(paths, collection_name, chunks)
    ingestion_id = f"local-{slugify(source_dir.name)}-{slugify(utc_now())}"
    payload = {
        "ingestion_id": ingestion_id,
        "created_at": utc_now(),
        "source_type": "local_directory",
        "source_dir": str(source_dir),
        "collection_name": collection_name,
        "documents": documents,
        "chunks": upsert_result["count"],
    }
    write_json(paths.ingestions_dir / f"{ingestion_id}.json", payload)
    append_jsonl(paths.experiments_root / "ingestions_index.jsonl", payload)
    return payload


def ingest_security_csv(
    paths: RagPaths,
    csv_path: Path,
    *,
    collection_name: str = "security_base",
    chunk_size: int = 1200,
    overlap: int = 80,
) -> dict[str, Any]:
    paths.ensure()
    csv_path = csv_path.resolve()
    rows = 0
    chunks: list[RagChunk] = []

    with csv_path.open("r", encoding="utf-8", errors="ignore", newline="") as handle:
        reader = csv.DictReader(handle)
        for index, row in enumerate(reader):
            rows += 1
            rule_id = str(row.get("id") or f"rule-{index}")
            text_parts = [
                f"Categoria: {row.get('category', 'unspecified')}",
                f"Severidade: {row.get('severity', 'unknown')}",
                f"Regra: {row.get('rule', '')}",
                f"Padrao: {row.get('pattern', '')}",
                f"Permitido: {row.get('allowed', '')}",
                f"Exemplo: {row.get('example', '')}",
                f"Mitigacao: {row.get('mitigation', '')}",
                f"Notas: {row.get('notes', '')}",
            ]
            text = "\n".join(part for part in text_parts if part.split(": ", 1)[1].strip())
            if not text.strip():
                continue
            chunks.extend(
                _build_chunks(
                    collection_name=collection_name,
                    document_id=slugify(rule_id),
                    text=text,
                    base_metadata={
                        "source_type": "security_csv",
                        "source_path": str(csv_path),
                        "rule_id": rule_id,
                        "category": row.get("category", ""),
                        "severity": row.get("severity", ""),
                        "allowed": row.get("allowed", ""),
                    },
                    chunk_size=chunk_size,
                    overlap=overlap,
                )
            )

    upsert_result = upsert_chunks(paths, collection_name, chunks)
    ingestion_id = f"security-{slugify(csv_path.stem)}-{slugify(utc_now())}"
    payload = {
        "ingestion_id": ingestion_id,
        "created_at": utc_now(),
        "source_type": "security_csv",
        "source_path": str(csv_path),
        "collection_name": collection_name,
        "rows": rows,
        "chunks": upsert_result["count"],
    }
    write_json(paths.ingestions_dir / f"{ingestion_id}.json", payload)
    append_jsonl(paths.experiments_root / "ingestions_index.jsonl", payload)
    return payload


def ingest_web_manifest(
    paths: RagPaths,
    manifest_path: Path,
    *,
    collection_name: str | None = None,
    chunk_size: int = 800,
    overlap: int = 120,
) -> dict[str, Any]:
    paths.ensure()
    payload = read_json(manifest_path)
    source = WebCrawlSource.from_dict(payload["web_crawl"])
    final_collection = collection_name or payload.get("collection_name") or default_collection_name(payload.get("name", "knowledge_base"))
    queue: list[tuple[str, int]] = [(normalize_url(item), 0) for item in source.seed_urls]
    visited: set[str] = set()
    seen_hashes: set[str] = set()
    chunks: list[RagChunk] = []
    accepted = 0
    rejected = 0
    duplicates = 0
    raw_documents: list[dict[str, Any]] = []

    while queue and accepted < source.max_pages:
        current_url, depth = queue.pop(0)
        if current_url in visited:
            continue
        visited.add(current_url)

        if not domain_allowed(current_url, source.allowed_domains, source.blocked_domains):
            rejected += 1
            continue
        if not pattern_allowed(current_url, source.follow_patterns):
            rejected += 1
            continue
        if pattern_blocked(current_url, source.exclude_patterns):
            rejected += 1
            continue
        if source.respect_robots and not robot_allowed(current_url, user_agent=source.user_agent):
            rejected += 1
            continue

        try:
            html_text = fetch_url(
                current_url,
                timeout_seconds=source.request_timeout_seconds,
                user_agent=source.user_agent,
            )
        except Exception:
            rejected += 1
            continue

        if source.adapter == "builtin_html":
            title, text = extract_text_builtin(html_text)
        else:
            title, text = extract_text_bs4(html_text, source.content_selectors)
        text = text[: source.max_chars_per_document].strip()
        if not text:
            rejected += 1
            continue
        content_hash = hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()
        if content_hash in seen_hashes:
            duplicates += 1
            continue
        seen_hashes.add(content_hash)

        accepted += 1
        document_id = slugify(current_url)
        raw_documents.append(
            {
                "document_id": document_id,
                "source_url": current_url,
                "title": title or current_url,
                "depth": depth,
                "content_hash": content_hash,
                "text": text,
            }
        )
        chunks.extend(
            _build_chunks(
                collection_name=final_collection,
                document_id=document_id,
                text=text,
                base_metadata={
                    "source_type": "web",
                    "source_url": current_url,
                    "title": title or current_url,
                    "depth": depth,
                },
                chunk_size=chunk_size,
                overlap=overlap,
            )
        )

        if depth >= source.max_depth:
            continue
        if source.delay_between_requests_ms > 0:
            time.sleep(source.delay_between_requests_ms / 1000)
        for link in extract_links(current_url, html_text):
            if link not in visited:
                queue.append((link, depth + 1))

    upsert_result = upsert_chunks(paths, final_collection, chunks)
    ingestion_id = f"web-{slugify(payload.get('name', manifest_path.stem))}-{slugify(utc_now())}"
    raw_path = paths.crawl_artifacts_dir / f"{ingestion_id}.jsonl"
    with raw_path.open("w", encoding="utf-8") as handle:
        for item in raw_documents:
            handle.write(json.dumps(item, ensure_ascii=False) + "\n")
    report = {
        "ingestion_id": ingestion_id,
        "created_at": utc_now(),
        "source_type": "web_manifest",
        "manifest_path": str(manifest_path),
        "collection_name": final_collection,
        "visited": len(visited),
        "accepted": accepted,
        "rejected": rejected,
        "duplicates": duplicates,
        "chunks": upsert_result["count"],
        "raw_documents_path": str(raw_path),
    }
    write_json(paths.ingestions_dir / f"{ingestion_id}.json", report)
    append_jsonl(paths.experiments_root / "ingestions_index.jsonl", report)
    return report
