from __future__ import annotations

import hashlib
import io
import json
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse, urlunparse
from urllib.request import Request as UrlRequest, urlopen

from bs4 import BeautifulSoup
from pypdf import PdfReader
from sqlmodel import Session, select

from rag.common import RagChunk, RagPaths
from rag.vectorstore import query_collection, upsert_chunks

from .config import OrquestraSettings
from .models import (
    MemoryRecord,
    OsintCapture,
    OsintClaim,
    OsintConnectorConfig,
    OsintEntity,
    OsintEvidence,
    OsintInvestigation,
    OsintRun,
    OsintSource,
    OsintSourceRegistryEntry,
    RuntimeMetadata,
    utc_now,
)

OSINT_CONFIG_KEY = "osint_config"
OSINT_EVIDENCE_COLLECTION = "orquestra_osint_evidence_v1"
DEFAULT_TOR_PROXY_URL = "socks5h://127.0.0.1:9050"
OSINT_USER_AGENT = "OrquestraOSINT/0.3 (+local-first)"


def _safe_json(raw: str | None, fallback: Any) -> Any:
    try:
        return json.loads(raw or "")
    except Exception:
        return fallback


def _slugify(raw: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9]+", "-", raw).strip("-").lower()
    return normalized or "item"


def _tokens(text: str) -> set[str]:
    return {token for token in re.findall(r"[a-zA-Z0-9_À-ÿ-]{3,}", text.lower())}


def _lexical_score(query: str, *parts: str) -> float:
    query_tokens = _tokens(query)
    if not query_tokens:
        return 0.0
    haystack_tokens = _tokens(" ".join(parts))
    if not haystack_tokens:
        return 0.0
    return len(query_tokens & haystack_tokens) / max(len(query_tokens), 1)


def _canonical_url(raw_url: str) -> str:
    parsed = urlparse(raw_url.strip())
    if not parsed.scheme:
        return raw_url.strip()
    normalized = parsed._replace(fragment="")
    path = normalized.path or "/"
    normalized = normalized._replace(path=path.rstrip("/") or "/")
    return urlunparse(normalized)


def _credential_status(connector: OsintConnectorConfig) -> tuple[str, bool]:
    metadata = _safe_json(connector.metadata_json, {})
    secondary_env = str(metadata.get("secondary_credential_env") or "")
    primary_ready = bool(connector.credential_env and os.getenv(connector.credential_env))
    secondary_ready = bool(not secondary_env or os.getenv(secondary_env))
    if connector.requires_credential:
        if primary_ready and secondary_ready:
            return "configured", True
        return "missing", False
    if connector.credential_env and os.getenv(connector.credential_env):
        return "configured_optional", True
    return "not_required", True


def _effective_enabled(
    connector: OsintConnectorConfig,
    *,
    project_id: str | None = None,
    investigation: OsintInvestigation | None = None,
    selected_connector_ids: list[str] | None = None,
) -> bool:
    enabled = bool(connector.enabled_global and connector.enabled_by_default)
    overrides = _safe_json(connector.project_overrides_json, {})
    if project_id and isinstance(overrides, dict):
        raw_override = overrides.get(project_id)
        if isinstance(raw_override, dict):
            enabled = bool(raw_override.get("enabled", enabled))
        elif raw_override is not None:
            enabled = bool(raw_override)
    explicit_ids = selected_connector_ids or _safe_json(investigation.enabled_connector_ids_json, []) if investigation else selected_connector_ids
    if explicit_ids:
        enabled = enabled and connector.connector_id in explicit_ids
    return enabled


def _default_osint_config() -> dict[str, Any]:
    return {
        "search_timeout_seconds": 20,
        "fetch_timeout_seconds": 20,
        "default_max_results": 5,
        "default_fetch_limit": 2,
        "default_evidence_limit": 4,
        "tor_proxy_url": os.getenv("ORQUESTRA_OSINT_TOR_PROXY_URL", DEFAULT_TOR_PROXY_URL),
        "store_result_metadata": True,
        "store_full_provider_snippet": False,
    }


DEFAULT_CONNECTOR_DEFINITIONS: list[dict[str, Any]] = [
    {
        "connector_id": "brave",
        "label": "Brave Search",
        "category": "search_provider",
        "connector_kind": "search_provider",
        "description": "Busca web geral com índice próprio e resultados frescos.",
        "enabled_global": True,
        "enabled_by_default": True,
        "requires_credential": True,
        "credential_env": "BRAVE_SEARCH_API_KEY",
        "priority": 10,
        "allowed_modes_json": json.dumps(["search", "fresh_web"], ensure_ascii=False),
        "training_allowed": False,
        "retention_policy": "metadata_only",
        "via_tor_allowed": False,
        "metadata_json": json.dumps({"provider_group": "general_search"}, ensure_ascii=False),
    },
    {
        "connector_id": "tavily",
        "label": "Tavily",
        "category": "search_provider",
        "connector_kind": "search_provider",
        "description": "Busca com extração opcional de conteúdo estruturado.",
        "enabled_global": True,
        "enabled_by_default": False,
        "requires_credential": True,
        "credential_env": "TAVILY_API_KEY",
        "priority": 20,
        "allowed_modes_json": json.dumps(["search", "fresh_web", "extract"], ensure_ascii=False),
        "training_allowed": False,
        "retention_policy": "metadata_only",
        "via_tor_allowed": False,
        "metadata_json": json.dumps({"provider_group": "general_search"}, ensure_ascii=False),
    },
    {
        "connector_id": "exa",
        "label": "Exa",
        "category": "search_provider",
        "connector_kind": "search_provider",
        "description": "Busca semântica com highlights otimizados para RAG.",
        "enabled_global": True,
        "enabled_by_default": False,
        "requires_credential": True,
        "credential_env": "EXA_API_KEY",
        "priority": 30,
        "allowed_modes_json": json.dumps(["search", "fresh_web", "extract"], ensure_ascii=False),
        "training_allowed": False,
        "retention_policy": "metadata_only",
        "via_tor_allowed": False,
        "metadata_json": json.dumps({"provider_group": "general_search"}, ensure_ascii=False),
    },
    {
        "connector_id": "github",
        "label": "GitHub",
        "category": "repository",
        "connector_kind": "structured_public_api",
        "description": "Consulta repositórios públicos e código aberto via GitHub REST API.",
        "enabled_global": True,
        "enabled_by_default": True,
        "requires_credential": False,
        "credential_env": "GITHUB_TOKEN",
        "priority": 40,
        "allowed_modes_json": json.dumps(["search", "fetch"], ensure_ascii=False),
        "training_allowed": False,
        "retention_policy": "metadata_only",
        "via_tor_allowed": False,
        "metadata_json": json.dumps({"provider_group": "structured_source"}, ensure_ascii=False),
    },
    {
        "connector_id": "wikidata",
        "label": "Wikidata",
        "category": "structured_public_api",
        "connector_kind": "structured_public_api",
        "description": "Pesquisa entidades abertas com o Action API do Wikidata.",
        "enabled_global": True,
        "enabled_by_default": True,
        "requires_credential": False,
        "credential_env": None,
        "priority": 45,
        "allowed_modes_json": json.dumps(["search", "fetch"], ensure_ascii=False),
        "training_allowed": False,
        "retention_policy": "metadata_only",
        "via_tor_allowed": False,
        "metadata_json": json.dumps({"provider_group": "structured_source"}, ensure_ascii=False),
    },
    {
        "connector_id": "sec",
        "label": "SEC EDGAR",
        "category": "structured_public_api",
        "connector_kind": "structured_public_api",
        "description": "Acessa CIK, company facts e histórico de submissões públicas da SEC.",
        "enabled_global": True,
        "enabled_by_default": True,
        "requires_credential": False,
        "credential_env": None,
        "priority": 50,
        "allowed_modes_json": json.dumps(["search", "fetch"], ensure_ascii=False),
        "training_allowed": False,
        "retention_policy": "metadata_only",
        "via_tor_allowed": False,
        "metadata_json": json.dumps({"provider_group": "structured_source"}, ensure_ascii=False),
    },
    {
        "connector_id": "internet_archive",
        "label": "Internet Archive",
        "category": "archive",
        "connector_kind": "structured_public_api",
        "description": "Pesquisa acervos e documentos via advancedsearch.",
        "enabled_global": True,
        "enabled_by_default": True,
        "requires_credential": False,
        "credential_env": None,
        "priority": 55,
        "allowed_modes_json": json.dumps(["search", "fetch"], ensure_ascii=False),
        "training_allowed": False,
        "retention_policy": "metadata_only",
        "via_tor_allowed": False,
        "metadata_json": json.dumps({"provider_group": "archive"}, ensure_ascii=False),
    },
    {
        "connector_id": "cisa_kev",
        "label": "CISA KEV",
        "category": "threat_intel",
        "connector_kind": "structured_public_api",
        "description": "Catálogo de vulnerabilidades exploradas em ambiente real.",
        "enabled_global": True,
        "enabled_by_default": True,
        "requires_credential": False,
        "credential_env": None,
        "priority": 60,
        "allowed_modes_json": json.dumps(["search"], ensure_ascii=False),
        "training_allowed": False,
        "retention_policy": "metadata_only",
        "via_tor_allowed": False,
        "metadata_json": json.dumps({"provider_group": "threat_intel"}, ensure_ascii=False),
    },
    {
        "connector_id": "nvd",
        "label": "NVD CVE",
        "category": "threat_intel",
        "connector_kind": "structured_public_api",
        "description": "Busca CVEs e descrições oficiais no NVD.",
        "enabled_global": True,
        "enabled_by_default": True,
        "requires_credential": False,
        "credential_env": "NVD_API_KEY",
        "priority": 70,
        "allowed_modes_json": json.dumps(["search"], ensure_ascii=False),
        "training_allowed": False,
        "retention_policy": "metadata_only",
        "via_tor_allowed": False,
        "metadata_json": json.dumps({"provider_group": "threat_intel"}, ensure_ascii=False),
    },
    {
        "connector_id": "youtube",
        "label": "YouTube Data API",
        "category": "media",
        "connector_kind": "structured_public_api",
        "description": "Pesquisa vídeos e canais públicos quando houver chave configurada.",
        "enabled_global": True,
        "enabled_by_default": False,
        "requires_credential": True,
        "credential_env": "YOUTUBE_API_KEY",
        "priority": 80,
        "allowed_modes_json": json.dumps(["search"], ensure_ascii=False),
        "training_allowed": False,
        "retention_policy": "metadata_only",
        "via_tor_allowed": False,
        "metadata_json": json.dumps({"provider_group": "media"}, ensure_ascii=False),
    },
    {
        "connector_id": "shodan",
        "label": "Shodan",
        "category": "threat_intel",
        "connector_kind": "structured_public_api",
        "description": "Attack surface e serviços expostos com chave própria.",
        "enabled_global": True,
        "enabled_by_default": False,
        "requires_credential": True,
        "credential_env": "SHODAN_API_KEY",
        "priority": 90,
        "allowed_modes_json": json.dumps(["search"], ensure_ascii=False),
        "training_allowed": False,
        "retention_policy": "metadata_only",
        "via_tor_allowed": False,
        "metadata_json": json.dumps({"provider_group": "threat_intel"}, ensure_ascii=False),
    },
    {
        "connector_id": "censys",
        "label": "Censys",
        "category": "threat_intel",
        "connector_kind": "structured_public_api",
        "description": "Conector administrável para Censys; fica desligado até haver credenciais.",
        "enabled_global": True,
        "enabled_by_default": False,
        "requires_credential": True,
        "credential_env": "CENSYS_API_ID",
        "priority": 100,
        "allowed_modes_json": json.dumps(["search"], ensure_ascii=False),
        "training_allowed": False,
        "retention_policy": "metadata_only",
        "via_tor_allowed": False,
        "metadata_json": json.dumps({"provider_group": "threat_intel", "secondary_credential_env": "CENSYS_API_SECRET"}, ensure_ascii=False),
    },
    {
        "connector_id": "reddit",
        "label": "Reddit",
        "category": "conditional_adapter",
        "connector_kind": "conditional_adapter",
        "description": "Adapter condicional, desligado por padrão até existir credencial e política explícita.",
        "enabled_global": True,
        "enabled_by_default": False,
        "requires_credential": True,
        "credential_env": "REDDIT_CLIENT_ID",
        "priority": 110,
        "allowed_modes_json": json.dumps(["search"], ensure_ascii=False),
        "training_allowed": False,
        "retention_policy": "metadata_only",
        "via_tor_allowed": False,
        "metadata_json": json.dumps({"provider_group": "community", "secondary_credential_env": "REDDIT_CLIENT_SECRET"}, ensure_ascii=False),
    },
    {
        "connector_id": "onion_manual",
        "label": "Tor Manual Seeds",
        "category": "darkweb_seed",
        "connector_kind": "manual_seed",
        "description": "Seeds e bookmarks .onion administráveis, acessados via fetch com Tor quando habilitado.",
        "enabled_global": True,
        "enabled_by_default": False,
        "requires_credential": False,
        "credential_env": None,
        "priority": 120,
        "allowed_modes_json": json.dumps(["fetch", "crawl"], ensure_ascii=False),
        "training_allowed": False,
        "retention_policy": "metadata_only",
        "via_tor_allowed": True,
        "metadata_json": json.dumps({"provider_group": "darkweb"}, ensure_ascii=False),
    },
]

DEFAULT_SOURCE_REGISTRY: list[dict[str, Any]] = [
    {
        "source_key": "brave-search-api",
        "connector_id": "brave",
        "title": "Brave Search API",
        "category": "search_provider",
        "access_type": "api",
        "base_url": "https://api.search.brave.com/res/v1/web/search",
        "description": "Busca web geral com índice próprio.",
        "retention_policy": "metadata_only",
        "training_allowed": False,
        "reliability": 0.8,
        "preset_tags_json": json.dumps(["research", "osint"], ensure_ascii=False),
        "jurisdiction_tags_json": json.dumps(["global"], ensure_ascii=False),
        "tor_supported": False,
        "api_auth_required": True,
        "robots_sensitive": False,
        "metadata_json": json.dumps({"docs_url": "https://brave.com/search/api/"}, ensure_ascii=False),
    },
    {
        "source_key": "tavily-search",
        "connector_id": "tavily",
        "title": "Tavily Search API",
        "category": "search_provider",
        "access_type": "api",
        "base_url": "https://api.tavily.com/search",
        "description": "Busca com extração opcional e filtros por domínio.",
        "retention_policy": "metadata_only",
        "training_allowed": False,
        "reliability": 0.78,
        "preset_tags_json": json.dumps(["research", "osint"], ensure_ascii=False),
        "jurisdiction_tags_json": json.dumps(["global"], ensure_ascii=False),
        "tor_supported": False,
        "api_auth_required": True,
        "robots_sensitive": False,
        "metadata_json": json.dumps({"docs_url": "https://docs.tavily.com/documentation/api-reference/endpoint/search"}, ensure_ascii=False),
    },
    {
        "source_key": "exa-search",
        "connector_id": "exa",
        "title": "Exa Search API",
        "category": "search_provider",
        "access_type": "api",
        "base_url": "https://api.exa.ai/search",
        "description": "Busca semântica com highlights e contents integrados.",
        "retention_policy": "metadata_only",
        "training_allowed": False,
        "reliability": 0.76,
        "preset_tags_json": json.dumps(["research", "osint"], ensure_ascii=False),
        "jurisdiction_tags_json": json.dumps(["global"], ensure_ascii=False),
        "tor_supported": False,
        "api_auth_required": True,
        "robots_sensitive": False,
        "metadata_json": json.dumps({"docs_url": "https://exa.ai/docs/reference/search"}, ensure_ascii=False),
    },
    {
        "source_key": "github-rest",
        "connector_id": "github",
        "title": "GitHub REST API",
        "category": "repository",
        "access_type": "api",
        "base_url": "https://api.github.com/search/repositories",
        "description": "Busca repositórios públicos e metadados técnicos.",
        "retention_policy": "metadata_only",
        "training_allowed": False,
        "reliability": 0.85,
        "preset_tags_json": json.dumps(["research", "osint"], ensure_ascii=False),
        "jurisdiction_tags_json": json.dumps(["global"], ensure_ascii=False),
        "tor_supported": False,
        "api_auth_required": False,
        "robots_sensitive": False,
        "metadata_json": json.dumps({"docs_url": "https://docs.github.com/en/rest"}, ensure_ascii=False),
    },
    {
        "source_key": "wikidata-api",
        "connector_id": "wikidata",
        "title": "Wikidata Action API",
        "category": "structured_public_api",
        "access_type": "api",
        "base_url": "https://www.wikidata.org/w/api.php",
        "description": "Busca entidades públicas e identificadores abertos.",
        "retention_policy": "metadata_only",
        "training_allowed": False,
        "reliability": 0.74,
        "preset_tags_json": json.dumps(["research", "osint"], ensure_ascii=False),
        "jurisdiction_tags_json": json.dumps(["global"], ensure_ascii=False),
        "tor_supported": False,
        "api_auth_required": False,
        "robots_sensitive": False,
        "metadata_json": json.dumps({"docs_url": "https://www.wikidata.org/wiki/Wikidata:Data_access"}, ensure_ascii=False),
    },
    {
        "source_key": "sec-edgar-company-tickers",
        "connector_id": "sec",
        "title": "SEC Company Tickers",
        "category": "structured_public_api",
        "access_type": "api",
        "base_url": "https://www.sec.gov/files/company_tickers_exchange.json",
        "description": "Mapa de ticker, exchange e CIK para busca em filings.",
        "retention_policy": "metadata_only",
        "training_allowed": False,
        "reliability": 0.88,
        "preset_tags_json": json.dumps(["research", "osint"], ensure_ascii=False),
        "jurisdiction_tags_json": json.dumps(["us"], ensure_ascii=False),
        "tor_supported": False,
        "api_auth_required": False,
        "robots_sensitive": True,
        "metadata_json": json.dumps({"docs_url": "https://www.sec.gov/search-filings/edgar-application-programming-interfaces"}, ensure_ascii=False),
    },
    {
        "source_key": "internet-archive-advancedsearch",
        "connector_id": "internet_archive",
        "title": "Internet Archive Advanced Search",
        "category": "archive",
        "access_type": "api",
        "base_url": "https://archive.org/advancedsearch.php",
        "description": "Pesquisa acervos digitais e documentos históricos.",
        "retention_policy": "metadata_only",
        "training_allowed": False,
        "reliability": 0.7,
        "preset_tags_json": json.dumps(["research", "osint"], ensure_ascii=False),
        "jurisdiction_tags_json": json.dumps(["global"], ensure_ascii=False),
        "tor_supported": False,
        "api_auth_required": False,
        "robots_sensitive": False,
        "metadata_json": json.dumps({"docs_url": "https://archive.org/developers/"}, ensure_ascii=False),
    },
    {
        "source_key": "cisa-kev-json",
        "connector_id": "cisa_kev",
        "title": "CISA KEV Catalog",
        "category": "threat_intel",
        "access_type": "json",
        "base_url": "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json",
        "description": "Feed JSON do catálogo de vulnerabilidades exploradas em ambiente real.",
        "retention_policy": "metadata_only",
        "training_allowed": False,
        "reliability": 0.92,
        "preset_tags_json": json.dumps(["osint", "research"], ensure_ascii=False),
        "jurisdiction_tags_json": json.dumps(["us", "global"], ensure_ascii=False),
        "tor_supported": False,
        "api_auth_required": False,
        "robots_sensitive": False,
        "metadata_json": json.dumps({"docs_url": "https://www.cisa.gov/known-exploited-vulnerabilities-catalog"}, ensure_ascii=False),
    },
    {
        "source_key": "nvd-cves-api",
        "connector_id": "nvd",
        "title": "NVD CVE API",
        "category": "threat_intel",
        "access_type": "api",
        "base_url": "https://services.nvd.nist.gov/rest/json/cves/2.0",
        "description": "Busca CVEs e descrições associadas no NVD.",
        "retention_policy": "metadata_only",
        "training_allowed": False,
        "reliability": 0.9,
        "preset_tags_json": json.dumps(["osint", "research"], ensure_ascii=False),
        "jurisdiction_tags_json": json.dumps(["global"], ensure_ascii=False),
        "tor_supported": False,
        "api_auth_required": False,
        "robots_sensitive": False,
        "metadata_json": json.dumps({"docs_url": "https://nvd.nist.gov/developers/vulnerabilities"}, ensure_ascii=False),
    },
    {
        "source_key": "youtube-search",
        "connector_id": "youtube",
        "title": "YouTube Data API Search",
        "category": "media",
        "access_type": "api",
        "base_url": "https://www.googleapis.com/youtube/v3/search",
        "description": "Pesquisa vídeos e canais públicos.",
        "retention_policy": "metadata_only",
        "training_allowed": False,
        "reliability": 0.72,
        "preset_tags_json": json.dumps(["research", "osint"], ensure_ascii=False),
        "jurisdiction_tags_json": json.dumps(["global"], ensure_ascii=False),
        "tor_supported": False,
        "api_auth_required": True,
        "robots_sensitive": False,
        "metadata_json": json.dumps({"docs_url": "https://developers.google.com/youtube/v3/docs/search"}, ensure_ascii=False),
    },
    {
        "source_key": "shodan-host-search",
        "connector_id": "shodan",
        "title": "Shodan Host Search",
        "category": "threat_intel",
        "access_type": "api",
        "base_url": "https://api.shodan.io/shodan/host/search",
        "description": "Pesquisa infraestrutura exposta com chave própria.",
        "retention_policy": "metadata_only",
        "training_allowed": False,
        "reliability": 0.85,
        "preset_tags_json": json.dumps(["osint"], ensure_ascii=False),
        "jurisdiction_tags_json": json.dumps(["global"], ensure_ascii=False),
        "tor_supported": False,
        "api_auth_required": True,
        "robots_sensitive": False,
        "metadata_json": json.dumps({"docs_url": "https://developer.shodan.io/api"}, ensure_ascii=False),
    },
]


@dataclass
class OsintPaths:
    root: Path

    def ensure(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)

    def investigation_root(self, investigation_id: str) -> Path:
        return self.root / "investigations" / _slugify(investigation_id)

    def runs_dir(self, investigation_id: str) -> Path:
        return self.investigation_root(investigation_id) / "runs"

    def sources_dir(self, investigation_id: str) -> Path:
        return self.investigation_root(investigation_id) / "sources"

    def captures_dir(self, investigation_id: str) -> Path:
        return self.investigation_root(investigation_id) / "captures"

    def evidence_dir(self, investigation_id: str) -> Path:
        return self.investigation_root(investigation_id) / "evidence"

    def claims_dir(self, investigation_id: str) -> Path:
        return self.investigation_root(investigation_id) / "claims"

    def exports_dir(self, investigation_id: str) -> Path:
        return self.investigation_root(investigation_id) / "exports"

    def ensure_investigation(self, investigation_id: str) -> None:
        for path in (
            self.investigation_root(investigation_id),
            self.runs_dir(investigation_id),
            self.sources_dir(investigation_id),
            self.captures_dir(investigation_id),
            self.evidence_dir(investigation_id),
            self.claims_dir(investigation_id),
            self.exports_dir(investigation_id),
        ):
            path.mkdir(parents=True, exist_ok=True)


def get_osint_config(session: Session) -> dict[str, Any]:
    record = session.get(RuntimeMetadata, OSINT_CONFIG_KEY)
    stored = _safe_json(record.value if record else "", {})
    return {**_default_osint_config(), **(stored if isinstance(stored, dict) else {})}


def save_osint_config(session: Session, payload: dict[str, Any]) -> dict[str, Any]:
    merged = {**get_osint_config(session), **payload}
    record = session.get(RuntimeMetadata, OSINT_CONFIG_KEY)
    if record is None:
        record = RuntimeMetadata(key=OSINT_CONFIG_KEY, value=json.dumps(merged, ensure_ascii=False))
    else:
        record.value = json.dumps(merged, ensure_ascii=False)
        record.updated_at = utc_now()
    session.add(record)
    return merged


def seed_osint_state(session: Session) -> None:
    for payload in DEFAULT_CONNECTOR_DEFINITIONS:
        record = session.get(OsintConnectorConfig, payload["connector_id"])
        if record is None:
            record = OsintConnectorConfig(**payload)
            session.add(record)
            continue
        record.label = payload["label"]
        record.category = payload["category"]
        record.connector_kind = payload["connector_kind"]
        record.description = payload["description"]
        record.requires_credential = payload["requires_credential"]
        record.credential_env = payload["credential_env"]
        record.priority = payload["priority"]
        record.allowed_modes_json = payload["allowed_modes_json"]
        record.training_allowed = payload["training_allowed"]
        record.retention_policy = payload["retention_policy"]
        record.via_tor_allowed = payload["via_tor_allowed"]
        record.metadata_json = payload["metadata_json"]
        record.updated_at = utc_now()
        session.add(record)

    for payload in DEFAULT_SOURCE_REGISTRY:
        existing = session.exec(
            select(OsintSourceRegistryEntry).where(OsintSourceRegistryEntry.source_key == payload["source_key"])
        ).first()
        if existing is None:
            session.add(OsintSourceRegistryEntry(**payload))
            continue
        existing.connector_id = payload["connector_id"]
        existing.title = payload["title"]
        existing.category = payload["category"]
        existing.access_type = payload["access_type"]
        existing.base_url = payload["base_url"]
        existing.description = payload["description"]
        existing.retention_policy = payload["retention_policy"]
        existing.training_allowed = payload["training_allowed"]
        existing.reliability = payload["reliability"]
        existing.jurisdiction_tags_json = payload["jurisdiction_tags_json"]
        existing.preset_tags_json = payload["preset_tags_json"]
        existing.tor_supported = payload["tor_supported"]
        existing.api_auth_required = payload["api_auth_required"]
        existing.robots_sensitive = payload["robots_sensitive"]
        existing.metadata_json = payload["metadata_json"]
        existing.updated_at = utc_now()
        session.add(existing)

    save_osint_config(session, {})


class OsintService:
    def __init__(self, settings: OrquestraSettings) -> None:
        self.settings = settings
        self.paths = OsintPaths(settings.artifacts_root / "osint")
        self.paths.ensure()
        self.rag_paths = RagPaths.load(settings.workspace_root)

    def list_connectors(
        self,
        session: Session,
        *,
        project_id: str | None = None,
        investigation_id: str | None = None,
        selected_connector_ids: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        investigation = session.get(OsintInvestigation, investigation_id) if investigation_id else None
        rows = session.exec(select(OsintConnectorConfig).order_by(OsintConnectorConfig.priority, OsintConnectorConfig.connector_id)).all()
        return [
            self.connector_to_dict(
                row,
                project_id=project_id,
                investigation=investigation,
                selected_connector_ids=selected_connector_ids,
            )
            for row in rows
        ]

    def connector_to_dict(
        self,
        row: OsintConnectorConfig,
        *,
        project_id: str | None = None,
        investigation: OsintInvestigation | None = None,
        selected_connector_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        credential_status, ready_for_creds = _credential_status(row)
        metadata = _safe_json(row.metadata_json, {})
        health_status = metadata.get("cooldown_until") and "cooldown" or row.health_status
        effective_enabled = _effective_enabled(
            row,
            project_id=project_id,
            investigation=investigation,
            selected_connector_ids=selected_connector_ids,
        )
        ready = bool(effective_enabled and ready_for_creds and health_status not in {"cooldown", "offline"})
        return {
            "connector_id": row.connector_id,
            "label": row.label,
            "category": row.category,
            "connector_kind": row.connector_kind,
            "status": "ready" if ready else "configured_but_unavailable" if effective_enabled else "disabled",
            "description": row.description,
            "enabled_global": row.enabled_global,
            "enabled_by_default": row.enabled_by_default,
            "effective_enabled": effective_enabled,
            "requires_credential": row.requires_credential,
            "credential_env": row.credential_env,
            "credential_status": credential_status,
            "priority": row.priority,
            "health_status": health_status,
            "allowed_modes": _safe_json(row.allowed_modes_json, []),
            "training_allowed": row.training_allowed,
            "retention_policy": row.retention_policy,
            "via_tor_allowed": row.via_tor_allowed,
            "project_overrides": _safe_json(row.project_overrides_json, {}),
            "metadata": metadata,
            "ready": ready,
        }

    def update_connector(
        self,
        session: Session,
        connector_id: str,
        *,
        enabled_global: bool | None = None,
        enabled_by_default: bool | None = None,
        priority: int | None = None,
        training_allowed: bool | None = None,
        retention_policy: str | None = None,
        via_tor_allowed: bool | None = None,
        health_status: str | None = None,
        project_overrides: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        row = session.get(OsintConnectorConfig, connector_id)
        if row is None:
            raise KeyError(connector_id)
        if enabled_global is not None:
            row.enabled_global = enabled_global
        if enabled_by_default is not None:
            row.enabled_by_default = enabled_by_default
        if priority is not None:
            row.priority = priority
        if training_allowed is not None:
            row.training_allowed = training_allowed
        if retention_policy is not None:
            row.retention_policy = retention_policy
        if via_tor_allowed is not None:
            row.via_tor_allowed = via_tor_allowed
        if health_status is not None:
            row.health_status = health_status
        if project_overrides is not None:
            row.project_overrides_json = json.dumps(project_overrides, ensure_ascii=False)
        if metadata is not None:
            current_metadata = _safe_json(row.metadata_json, {})
            row.metadata_json = json.dumps(current_metadata | metadata, ensure_ascii=False)
        row.updated_at = utc_now()
        session.add(row)
        return self.connector_to_dict(row)

    def list_registry(self, session: Session) -> list[dict[str, Any]]:
        rows = session.exec(select(OsintSourceRegistryEntry).order_by(OsintSourceRegistryEntry.category, OsintSourceRegistryEntry.title)).all()
        return [self.registry_to_dict(row) for row in rows]

    def registry_to_dict(self, row: OsintSourceRegistryEntry) -> dict[str, Any]:
        return {
            "id": row.id,
            "source_key": row.source_key,
            "connector_id": row.connector_id,
            "title": row.title,
            "category": row.category,
            "access_type": row.access_type,
            "base_url": row.base_url,
            "description": row.description,
            "retention_policy": row.retention_policy,
            "training_allowed": row.training_allowed,
            "reliability": row.reliability,
            "jurisdiction_tags": _safe_json(row.jurisdiction_tags_json, []),
            "preset_tags": _safe_json(row.preset_tags_json, []),
            "tor_supported": row.tor_supported,
            "api_auth_required": row.api_auth_required,
            "robots_sensitive": row.robots_sensitive,
            "metadata": _safe_json(row.metadata_json, {}),
            "created_at": row.created_at.isoformat(),
            "updated_at": row.updated_at.isoformat(),
        }

    def upsert_registry_entry(self, session: Session, payload: dict[str, Any]) -> dict[str, Any]:
        source_key = str(payload.get("source_key") or "").strip()
        if not source_key:
            raise ValueError("source_key é obrigatório")
        row = session.exec(select(OsintSourceRegistryEntry).where(OsintSourceRegistryEntry.source_key == source_key)).first()
        if row is None:
            row = OsintSourceRegistryEntry(source_key=source_key, title=str(payload.get("title") or source_key), category=str(payload.get("category") or "manual_seed"))
        row.connector_id = payload.get("connector_id")
        row.title = str(payload.get("title") or row.title)
        row.category = str(payload.get("category") or row.category)
        row.access_type = str(payload.get("access_type") or row.access_type)
        row.base_url = str(payload.get("base_url") or row.base_url)
        row.description = str(payload.get("description") or row.description)
        row.retention_policy = str(payload.get("retention_policy") or row.retention_policy)
        row.training_allowed = bool(payload.get("training_allowed", row.training_allowed))
        row.reliability = float(payload.get("reliability", row.reliability))
        row.jurisdiction_tags_json = json.dumps(payload.get("jurisdiction_tags", _safe_json(row.jurisdiction_tags_json, [])), ensure_ascii=False)
        row.preset_tags_json = json.dumps(payload.get("preset_tags", _safe_json(row.preset_tags_json, [])), ensure_ascii=False)
        row.tor_supported = bool(payload.get("tor_supported", row.tor_supported))
        row.api_auth_required = bool(payload.get("api_auth_required", row.api_auth_required))
        row.robots_sensitive = bool(payload.get("robots_sensitive", row.robots_sensitive))
        row.metadata_json = json.dumps(payload.get("metadata", _safe_json(row.metadata_json, {})), ensure_ascii=False)
        row.updated_at = utc_now()
        session.add(row)
        session.flush()
        return self.registry_to_dict(row)

    def list_investigations(self, session: Session, *, project_id: str | None = None, session_id: str | None = None) -> list[dict[str, Any]]:
        statement = select(OsintInvestigation).order_by(OsintInvestigation.updated_at.desc())
        if project_id:
            statement = statement.where(OsintInvestigation.project_id == project_id)
        if session_id:
            statement = statement.where(OsintInvestigation.session_id == session_id)
        rows = session.exec(statement.limit(100)).all()
        return [self.investigation_to_dict(row) for row in rows]

    def investigation_to_dict(self, row: OsintInvestigation) -> dict[str, Any]:
        return {
            "id": row.id,
            "project_id": row.project_id,
            "session_id": row.session_id,
            "title": row.title,
            "objective": row.objective,
            "target_entity": row.target_entity,
            "language": row.language,
            "jurisdiction": row.jurisdiction,
            "mode": row.mode,
            "status": row.status,
            "enabled_connector_ids": _safe_json(row.enabled_connector_ids_json, []),
            "source_registry_ids": _safe_json(row.source_registry_ids_json, []),
            "allowed_domains": _safe_json(row.allowed_domains_json, []),
            "blocked_domains": _safe_json(row.blocked_domains_json, []),
            "metadata": _safe_json(row.metadata_json, {}),
            "created_at": row.created_at.isoformat(),
            "updated_at": row.updated_at.isoformat(),
        }

    def create_investigation(
        self,
        session: Session,
        *,
        project_id: str | None = None,
        session_id: str | None = None,
        title: str,
        objective: str = "",
        target_entity: str = "",
        language: str = "pt-BR",
        jurisdiction: str = "global",
        mode: str = "balanced",
        enabled_connector_ids: list[str] | None = None,
        source_registry_ids: list[str] | None = None,
        allowed_domains: list[str] | None = None,
        blocked_domains: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        row = OsintInvestigation(
            project_id=project_id,
            session_id=session_id,
            title=title.strip() or target_entity.strip() or "Investigation",
            objective=objective.strip(),
            target_entity=target_entity.strip(),
            language=language.strip() or "pt-BR",
            jurisdiction=jurisdiction.strip() or "global",
            mode=mode.strip() or "balanced",
            enabled_connector_ids_json=json.dumps(enabled_connector_ids or [], ensure_ascii=False),
            source_registry_ids_json=json.dumps(source_registry_ids or [], ensure_ascii=False),
            allowed_domains_json=json.dumps(allowed_domains or [], ensure_ascii=False),
            blocked_domains_json=json.dumps(blocked_domains or [], ensure_ascii=False),
            metadata_json=json.dumps(metadata or {}, ensure_ascii=False),
        )
        session.add(row)
        session.flush()
        self.paths.ensure_investigation(row.id)
        return self.investigation_to_dict(row)

    def update_investigation(self, session: Session, investigation_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        row = session.get(OsintInvestigation, investigation_id)
        if row is None:
            raise KeyError(investigation_id)
        for field in ("title", "objective", "target_entity", "language", "jurisdiction", "mode", "status"):
            if field in payload and payload[field] is not None:
                setattr(row, field, str(payload[field]))
        if "enabled_connector_ids" in payload:
            row.enabled_connector_ids_json = json.dumps(payload["enabled_connector_ids"] or [], ensure_ascii=False)
        if "source_registry_ids" in payload:
            row.source_registry_ids_json = json.dumps(payload["source_registry_ids"] or [], ensure_ascii=False)
        if "allowed_domains" in payload:
            row.allowed_domains_json = json.dumps(payload["allowed_domains"] or [], ensure_ascii=False)
        if "blocked_domains" in payload:
            row.blocked_domains_json = json.dumps(payload["blocked_domains"] or [], ensure_ascii=False)
        if "metadata" in payload:
            row.metadata_json = json.dumps(payload["metadata"] or {}, ensure_ascii=False)
        row.updated_at = utc_now()
        session.add(row)
        self.paths.ensure_investigation(row.id)
        return self.investigation_to_dict(row)

    def ensure_session_investigation(
        self,
        session: Session,
        *,
        session_id: str | None,
        project_id: str | None,
        objective: str,
        connector_ids: list[str] | None = None,
    ) -> OsintInvestigation:
        if session_id:
            row = session.exec(
                select(OsintInvestigation)
                .where(OsintInvestigation.session_id == session_id)
                .where(OsintInvestigation.status == "active")
                .order_by(OsintInvestigation.updated_at.desc())
            ).first()
            if row is not None:
                return row
        payload = self.create_investigation(
            session,
            project_id=project_id,
            session_id=session_id,
            title=_truncate_text(objective or "Investigação OSINT", 80),
            objective=objective,
            enabled_connector_ids=connector_ids or [],
            metadata={"auto_created_from_chat": True},
        )
        row = session.get(OsintInvestigation, payload["id"])
        if row is None:
            raise RuntimeError("Falha ao criar investigação automática")
        return row

    def plan_queries(
        self,
        session: Session,
        investigation_id: str,
        *,
        query: str | None = None,
    ) -> dict[str, Any]:
        row = session.get(OsintInvestigation, investigation_id)
        if row is None:
            raise KeyError(investigation_id)
        base_query = (query or row.target_entity or row.objective or row.title).strip()
        variants: list[str] = []
        if base_query:
            variants.append(base_query)
            variants.append(f'"{base_query}"')
            variants.append(f"{base_query} site:github.com")
            variants.append(f"{base_query} filetype:pdf")
            if row.jurisdiction and row.jurisdiction != "global":
                variants.append(f"{base_query} {row.jurisdiction}")
        unique_queries = []
        seen: set[str] = set()
        for item in variants:
            normalized = item.strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            unique_queries.append(normalized)
        metadata = _safe_json(row.metadata_json, {})
        metadata["query_plan"] = unique_queries
        row.metadata_json = json.dumps(metadata, ensure_ascii=False)
        row.updated_at = utc_now()
        session.add(row)
        return {"investigation": self.investigation_to_dict(row), "queries": unique_queries}

    def _record_run(
        self,
        session: Session,
        *,
        investigation: OsintInvestigation,
        run_kind: str,
        query: str = "",
        connector_ids: list[str] | None = None,
        via_tor: bool = False,
        metadata: dict[str, Any] | None = None,
    ) -> OsintRun:
        self.paths.ensure_investigation(investigation.id)
        log_path = self.paths.runs_dir(investigation.id) / f"{utc_now().strftime('%Y%m%d-%H%M%S')}-{run_kind}.json"
        run = OsintRun(
            investigation_id=investigation.id,
            run_kind=run_kind,
            status="running",
            query=query,
            connector_ids_json=json.dumps(connector_ids or [], ensure_ascii=False),
            via_tor=via_tor,
            log_path=str(log_path),
            metadata_json=json.dumps(metadata or {}, ensure_ascii=False),
        )
        session.add(run)
        session.flush()
        return run

    def _finish_run(self, run: OsintRun, *, status: str, payload: dict[str, Any]) -> None:
        run.status = status
        run.updated_at = utc_now()
        Path(run.log_path).parent.mkdir(parents=True, exist_ok=True)
        Path(run.log_path).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def _http_json(
        self,
        url: str,
        *,
        method: str = "GET",
        headers: dict[str, str] | None = None,
        body: dict[str, Any] | None = None,
        timeout: int = 20,
    ) -> dict[str, Any]:
        payload = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
        request_headers = {"User-Agent": OSINT_USER_AGENT, **(headers or {})}
        request = UrlRequest(url, data=payload, headers=request_headers, method=method.upper())
        if payload is not None:
            request.add_header("Content-Type", "application/json")
        with urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))

    def _http_bytes(
        self,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        timeout: int = 20,
    ) -> tuple[bytes, dict[str, str]]:
        request_headers = {"User-Agent": OSINT_USER_AGENT, **(headers or {})}
        request = UrlRequest(url, headers=request_headers)
        with urlopen(request, timeout=timeout) as response:
            raw = response.read()
            headers_map = {key.lower(): value for key, value in response.headers.items()}
            return raw, headers_map

    def _search_brave(self, query: str, *, connector: OsintConnectorConfig, limit: int, language: str, country: str) -> list[dict[str, Any]]:
        api_key = os.getenv(connector.credential_env or "")
        if not api_key:
            return []
        params = urlencode(
            {
                "q": query,
                "count": min(max(limit, 1), 10),
                "search_lang": (language or "en")[:2],
                "country": (country or "US")[:2].upper(),
                "extra_snippets": "true",
                "safesearch": "moderate",
            }
        )
        payload = self._http_json(
            f"https://api.search.brave.com/res/v1/web/search?{params}",
            headers={"X-Subscription-Token": api_key},
            timeout=20,
        )
        results = payload.get("web", {}).get("results", []) if isinstance(payload, dict) else []
        return [
            {
                "title": item.get("title") or item.get("url") or "Brave result",
                "url": item.get("url", ""),
                "snippet": " ".join(
                    part for part in [item.get("description", ""), *item.get("extra_snippets", [])[:2]] if isinstance(part, str) and part.strip()
                ).strip(),
                "provider": "brave",
                "rank": index,
            }
            for index, item in enumerate(results)
            if item.get("url")
        ]

    def _search_tavily(self, query: str, *, connector: OsintConnectorConfig, limit: int) -> list[dict[str, Any]]:
        api_key = os.getenv(connector.credential_env or "")
        if not api_key:
            return []
        payload = self._http_json(
            "https://api.tavily.com/search",
            method="POST",
            headers={"Authorization": f"Bearer {api_key}"},
            body={
                "query": query,
                "search_depth": "basic",
                "max_results": min(max(limit, 1), 10),
                "include_answer": False,
                "include_raw_content": False,
                "include_favicon": True,
            },
            timeout=20,
        )
        results = payload.get("results", []) if isinstance(payload, dict) else []
        return [
            {
                "title": item.get("title") or item.get("url") or "Tavily result",
                "url": item.get("url", ""),
                "snippet": item.get("content", "") or item.get("snippet", ""),
                "provider": "tavily",
                "rank": index,
            }
            for index, item in enumerate(results)
            if item.get("url")
        ]

    def _search_exa(self, query: str, *, connector: OsintConnectorConfig, limit: int) -> list[dict[str, Any]]:
        api_key = os.getenv(connector.credential_env or "")
        if not api_key:
            return []
        payload = self._http_json(
            "https://api.exa.ai/search",
            method="POST",
            headers={"x-api-key": api_key},
            body={
                "query": query,
                "numResults": min(max(limit, 1), 10),
                "contents": {"highlights": {"maxCharacters": 900}},
            },
            timeout=20,
        )
        results = payload.get("results", []) if isinstance(payload, dict) else []
        return [
            {
                "title": item.get("title") or item.get("url") or "Exa result",
                "url": item.get("url", ""),
                "snippet": (
                    item.get("highlights") and " ".join(item.get("highlights", [])[:2])
                )
                or item.get("text", "")
                or "",
                "provider": "exa",
                "rank": index,
            }
            for index, item in enumerate(results)
            if item.get("url")
        ]

    def _search_github(self, query: str, *, connector: OsintConnectorConfig, limit: int) -> list[dict[str, Any]]:
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        token = os.getenv(connector.credential_env or "")
        if token:
            headers["Authorization"] = f"Bearer {token}"
        params = urlencode({"q": query, "per_page": min(max(limit, 1), 10), "sort": "updated"})
        payload = self._http_json(f"https://api.github.com/search/repositories?{params}", headers=headers, timeout=20)
        items = payload.get("items", []) if isinstance(payload, dict) else []
        return [
            {
                "title": item.get("full_name") or item.get("name") or item.get("html_url") or "GitHub result",
                "url": item.get("html_url", ""),
                "snippet": item.get("description", "") or "",
                "provider": "github",
                "rank": index,
            }
            for index, item in enumerate(items)
            if item.get("html_url")
        ]

    def _search_wikidata(self, query: str, *, limit: int, language: str) -> list[dict[str, Any]]:
        params = urlencode(
            {
                "action": "wbsearchentities",
                "search": query,
                "language": (language or "en")[:2],
                "format": "json",
                "limit": min(max(limit, 1), 10),
            }
        )
        payload = self._http_json(f"https://www.wikidata.org/w/api.php?{params}", timeout=20)
        items = payload.get("search", []) if isinstance(payload, dict) else []
        return [
            {
                "title": item.get("label") or item.get("id") or "Wikidata entity",
                "url": f"https://www.wikidata.org/wiki/{item.get('id')}",
                "snippet": item.get("description", "") or "",
                "provider": "wikidata",
                "rank": index,
            }
            for index, item in enumerate(items)
            if item.get("id")
        ]

    def _search_sec(self, query: str, *, limit: int) -> list[dict[str, Any]]:
        payload = self._http_json("https://www.sec.gov/files/company_tickers_exchange.json", headers={"Accept": "application/json"}, timeout=20)
        records = payload.get("data", []) if isinstance(payload, dict) else []
        ranked: list[dict[str, Any]] = []
        for item in records:
            if not isinstance(item, list) or len(item) < 4:
                continue
            title = str(item[1] or "")
            ticker = str(item[2] or "")
            cik = str(item[0] or "")
            score = _lexical_score(query, title, ticker, cik)
            if score <= 0:
                continue
            cik_padded = cik.zfill(10)
            ranked.append(
                {
                    "title": f"{title} ({ticker})" if ticker else title or cik,
                    "url": f"https://data.sec.gov/submissions/CIK{cik_padded}.json",
                    "snippet": f"CIK {cik_padded} · exchange {item[3] or '-'}",
                    "provider": "sec",
                    "rank": 0,
                    "score": score,
                }
            )
        ranked = sorted(ranked, key=lambda item: item.get("score", 0.0), reverse=True)[:limit]
        for index, item in enumerate(ranked):
            item["rank"] = index
        return ranked

    def _search_internet_archive(self, query: str, *, limit: int) -> list[dict[str, Any]]:
        params = urlencode(
            {
                "q": f"title:({query}) OR description:({query})",
                "fl[]": ["identifier", "title", "description", "mediatype", "date"],
                "sort[]": "downloads desc",
                "rows": min(max(limit, 1), 10),
                "page": 1,
                "output": "json",
            },
            doseq=True,
        )
        payload = self._http_json(f"https://archive.org/advancedsearch.php?{params}", timeout=20)
        docs = payload.get("response", {}).get("docs", []) if isinstance(payload, dict) else []
        return [
            {
                "title": item.get("title") or item.get("identifier") or "Archive item",
                "url": f"https://archive.org/details/{item.get('identifier')}",
                "snippet": (item.get("description") or "")[:400],
                "provider": "internet_archive",
                "rank": index,
            }
            for index, item in enumerate(docs)
            if item.get("identifier")
        ]

    def _search_cisa_kev(self, query: str, *, limit: int) -> list[dict[str, Any]]:
        payload = self._http_json("https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json", timeout=20)
        items = payload.get("vulnerabilities", []) if isinstance(payload, dict) else []
        ranked: list[dict[str, Any]] = []
        for item in items:
            cve_id = str(item.get("cveID") or "")
            title = str(item.get("vendorProject") or "")
            product = str(item.get("product") or "")
            description = str(item.get("shortDescription") or "")
            score = _lexical_score(query, cve_id, title, product, description)
            if score <= 0:
                continue
            ranked.append(
                {
                    "title": f"{cve_id} · {title} {product}".strip(),
                    "url": f"https://www.cisa.gov/known-exploited-vulnerabilities-catalog-print#{cve_id}",
                    "snippet": description,
                    "provider": "cisa_kev",
                    "rank": 0,
                    "score": score,
                }
            )
        ranked = sorted(ranked, key=lambda item: item.get("score", 0.0), reverse=True)[:limit]
        for index, item in enumerate(ranked):
            item["rank"] = index
        return ranked

    def _search_nvd(self, query: str, *, limit: int) -> list[dict[str, Any]]:
        params = urlencode({"keywordSearch": query, "resultsPerPage": min(max(limit, 1), 10)})
        headers = {}
        api_key = os.getenv("NVD_API_KEY")
        if api_key:
            headers["apiKey"] = api_key
        payload = self._http_json(f"https://services.nvd.nist.gov/rest/json/cves/2.0?{params}", headers=headers, timeout=20)
        items = payload.get("vulnerabilities", []) if isinstance(payload, dict) else []
        results: list[dict[str, Any]] = []
        for index, item in enumerate(items):
            cve = item.get("cve", {})
            cve_id = cve.get("id")
            if not cve_id:
                continue
            descriptions = cve.get("descriptions", [])
            description = next((entry.get("value", "") for entry in descriptions if entry.get("lang") == "en"), "")
            results.append(
                {
                    "title": cve_id,
                    "url": f"https://nvd.nist.gov/vuln/detail/{cve_id}",
                    "snippet": description,
                    "provider": "nvd",
                    "rank": index,
                }
            )
        return results

    def _search_youtube(self, query: str, *, connector: OsintConnectorConfig, limit: int) -> list[dict[str, Any]]:
        api_key = os.getenv(connector.credential_env or "")
        if not api_key:
            return []
        params = urlencode(
            {
                "part": "snippet",
                "type": "video",
                "maxResults": min(max(limit, 1), 10),
                "q": query,
                "key": api_key,
            }
        )
        payload = self._http_json(f"https://www.googleapis.com/youtube/v3/search?{params}", timeout=20)
        items = payload.get("items", []) if isinstance(payload, dict) else []
        return [
            {
                "title": item.get("snippet", {}).get("title") or "YouTube result",
                "url": f"https://www.youtube.com/watch?v={item.get('id', {}).get('videoId')}",
                "snippet": item.get("snippet", {}).get("description", ""),
                "provider": "youtube",
                "rank": index,
            }
            for index, item in enumerate(items)
            if item.get("id", {}).get("videoId")
        ]

    def _search_shodan(self, query: str, *, connector: OsintConnectorConfig, limit: int) -> list[dict[str, Any]]:
        api_key = os.getenv(connector.credential_env or "")
        if not api_key:
            return []
        params = urlencode({"key": api_key, "query": query, "limit": min(max(limit, 1), 10)})
        payload = self._http_json(f"https://api.shodan.io/shodan/host/search?{params}", timeout=20)
        matches = payload.get("matches", []) if isinstance(payload, dict) else []
        results: list[dict[str, Any]] = []
        for index, item in enumerate(matches):
            ip = item.get("ip_str")
            if not ip:
                continue
            org = item.get("org") or item.get("isp") or ""
            port = item.get("port")
            results.append(
                {
                    "title": f"{ip}:{port}" if port else ip,
                    "url": f"https://www.shodan.io/host/{ip}",
                    "snippet": f"{org} · {item.get('data', '')[:220]}",
                    "provider": "shodan",
                    "rank": index,
                }
            )
        return results

    def _connector_search(
        self,
        connector: OsintConnectorConfig,
        *,
        query: str,
        limit: int,
        language: str,
        jurisdiction: str,
    ) -> list[dict[str, Any]]:
        if connector.connector_id == "brave":
            return self._search_brave(query, connector=connector, limit=limit, language=language, country=jurisdiction)
        if connector.connector_id == "tavily":
            return self._search_tavily(query, connector=connector, limit=limit)
        if connector.connector_id == "exa":
            return self._search_exa(query, connector=connector, limit=limit)
        if connector.connector_id == "github":
            return self._search_github(query, connector=connector, limit=limit)
        if connector.connector_id == "wikidata":
            return self._search_wikidata(query, limit=limit, language=language)
        if connector.connector_id == "sec":
            return self._search_sec(query, limit=limit)
        if connector.connector_id == "internet_archive":
            return self._search_internet_archive(query, limit=limit)
        if connector.connector_id == "cisa_kev":
            return self._search_cisa_kev(query, limit=limit)
        if connector.connector_id == "nvd":
            return self._search_nvd(query, limit=limit)
        if connector.connector_id == "youtube":
            return self._search_youtube(query, connector=connector, limit=limit)
        if connector.connector_id == "shodan":
            return self._search_shodan(query, connector=connector, limit=limit)
        return []

    def search(
        self,
        session: Session,
        *,
        investigation_id: str,
        query: str,
        connector_ids: list[str] | None = None,
        source_registry_ids: list[str] | None = None,
        via_tor: bool = False,
        limit: int | None = None,
    ) -> dict[str, Any]:
        investigation = session.get(OsintInvestigation, investigation_id)
        if investigation is None:
            raise KeyError(investigation_id)
        config = get_osint_config(session)
        max_results = int(limit or config.get("default_max_results", 5) or 5)
        connector_states = self.list_connectors(
            session,
            project_id=investigation.project_id,
            investigation_id=investigation.id,
            selected_connector_ids=connector_ids,
        )
        active_ids = [
            item["connector_id"]
            for item in connector_states
            if item["effective_enabled"] and item["ready"]
        ]
        run = self._record_run(
            session,
            investigation=investigation,
            run_kind="search",
            query=query,
            connector_ids=active_ids,
            via_tor=via_tor,
            metadata={"source_registry_ids": source_registry_ids or []},
        )
        results: list[dict[str, Any]] = []
        skipped: list[dict[str, Any]] = []
        errors: list[dict[str, Any]] = []
        seen_urls: set[str] = set()

        connector_rows = {
            row.connector_id: row
            for row in session.exec(select(OsintConnectorConfig).where(OsintConnectorConfig.connector_id.in_(active_ids))).all()
        }
        for connector_id in active_ids:
            connector = connector_rows.get(connector_id)
            if connector is None:
                continue
            try:
                connector_results = self._connector_search(
                    connector,
                    query=query,
                    limit=max_results,
                    language=investigation.language,
                    jurisdiction=investigation.jurisdiction,
                )
            except Exception as exc:
                errors.append({"connector_id": connector_id, "error": str(exc)})
                continue
            for item in connector_results:
                canonical = _canonical_url(str(item.get("url") or ""))
                if not canonical or canonical in seen_urls:
                    continue
                seen_urls.add(canonical)
                source = OsintSource(
                    investigation_id=investigation.id,
                    run_id=run.id,
                    connector_id=connector_id,
                    provider=str(item.get("provider") or connector_id),
                    title=str(item.get("title") or canonical),
                    url=str(item.get("url") or canonical),
                    canonical_url=canonical,
                    snippet=_truncate_text(str(item.get("snippet") or ""), 900),
                    rank=int(item.get("rank", len(results))),
                    search_query=query,
                    metadata_json=json.dumps(item.get("metadata", {}), ensure_ascii=False),
                )
                session.add(source)
                session.flush()
                self._write_source_file(source)
                results.append(self.source_to_dict(source))
                if len(results) >= max_results:
                    break
            if len(results) >= max_results:
                break

        if not results:
            registry_candidates = self._registry_seed_results(
                session,
                query=query,
                investigation=investigation,
                source_registry_ids=source_registry_ids,
                limit=max_results,
            )
            for item in registry_candidates:
                source = OsintSource(
                    investigation_id=investigation.id,
                    run_id=run.id,
                    registry_entry_id=item.get("registry_entry_id"),
                    connector_id=str(item.get("connector_id") or "manual_seed"),
                    provider=str(item.get("provider") or item.get("connector_id") or "manual_seed"),
                    title=str(item.get("title") or item.get("url") or "Seed source"),
                    url=str(item.get("url") or ""),
                    canonical_url=_canonical_url(str(item.get("url") or "")),
                    snippet=_truncate_text(str(item.get("snippet") or ""), 900),
                    rank=int(item.get("rank", len(results))),
                    search_query=query,
                    metadata_json=json.dumps({"seed": True}, ensure_ascii=False),
                )
                session.add(source)
                session.flush()
                self._write_source_file(source)
                results.append(self.source_to_dict(source))

        payload = {
            "run": self.run_to_dict(run),
            "query": query,
            "results": results,
            "skipped": skipped,
            "errors": errors,
            "connectors_used": active_ids,
            "connector_states": connector_states,
        }
        self._finish_run(run, status="succeeded" if results else "partial", payload=payload)
        session.add(run)
        investigation.updated_at = utc_now()
        session.add(investigation)
        return payload

    def _registry_seed_results(
        self,
        session: Session,
        *,
        query: str,
        investigation: OsintInvestigation,
        source_registry_ids: list[str] | None,
        limit: int,
    ) -> list[dict[str, Any]]:
        statement = select(OsintSourceRegistryEntry)
        if source_registry_ids:
            statement = statement.where(OsintSourceRegistryEntry.id.in_(source_registry_ids))
        rows = session.exec(statement).all()
        ranked: list[dict[str, Any]] = []
        for row in rows:
            if row.connector_id == "onion_manual" and not investigation.metadata_json:
                continue
            score = _lexical_score(query, row.title, row.description, row.base_url, row.source_key)
            if score <= 0:
                continue
            ranked.append(
                {
                    "registry_entry_id": row.id,
                    "connector_id": row.connector_id or "manual_seed",
                    "provider": row.connector_id or "manual_seed",
                    "title": row.title,
                    "url": row.base_url,
                    "snippet": row.description,
                    "score": score,
                    "rank": 0,
                }
            )
        ranked = sorted(ranked, key=lambda item: item["score"], reverse=True)[:limit]
        for index, item in enumerate(ranked):
            item["rank"] = index
        return ranked

    def source_to_dict(self, row: OsintSource) -> dict[str, Any]:
        return {
            "id": row.id,
            "investigation_id": row.investigation_id,
            "run_id": row.run_id,
            "registry_entry_id": row.registry_entry_id,
            "connector_id": row.connector_id,
            "provider": row.provider,
            "title": row.title,
            "url": row.url,
            "canonical_url": row.canonical_url,
            "snippet": row.snippet,
            "rank": row.rank,
            "search_query": row.search_query,
            "metadata": _safe_json(row.metadata_json, {}),
            "created_at": row.created_at.isoformat(),
        }

    def run_to_dict(self, row: OsintRun) -> dict[str, Any]:
        return {
            "id": row.id,
            "investigation_id": row.investigation_id,
            "run_kind": row.run_kind,
            "status": row.status,
            "query": row.query,
            "connector_ids": _safe_json(row.connector_ids_json, []),
            "via_tor": row.via_tor,
            "log_path": row.log_path,
            "metadata": _safe_json(row.metadata_json, {}),
            "created_at": row.created_at.isoformat(),
            "updated_at": row.updated_at.isoformat(),
        }

    def fetch(
        self,
        session: Session,
        *,
        investigation_id: str,
        source_id: str | None = None,
        url: str | None = None,
        via_tor: bool = False,
        follow_same_host_redirects_only: bool = False,
    ) -> dict[str, Any]:
        investigation = session.get(OsintInvestigation, investigation_id)
        if investigation is None:
            raise KeyError(investigation_id)
        source = session.get(OsintSource, source_id) if source_id else None
        target_url = (url or (source.url if source else "")).strip()
        if not target_url:
            raise ValueError("URL para fetch não informada")
        run = self._record_run(
            session,
            investigation=investigation,
            run_kind="fetch",
            query=target_url,
            connector_ids=[source.connector_id] if source else [],
            via_tor=via_tor,
        )
        try:
            raw_bytes, response_headers = self._fetch_url(
                target_url,
                via_tor=via_tor,
                follow_same_host_redirects_only=follow_same_host_redirects_only,
            )
        except Exception as exc:
            payload = {"run": self.run_to_dict(run), "status": "failed", "error": str(exc)}
            self._finish_run(run, status="failed", payload=payload)
            session.add(run)
            return payload

        capture = self._persist_capture(
            session,
            investigation=investigation,
            source=source,
            url=target_url,
            raw_bytes=raw_bytes,
            response_headers=response_headers,
            via_tor=via_tor,
        )
        evidence_payload = self.extract_evidence_from_capture(session, capture_id=capture.id, auto_claim=True)
        payload = {
            "run": self.run_to_dict(run),
            "capture": self.capture_to_dict(capture),
            "evidence": evidence_payload["evidence"],
            "claims": evidence_payload["claims"],
        }
        self._finish_run(run, status="succeeded", payload=payload)
        session.add(run)
        investigation.updated_at = utc_now()
        session.add(investigation)
        return payload

    def _fetch_url(
        self,
        url: str,
        *,
        via_tor: bool,
        follow_same_host_redirects_only: bool,
    ) -> tuple[bytes, dict[str, str]]:
        timeout = int(_default_osint_config()["fetch_timeout_seconds"])
        if via_tor:
            proxy_url = os.getenv("ORQUESTRA_OSINT_TOR_PROXY_URL", DEFAULT_TOR_PROXY_URL)
            if not proxy_url:
                raise RuntimeError("Tor proxy não configurado")
            command = [
                "/usr/bin/curl",
                "--silent",
                "--show-error",
                "--location",
                "--max-time",
                str(timeout),
                "--user-agent",
                OSINT_USER_AGENT,
                "--socks5-hostname",
                proxy_url.removeprefix("socks5h://").removeprefix("socks5://"),
                url,
            ]
            if follow_same_host_redirects_only:
                command.extend(["--proto-redir", "=https,http"])
            process = subprocess.run(command, check=False, capture_output=True)
            if process.returncode != 0:
                raise RuntimeError(process.stderr.decode("utf-8", errors="ignore").strip() or "Falha no fetch via Tor")
            return process.stdout, {}
        headers = {"Accept": "text/html,application/xhtml+xml,application/json,application/pdf,text/plain;q=0.9,*/*;q=0.8"}
        return self._http_bytes(url, headers=headers, timeout=timeout)

    def _persist_capture(
        self,
        session: Session,
        *,
        investigation: OsintInvestigation,
        source: OsintSource | None,
        url: str,
        raw_bytes: bytes,
        response_headers: dict[str, str],
        via_tor: bool,
    ) -> OsintCapture:
        self.paths.ensure_investigation(investigation.id)
        content_type = response_headers.get("content-type", "")
        content_hash = hashlib.sha256(raw_bytes).hexdigest()
        snapshot_path = self.paths.captures_dir(investigation.id) / f"{utc_now().strftime('%Y%m%d-%H%M%S')}-{content_hash[:10]}.bin"
        snapshot_path.write_bytes(raw_bytes)
        normalized_text = self._normalize_content(raw_bytes, content_type=content_type, url=url)
        normalized_path = snapshot_path.with_suffix(".md")
        normalized_path.write_text(normalized_text, encoding="utf-8")
        capture = OsintCapture(
            investigation_id=investigation.id,
            source_id=source.id if source else None,
            connector_id=source.connector_id if source else "direct_fetch",
            url=url,
            canonical_url=_canonical_url(url),
            title=source.title if source else _canonical_url(url),
            content_type=content_type,
            content_hash=content_hash,
            snapshot_path=str(snapshot_path),
            normalized_path=str(normalized_path),
            via_tor=via_tor,
            license_policy="metadata_only",
            metadata_json=json.dumps({"response_headers": response_headers}, ensure_ascii=False),
        )
        session.add(capture)
        session.flush()
        return capture

    def _normalize_content(self, raw_bytes: bytes, *, content_type: str, url: str) -> str:
        lowered = (content_type or "").lower()
        if lowered.startswith("application/json") or url.lower().endswith(".json"):
            try:
                return json.dumps(json.loads(raw_bytes.decode("utf-8")), ensure_ascii=False, indent=2)
            except Exception:
                return raw_bytes.decode("utf-8", errors="ignore")
        if "pdf" in lowered or url.lower().endswith(".pdf"):
            try:
                reader = PdfReader(io.BytesIO(raw_bytes))
                parts = [page.extract_text() or "" for page in reader.pages[:8]]
                return "\n\n".join(part.strip() for part in parts if part.strip()) or "[PDF sem texto extraível]"
            except Exception:
                return "[Falha ao extrair PDF]"
        if "html" in lowered or lowered == "" or lowered.startswith("text/"):
            text = raw_bytes.decode("utf-8", errors="ignore")
            if "<html" in text.lower():
                soup = BeautifulSoup(text, "html.parser")
                for tag in soup(["script", "style", "noscript"]):
                    tag.decompose()
                title = soup.title.get_text(" ", strip=True) if soup.title else ""
                body = soup.get_text("\n", strip=True)
                normalized = "\n".join(line.strip() for line in body.splitlines() if line.strip())
                return "\n\n".join(part for part in [title, normalized] if part)
            return text
        return raw_bytes.decode("utf-8", errors="ignore")

    def extract_evidence_from_capture(self, session: Session, *, capture_id: str, auto_claim: bool = True) -> dict[str, Any]:
        capture = session.get(OsintCapture, capture_id)
        if capture is None:
            raise KeyError(capture_id)
        normalized_path = Path(capture.normalized_path)
        content = normalized_path.read_text(encoding="utf-8", errors="ignore") if normalized_path.exists() else ""
        excerpt = _truncate_text(content, 1800)
        evidence = OsintEvidence(
            investigation_id=capture.investigation_id or "",
            source_id=capture.source_id,
            capture_id=capture.id,
            title=capture.title or capture.url,
            content=excerpt or (capture.url if capture.url else "Sem conteúdo normalizado"),
            validation_status="pending",
            source_quality=0.72,
            metadata_json=json.dumps(
                {
                    "url": capture.url,
                    "canonical_url": capture.canonical_url,
                    "content_hash": capture.content_hash,
                    "license_policy": capture.license_policy,
                },
                ensure_ascii=False,
            ),
        )
        session.add(evidence)
        session.flush()
        self._write_evidence_file(evidence)
        self._upsert_evidence_vector(evidence)
        claims: list[dict[str, Any]] = []
        if auto_claim:
            claim = OsintClaim(
                investigation_id=evidence.investigation_id,
                evidence_ids_json=json.dumps([evidence.id], ensure_ascii=False),
                title=f"Claim: {evidence.title}",
                content=_truncate_text(evidence.content, 520),
                confidence=0.62,
                status="pending",
                metadata_json=json.dumps(
                    {
                        "url": capture.url,
                        "capture_id": capture.id,
                        "training_allowed": False,
                    },
                    ensure_ascii=False,
                ),
            )
            session.add(claim)
            session.flush()
            evidence.claim_ids_json = json.dumps([claim.id], ensure_ascii=False)
            session.add(evidence)
            self._write_claim_file(claim)
            claims.append(self.claim_to_dict(claim))
        return {"evidence": [self.evidence_to_dict(evidence)], "claims": claims}

    def evidence_to_dict(self, row: OsintEvidence) -> dict[str, Any]:
        return {
            "id": row.id,
            "investigation_id": row.investigation_id,
            "source_id": row.source_id,
            "capture_id": row.capture_id,
            "title": row.title,
            "content": row.content,
            "validation_status": row.validation_status,
            "source_quality": row.source_quality,
            "entity_ids": _safe_json(row.entity_ids_json, []),
            "claim_ids": _safe_json(row.claim_ids_json, []),
            "metadata": _safe_json(row.metadata_json, {}),
            "created_at": row.created_at.isoformat(),
            "updated_at": row.updated_at.isoformat(),
        }

    def claim_to_dict(self, row: OsintClaim) -> dict[str, Any]:
        return {
            "id": row.id,
            "investigation_id": row.investigation_id,
            "evidence_ids": _safe_json(row.evidence_ids_json, []),
            "title": row.title,
            "content": row.content,
            "confidence": row.confidence,
            "status": row.status,
            "memory_record_id": row.memory_record_id,
            "metadata": _safe_json(row.metadata_json, {}),
            "created_at": row.created_at.isoformat(),
            "updated_at": row.updated_at.isoformat(),
        }

    def capture_to_dict(self, row: OsintCapture) -> dict[str, Any]:
        return {
            "id": row.id,
            "investigation_id": row.investigation_id,
            "source_id": row.source_id,
            "connector_id": row.connector_id,
            "url": row.url,
            "canonical_url": row.canonical_url,
            "title": row.title,
            "content_type": row.content_type,
            "content_hash": row.content_hash,
            "snapshot_path": row.snapshot_path,
            "normalized_path": row.normalized_path,
            "published_at": row.published_at.isoformat() if row.published_at else None,
            "fetched_at": row.fetched_at.isoformat(),
            "via_tor": row.via_tor,
            "license_policy": row.license_policy,
            "metadata": _safe_json(row.metadata_json, {}),
            "created_at": row.created_at.isoformat(),
        }

    def list_runs(self, session: Session, investigation_id: str) -> list[dict[str, Any]]:
        rows = session.exec(select(OsintRun).where(OsintRun.investigation_id == investigation_id).order_by(OsintRun.created_at.desc())).all()
        return [self.run_to_dict(row) for row in rows]

    def list_evidence(self, session: Session, *, investigation_id: str | None = None, validation_status: str | None = None) -> list[dict[str, Any]]:
        statement = select(OsintEvidence).order_by(OsintEvidence.updated_at.desc())
        if investigation_id:
            statement = statement.where(OsintEvidence.investigation_id == investigation_id)
        if validation_status:
            statement = statement.where(OsintEvidence.validation_status == validation_status)
        rows = session.exec(statement.limit(120)).all()
        return [self.evidence_to_dict(row) for row in rows]

    def list_claims(self, session: Session, *, investigation_id: str | None = None, status: str | None = None) -> list[dict[str, Any]]:
        statement = select(OsintClaim).order_by(OsintClaim.updated_at.desc())
        if investigation_id:
            statement = statement.where(OsintClaim.investigation_id == investigation_id)
        if status:
            statement = statement.where(OsintClaim.status == status)
        rows = session.exec(statement.limit(120)).all()
        return [self.claim_to_dict(row) for row in rows]

    def approve_evidence(self, session: Session, evidence_id: str) -> dict[str, Any]:
        row = session.get(OsintEvidence, evidence_id)
        if row is None:
            raise KeyError(evidence_id)
        row.validation_status = "approved"
        row.updated_at = utc_now()
        session.add(row)
        return self.evidence_to_dict(row)

    def approve_claim(self, session: Session, claim_id: str, *, create_memory: bool = True) -> dict[str, Any]:
        row = session.get(OsintClaim, claim_id)
        if row is None:
            raise KeyError(claim_id)
        row.status = "approved"
        row.updated_at = utc_now()
        session.add(row)
        memory_payload = None
        if create_memory:
            evidence_ids = _safe_json(row.evidence_ids_json, [])
            evidence_rows = [session.get(OsintEvidence, evidence_id) for evidence_id in evidence_ids]
            citations = []
            investigation = session.get(OsintInvestigation, row.investigation_id)
            for evidence in evidence_rows:
                if evidence is None:
                    continue
                metadata = _safe_json(evidence.metadata_json, {})
                citations.append(
                    {
                        "channel": "osint_evidence",
                        "title": evidence.title,
                        "source": metadata.get("canonical_url") or metadata.get("url") or "",
                        "evidence_id": evidence.id,
                        "capture_id": evidence.capture_id,
                    }
                )
            memory_metadata = _safe_json(row.metadata_json, {}) | {
                "title": row.title,
                "source_url": citations[0]["source"] if citations else "",
                "citations": citations,
                "evidence_ids": evidence_ids,
                "claim_id": row.id,
                "investigation_id": row.investigation_id,
                "validation_status": row.status,
                "license_policy": "metadata_only",
                "channel": "osint",
            }
            memory_record = MemoryRecord(
                project_id=investigation.project_id if investigation else None,
                session_id=investigation.session_id if investigation else None,
                scope="source_fact",
                memory_kind="reference",
                source=f"osint_claim:{row.id}",
                content=row.content,
                confidence=row.confidence,
                approved_for_training=False,
                metadata_json=json.dumps(memory_metadata, ensure_ascii=False),
            )
            session.add(memory_record)
            session.flush()
            row.memory_record_id = memory_record.id
            session.add(row)
            memory_payload = {
                "id": memory_record.id,
                "project_id": memory_record.project_id,
                "session_id": memory_record.session_id,
                "scope": memory_record.scope,
                "memory_kind": memory_record.memory_kind,
                "source": memory_record.source,
                "content": memory_record.content,
                "confidence": memory_record.confidence,
                "metadata": memory_metadata,
                "created_at": memory_record.created_at.isoformat(),
            }
        return {"claim": self.claim_to_dict(row), "memory_record": memory_payload}

    def export_dataset_bundle(self, session: Session, *, investigation_id: str) -> dict[str, Any]:
        investigation = session.get(OsintInvestigation, investigation_id)
        if investigation is None:
            raise KeyError(investigation_id)
        rows = session.exec(
            select(OsintClaim)
            .where(OsintClaim.investigation_id == investigation_id)
            .where(OsintClaim.status == "approved")
            .order_by(OsintClaim.updated_at.desc())
        ).all()
        records: list[dict[str, Any]] = []
        skipped = 0
        for row in rows:
            metadata = _safe_json(row.metadata_json, {})
            if not bool(metadata.get("training_allowed", False)):
                skipped += 1
                continue
            records.append(
                {
                    "instruction": row.title,
                    "context": "",
                    "response": row.content,
                    "labels": {"investigation_id": investigation_id, "source": "osint_claim"},
                    "metadata": metadata,
                }
            )
        self.paths.ensure_investigation(investigation_id)
        export_path = self.paths.exports_dir(investigation_id) / f"dataset-bundle-{utc_now().strftime('%Y%m%d-%H%M%S')}.json"
        export_path.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
        return {
            "investigation_id": investigation_id,
            "record_count": len(records),
            "skipped_count": skipped,
            "export_path": str(export_path),
            "records": records,
        }

    def recall_evidence(
        self,
        session: Session,
        *,
        query: str,
        investigation_id: str | None = None,
        limit: int = 4,
    ) -> dict[str, Any]:
        items: list[dict[str, Any]] = []
        vector_error = ""
        try:
            hits = query_collection(self.rag_paths, OSINT_EVIDENCE_COLLECTION, query, top_k=max(limit * 3, limit))
            for hit in hits:
                metadata = hit.metadata
                if investigation_id and metadata.get("investigation_id") not in (investigation_id, "", None):
                    continue
                items.append(
                    {
                        "id": str(metadata.get("evidence_id") or hit.document_id or hit.chunk_id),
                        "title": metadata.get("title") or "Evidência",
                        "content": hit.text,
                        "score": round(1.0 - float(hit.distance or 0.0), 4),
                        "metadata": metadata | {"channel": "osint_evidence", "backend": "chroma"},
                    }
                )
                if len(items) >= limit:
                    break
        except Exception as exc:
            vector_error = str(exc)
        if len(items) < limit:
            statement = select(OsintEvidence).order_by(OsintEvidence.updated_at.desc())
            if investigation_id:
                statement = statement.where(OsintEvidence.investigation_id == investigation_id)
            rows = session.exec(statement.limit(120)).all()
            seen = {item["id"] for item in items}
            ranked: list[dict[str, Any]] = []
            for row in rows:
                if row.id in seen:
                    continue
                score = _lexical_score(query, row.title, row.content)
                if score <= 0:
                    continue
                ranked.append(
                    {
                        "id": row.id,
                        "title": row.title,
                        "content": row.content,
                        "score": round(score, 4),
                        "metadata": _safe_json(row.metadata_json, {}) | {"channel": "osint_evidence", "backend": "sqlite_lexical"},
                    }
                )
            items.extend(sorted(ranked, key=lambda item: item["score"], reverse=True)[: max(limit - len(items), 0)])
        return {
            "items": items[:limit],
            "status": "ok" if not vector_error else "fallback" if items else "unavailable",
            "collection_name": OSINT_EVIDENCE_COLLECTION,
            "error": vector_error,
        }

    def format_context(self, items: list[dict[str, Any]], *, max_chars: int = 3000) -> str:
        rendered: list[str] = []
        total = 0
        for item in items:
            metadata = item.get("metadata", {})
            descriptor = metadata.get("canonical_url") or metadata.get("url") or metadata.get("source") or ""
            line = f"- [evidence] {item.get('title', 'Evidência')}: {item.get('content', '')}"
            if descriptor:
                line += f" ({descriptor})"
            if total + len(line) > max_chars:
                break
            rendered.append(line)
            total += len(line)
        return "\n".join(rendered)

    def build_context_bundle(
        self,
        session: Session,
        *,
        query: str,
        project_id: str | None = None,
        session_id: str | None = None,
        investigation_id: str | None = None,
        fresh_web_enabled: bool = False,
        evidence_enabled: bool = True,
        enabled_connector_ids: list[str] | None = None,
        source_registry_ids: list[str] | None = None,
        via_tor: bool = False,
        limit: int = 4,
    ) -> dict[str, Any]:
        investigation = session.get(OsintInvestigation, investigation_id) if investigation_id else None
        if investigation is None and (fresh_web_enabled or evidence_enabled) and (session_id or project_id):
            investigation = self.ensure_session_investigation(
                session,
                session_id=session_id,
                project_id=project_id,
                objective=query,
                connector_ids=enabled_connector_ids,
            )
            investigation_id = investigation.id
        evidence_payload = {"items": [], "status": "disabled", "collection_name": OSINT_EVIDENCE_COLLECTION, "error": ""}
        citations: list[dict[str, Any]] = []
        fresh_results: list[dict[str, Any]] = []
        if evidence_enabled and investigation_id:
            evidence_payload = self.recall_evidence(session, query=query, investigation_id=investigation_id, limit=limit)
            for item in evidence_payload.get("items", []):
                metadata = item.get("metadata", {})
                citations.append(
                    {
                        "channel": "osint_evidence",
                        "source": metadata.get("canonical_url") or metadata.get("url") or "",
                        "title": item.get("title", "Evidência"),
                        "evidence_id": item.get("id"),
                    }
                )
        if fresh_web_enabled and investigation is not None:
            search_payload = self.search(
                session,
                investigation_id=investigation.id,
                query=query,
                connector_ids=enabled_connector_ids,
                source_registry_ids=source_registry_ids,
                via_tor=via_tor,
                limit=limit,
            )
            fresh_results = list(search_payload.get("results", []))
            fetch_limit = min(int(get_osint_config(session).get("default_fetch_limit", 2) or 2), len(fresh_results))
            for item in fresh_results[:fetch_limit]:
                if not item.get("url"):
                    continue
                fetch_payload = self.fetch(session, investigation_id=investigation.id, source_id=item["id"], via_tor=via_tor)
                for evidence in fetch_payload.get("evidence", []):
                    citations.append(
                        {
                            "channel": "osint_fresh",
                            "source": evidence.get("metadata", {}).get("canonical_url") or evidence.get("metadata", {}).get("url") or "",
                            "title": evidence.get("title", "Fresh evidence"),
                            "evidence_id": evidence.get("id"),
                        }
                    )
            evidence_payload = self.recall_evidence(session, query=query, investigation_id=investigation.id, limit=limit)
        context = self.format_context(evidence_payload.get("items", []), max_chars=3200)
        return {
            "investigation_id": investigation.id if investigation else investigation_id,
            "context": context,
            "citations": citations[: max(limit * 2, 4)],
            "evidence": evidence_payload.get("items", []),
            "fresh_results": fresh_results,
            "status": evidence_payload.get("status", "disabled"),
            "selector_mode": "osint_hybrid",
        }

    def _write_source_file(self, row: OsintSource) -> None:
        if not row.investigation_id:
            return
        self.paths.ensure_investigation(row.investigation_id)
        target = self.paths.sources_dir(row.investigation_id) / f"{row.created_at.strftime('%Y%m%d-%H%M%S')}-{row.id[:8]}.json"
        target.write_text(json.dumps(self.source_to_dict(row), ensure_ascii=False, indent=2), encoding="utf-8")

    def _write_evidence_file(self, row: OsintEvidence) -> None:
        self.paths.ensure_investigation(row.investigation_id)
        target = self.paths.evidence_dir(row.investigation_id) / f"{row.created_at.strftime('%Y%m%d-%H%M%S')}-{row.id[:8]}.md"
        metadata = _safe_json(row.metadata_json, {})
        body = [
            "---",
            f"id: {json.dumps(row.id, ensure_ascii=False)}",
            f"title: {json.dumps(row.title, ensure_ascii=False)}",
            f"validation_status: {json.dumps(row.validation_status, ensure_ascii=False)}",
            f"source_quality: {json.dumps(str(row.source_quality), ensure_ascii=False)}",
            "---",
            "",
            f"# {row.title}",
            "",
            row.content,
            "",
            "## Metadata",
            "",
            "```json",
            json.dumps(metadata, ensure_ascii=False, indent=2),
            "```",
            "",
        ]
        target.write_text("\n".join(body), encoding="utf-8")

    def _write_claim_file(self, row: OsintClaim) -> None:
        self.paths.ensure_investigation(row.investigation_id)
        target = self.paths.claims_dir(row.investigation_id) / f"{row.created_at.strftime('%Y%m%d-%H%M%S')}-{row.id[:8]}.md"
        metadata = _safe_json(row.metadata_json, {})
        body = [
            "---",
            f"id: {json.dumps(row.id, ensure_ascii=False)}",
            f"title: {json.dumps(row.title, ensure_ascii=False)}",
            f"status: {json.dumps(row.status, ensure_ascii=False)}",
            f"confidence: {json.dumps(str(row.confidence), ensure_ascii=False)}",
            "---",
            "",
            f"# {row.title}",
            "",
            row.content,
            "",
            "## Metadata",
            "",
            "```json",
            json.dumps(metadata, ensure_ascii=False, indent=2),
            "```",
            "",
        ]
        target.write_text("\n".join(body), encoding="utf-8")

    def _upsert_evidence_vector(self, row: OsintEvidence) -> None:
        chunk = RagChunk(
            chunk_id=f"osint-evidence:{row.id}",
            document_id=row.id,
            collection_name=OSINT_EVIDENCE_COLLECTION,
            text=row.content,
            metadata={
                "investigation_id": row.investigation_id,
                "evidence_id": row.id,
                "title": row.title,
                **(_safe_json(row.metadata_json, {})),
            },
        )
        try:
            upsert_chunks(self.rag_paths, OSINT_EVIDENCE_COLLECTION, [chunk])
        except Exception:
            return


def _truncate_text(text: str, limit: int) -> str:
    normalized = " ".join(text.split())
    if len(normalized) <= limit:
        return normalized
    return normalized[: max(limit - 1, 1)].rstrip() + "…"
