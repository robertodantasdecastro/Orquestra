from __future__ import annotations

import hashlib
import html
import json
import re
import urllib.parse
import urllib.robotparser
import urllib.request
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup

from .common import (
    DatasetBundle,
    RuntimePaths,
    WebCrawlSource,
    append_jsonl,
    current_timestamp_slug,
    sleep_ms,
    slugify,
    utc_now,
    write_json,
    write_jsonl,
)


class LinkCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        attr_map = dict(attrs)
        href = attr_map.get("href")
        if href:
            self.links.append(href)


@dataclass
class CrawlDocument:
    url: str
    canonical_url: str
    depth: int
    title: str
    text: str
    content_hash: str
    fetched_at: str
    saved_html_path: str | None = None


def adapter_supported(adapter: str) -> bool:
    if adapter in {"builtin_bs4", "builtin_html"}:
        return True
    if adapter in {"langchain_webbase", "langchain_recursive"}:
        try:
            import langchain_community.document_loaders  # type: ignore  # noqa: F401
        except Exception:
            return False
        return True
    return False


def normalize_url(url: str) -> str:
    parsed = urllib.parse.urlsplit(url)
    clean = parsed._replace(fragment="")
    return urllib.parse.urlunsplit(clean)


def domain_allowed(url: str, allowed_domains: list[str], blocked_domains: list[str]) -> bool:
    hostname = urllib.parse.urlsplit(url).hostname or ""
    if blocked_domains and any(hostname == item or hostname.endswith(f".{item}") for item in blocked_domains):
        return False
    if not allowed_domains:
        return True
    return any(hostname == item or hostname.endswith(f".{item}") for item in allowed_domains)


def pattern_allowed(url: str, patterns: list[str]) -> bool:
    if not patterns:
        return True
    return any(re.search(pattern, url) for pattern in patterns)


def pattern_blocked(url: str, patterns: list[str]) -> bool:
    return any(re.search(pattern, url) for pattern in patterns)


def extract_links(base_url: str, html_text: str) -> list[str]:
    parser = LinkCollector()
    parser.feed(html_text)
    links: list[str] = []
    for href in parser.links:
        resolved = urllib.parse.urljoin(base_url, href)
        if resolved.startswith(("http://", "https://")):
            links.append(normalize_url(resolved))
    return links


def extract_text_bs4(html_text: str, selectors: list[str]) -> tuple[str, str]:
    soup = BeautifulSoup(html_text, "html.parser")
    title = (soup.title.string or "").strip() if soup.title and soup.title.string else ""
    chunks: list[str] = []
    if selectors:
        for selector in selectors:
            for node in soup.select(selector):
                text = node.get_text("\n", strip=True)
                if text:
                    chunks.append(text)
    if not chunks:
        body = soup.get_text("\n", strip=True)
        if body:
            chunks.append(body)
    merged = "\n".join(chunks)
    merged = re.sub(r"\n{2,}", "\n\n", merged)
    return title, html.unescape(merged).strip()


def extract_text_builtin(html_text: str) -> tuple[str, str]:
    title_match = re.search(r"<title>(.*?)</title>", html_text, re.IGNORECASE | re.DOTALL)
    title = html.unescape(title_match.group(1).strip()) if title_match else ""
    text = re.sub(r"<script.*?</script>", " ", html_text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<style.*?</style>", " ", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", html.unescape(text)).strip()
    return title, text


def fetch_url(url: str, *, timeout_seconds: int, user_agent: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": user_agent})
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        return response.read().decode("utf-8", errors="ignore")


def robot_allowed(url: str, *, user_agent: str) -> bool:
    parsed = urllib.parse.urlsplit(url)
    robots_url = urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, "/robots.txt", "", ""))
    robot_parser = urllib.robotparser.RobotFileParser()
    try:
        robot_parser.set_url(robots_url)
        robot_parser.read()
        return robot_parser.can_fetch(user_agent, url)
    except Exception:
        return True


def sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", text)
    return [item.strip() for item in parts if item.strip()]


def build_summary_record(document: CrawlDocument, chunk_index: int) -> dict[str, Any]:
    content = document.text.strip()
    content_sentences = sentences(content)
    if len(content_sentences) >= 3:
        output = " ".join(content_sentences[:2])
        input_text = " ".join(content_sentences[2:]) or content
    else:
        midpoint = max(len(content) // 2, 1)
        output = content[:midpoint].strip()
        input_text = content[midpoint:].strip() or content
    return {
        "id": f"{slugify(document.title or document.url)}-{chunk_index}",
        "instruction": "Resuma o conteudo abaixo em no maximo duas frases.",
        "input": input_text[:2400],
        "context": f"Titulo: {document.title}\nURL: {document.url}",
        "output": output[:400],
        "source_url": document.url,
        "source_hash": document.content_hash,
    }


def split_records(records: list[dict[str, Any]], train_ratio: float, val_ratio: float) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    if not records:
        return [], [], []
    ordered = sorted(records, key=lambda item: item["id"])
    total = len(ordered)
    train_end = max(1, int(total * train_ratio))
    val_end = min(total, train_end + max(1 if total > 2 else 0, int(total * val_ratio)))
    train = ordered[:train_end]
    val = ordered[train_end:val_end] or ordered[:1]
    test = ordered[val_end:] or ordered[-1:]
    return train, val, test


def run_web_ingestion(paths: RuntimePaths, manifest_path: Path, source: WebCrawlSource, dataset_name: str) -> DatasetBundle:
    if not adapter_supported(source.adapter):
        raise RuntimeError(
            f"Adapter de coleta '{source.adapter}' nao esta disponivel neste ambiente. "
            "Use 'builtin_bs4' ou instale os loaders opcionais correspondentes."
        )

    job_id = f"web-{current_timestamp_slug()}-{slugify(dataset_name)}"
    raw_dir = paths.datasets_web_raw_root / job_id
    curated_dir = paths.datasets_web_curated_root / job_id
    raw_dir.mkdir(parents=True, exist_ok=True)
    curated_dir.mkdir(parents=True, exist_ok=True)

    queue: list[tuple[str, int]] = [(normalize_url(item), 0) for item in source.seed_urls]
    visited: set[str] = set()
    content_hashes: set[str] = set()
    documents: list[CrawlDocument] = []
    rejected: list[dict[str, Any]] = []

    while queue and len(documents) < source.max_pages:
        current_url, depth = queue.pop(0)
        if current_url in visited:
            continue
        visited.add(current_url)

        if not domain_allowed(current_url, source.allowed_domains, source.blocked_domains):
            rejected.append({"url": current_url, "reason": "blocked_domain"})
            continue
        if not pattern_allowed(current_url, source.follow_patterns):
            rejected.append({"url": current_url, "reason": "follow_pattern_miss"})
            continue
        if pattern_blocked(current_url, source.exclude_patterns):
            rejected.append({"url": current_url, "reason": "exclude_pattern_match"})
            continue
        if source.respect_robots and not robot_allowed(current_url, user_agent=source.user_agent):
            rejected.append({"url": current_url, "reason": "robots_disallow"})
            continue

        try:
            html_text = fetch_url(
                current_url,
                timeout_seconds=source.request_timeout_seconds,
                user_agent=source.user_agent,
            )
        except Exception as exc:
            rejected.append({"url": current_url, "reason": f"fetch_error:{type(exc).__name__}"})
            continue

        if source.adapter == "builtin_html":
            title, extracted_text = extract_text_builtin(html_text)
        else:
            title, extracted_text = extract_text_bs4(html_text, source.content_selectors)
        extracted_text = extracted_text[: source.max_chars_per_document].strip()
        if not extracted_text:
            rejected.append({"url": current_url, "reason": "empty_text"})
            continue

        content_hash = hashlib.sha256(extracted_text.encode("utf-8")).hexdigest()
        if content_hash in content_hashes:
            rejected.append({"url": current_url, "reason": "duplicate_content"})
            continue
        content_hashes.add(content_hash)

        saved_html_path: str | None = None
        if source.output_format == "raw_html":
            html_path = paths.raw_html_root / f"{job_id}-{len(documents):03d}.html"
            html_path.parent.mkdir(parents=True, exist_ok=True)
            html_path.write_text(html_text, encoding="utf-8")
            saved_html_path = str(html_path)

        document = CrawlDocument(
            url=current_url,
            canonical_url=current_url,
            depth=depth,
            title=title,
            text=extracted_text,
            content_hash=content_hash,
            fetched_at=utc_now(),
            saved_html_path=saved_html_path,
        )
        documents.append(document)

        if depth < source.max_depth:
            for link in extract_links(current_url, html_text):
                if link in visited:
                    continue
                if not domain_allowed(link, source.allowed_domains, source.blocked_domains):
                    continue
                if pattern_blocked(link, source.exclude_patterns):
                    continue
                queue.append((link, depth + 1))

        sleep_ms(source.delay_between_requests_ms)

    raw_records = [
        {
            "url": item.url,
            "canonical_url": item.canonical_url,
            "depth": item.depth,
            "title": item.title,
            "text": item.text,
            "content_hash": item.content_hash,
            "fetched_at": item.fetched_at,
            "saved_html_path": item.saved_html_path,
        }
        for item in documents
    ]
    write_jsonl(raw_dir / "documents.jsonl", raw_records)
    write_json(raw_dir / "rejected.json", {"rejected": rejected, "generated_at": utc_now()})

    curated_records = [build_summary_record(doc, idx) for idx, doc in enumerate(documents)]
    train, val, test = split_records(
        curated_records,
        source.split_ratios.train,
        source.split_ratios.val,
    )
    train_path = curated_dir / "train.jsonl"
    val_path = curated_dir / "val.jsonl"
    test_path = curated_dir / "test.jsonl"
    write_jsonl(train_path, train)
    write_jsonl(val_path, val)
    write_jsonl(test_path, test)

    metadata = {
        "job_id": job_id,
        "manifest_path": str(manifest_path),
        "dataset_name": dataset_name,
        "created_at": utc_now(),
        "state": "curated",
        "documents_count": len(documents),
        "rejected_count": len(rejected),
        "raw_dir": str(raw_dir),
        "curated_dir": str(curated_dir),
        "train_file": str(train_path),
        "val_file": str(val_path),
        "test_file": str(test_path),
        "adapter": source.adapter,
    }
    write_json(paths.ingestion_dir / f"{job_id}.json", metadata)
    append_jsonl(paths.experiments_root / "ingestion_index.jsonl", metadata)

    return DatasetBundle(
        source_type="web_crawl",
        dataset_name=dataset_name,
        train_file=train_path,
        val_file=val_path,
        test_file=test_path,
        origin_manifest=manifest_path,
        raw_ingestion_id=job_id,
    )
