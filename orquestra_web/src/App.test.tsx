import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import App from "./App";

const SESSION_ID = "session-1";
const WORKFLOW_ID = "workflow-1";
const TASK_ID = "task-1";
const TASK_DEP_ID = "task-2";
const REMOTE_RUN_ID = "remote-run-1";
const REMOTE_ARTIFACT_ID = "remote-artifact-1";
const OSINT_INVESTIGATION_ID = "osint-1";

function jsonResponse(payload: unknown) {
  return Promise.resolve(
    new Response(JSON.stringify(payload), {
      status: 200,
      headers: { "Content-Type": "application/json" }
    })
  );
}

function mockApi(url: string) {
  const parsed = new URL(url, "http://localhost");
  const path = parsed.pathname;

  if (path === "/api/health") {
    return jsonResponse({
      ok: true,
      app: "Orquestra AI",
      app_version: "0.2.0",
      schema_version: 6,
      schema_target_version: 6,
      migration_required: false,
      workspace_root: "/tmp/orquestra",
      database_url: "sqlite:////tmp/orquestra.db",
      redis_url: "redis://127.0.0.1:6379/0",
      qdrant_path: "/tmp/qdrant",
      web_enabled: true,
      providers: 1,
      projects: 1,
      memory_topics: 0,
      workspace_scans: 0,
      runtime: {
        app_version: "0.2.0",
        schema_version: 6,
        target_schema_version: 6,
        migration_required: false,
        mode: "workspace",
        managed: false,
        manifest_path: "/tmp/install_manifest.json",
        backup_dir: "/tmp/backups",
        backup_count: 0,
        backups: []
      }
    });
  }

  if (path === "/api/ops/dashboard") {
    return jsonResponse({
      generated_at: new Date().toISOString(),
      services: [],
      metrics: [],
      process_snapshot: {
        background_processes: [],
        tmux_sessions: [],
        listeners: { api: true, web: true },
        recent_sessions: [],
        recent_scans: [],
        recent_jobs: [],
        recent_workflows: [
          {
            id: WORKFLOW_ID,
            session_id: SESSION_ID,
            task_id: TASK_ID,
            workflow_name: "session-validation",
            status: "interrupted",
            summary: "Executar validação local",
            log_path: "/tmp/workflow.log",
            output_path: "/tmp/workflow.json",
            progress: 0.5,
            cancel_requested: false,
            metadata: { recovered_after_restart: true },
            started_at: new Date().toISOString(),
            finished_at: new Date().toISOString(),
            output_exists: true,
            output_preview: {
              status: "interrupted",
              recovered: true,
              note: "resume from artifact"
            },
            steps: []
          }
        ],
        runtime_paths: {},
        runtime_state: {
          app_version: "0.2.0",
          schema_version: 6,
          target_schema_version: 6,
          migration_required: false,
          mode: "workspace",
          managed: false,
          manifest_path: "/tmp/install_manifest.json",
          backup_dir: "/tmp/backups",
          backup_count: 0,
          backups: []
        }
      },
      memory_snapshot: {
        topics: 0,
        records: 1,
        training_candidates: 0,
        review_candidates: 0,
        review_pending: 0,
        message_count: 3,
        scope_breakdown: [{ scope: "reference", count: 1 }],
        recent_records: [],
        recent_topics: [],
        recent_review_candidates: [],
        recent_candidates: [],
        storage: {
          database_size_bytes: 1024,
          memorygraph_dir_exists: true,
          workspace_dir_exists: true,
          assets_indexed: 0,
          scans_total: 0
        }
      },
      execution_snapshot: {
        providers: [
          {
            id: "provider-1",
            provider_id: "lmstudio",
            label: "LM Studio",
            transport: "openai_compatible",
            enabled: true,
            capabilities: ["chat"],
            config: {},
            updated_at: new Date().toISOString()
          }
        ],
        projects: [
          {
            id: "project-1",
            slug: "orquestra-lab",
            name: "Orquestra Lab",
            description: "Projeto base",
            default_provider_id: "lmstudio",
            default_model: "ministral",
            created_at: new Date().toISOString()
          }
        ],
        connectors: [],
        training_jobs: [],
        remote_jobs: [],
        workflow_runs: [
          {
            id: WORKFLOW_ID,
            session_id: SESSION_ID,
            task_id: TASK_ID,
            workflow_name: "session-validation",
            status: "interrupted",
            summary: "Executar validação local",
            log_path: "/tmp/workflow.log",
            output_path: "/tmp/workflow.json",
            progress: 0.5,
            cancel_requested: false,
            metadata: { recovered_after_restart: true },
            started_at: new Date().toISOString(),
            finished_at: new Date().toISOString(),
            output_exists: true,
            output_preview: {
              status: "interrupted",
              recovered: true,
              note: "resume from artifact"
            },
            steps: []
          }
        ],
        registry_models: [],
        actions: [],
        runs: [],
        artifacts: {
          app_bundle_path: "/tmp/Orquestra AI.app",
          app_bundle_exists: true,
          dmg_path: "/tmp/Orquestra AI.dmg",
          dmg_exists: true,
          installer_path: "/tmp/install.sh",
          installer_exists: true,
          uninstaller_path: "/tmp/uninstall.sh",
          uninstaller_exists: true,
          connectors_ready: 0
        }
      }
    });
  }

  if (path === "/api/models") {
    return jsonResponse({ provider_id: "lmstudio", models: ["ministral"] });
  }

  if (path === "/api/chat/sessions") {
    return jsonResponse([
      {
        id: SESSION_ID,
        project_id: "project-1",
        title: "Sessão teste",
        provider_id: "lmstudio",
        model_name: "ministral",
        status: "active",
        metadata: {},
        profile: {
          objective: "Validar planner e compaction.",
          preset: "assistant",
          preset_label: "Assistente",
          memory_policy: { enabled: true, scopes: ["session_memory"] },
          rag_policy: { enabled: true, collections: ["knowledge_base"], include_workspace: true, include_sources: true },
          persona_config: { style_notes: "Operacional" }
        },
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        last_message_at: new Date().toISOString()
      }
    ]);
  }

  if (path === "/api/memory" || path === "/api/memory/topics" || path === "/api/memory/training-candidates") {
    return jsonResponse([]);
  }

  if (path === "/api/memory/candidates") {
    return jsonResponse([]);
  }

  if (path === "/api/workspace/scans") {
    return jsonResponse([]);
  }

  if (path === "/api/osint/config") {
    return jsonResponse({
      search_timeout_seconds: 20,
      fetch_timeout_seconds: 20,
      default_max_results: 5,
      default_fetch_limit: 2,
      default_evidence_limit: 4,
      tor_proxy_url: "socks5h://127.0.0.1:9050",
      store_result_metadata: true,
      store_full_provider_snippet: false
    });
  }

  if (path === "/api/osint/connectors" || path === "/api/osint/providers") {
    return jsonResponse([
      {
        connector_id: "brave",
        label: "Brave Search",
        category: "search_provider",
        connector_kind: "search_provider",
        status: "ready",
        description: "Busca geral com fallback nativo.",
        enabled_global: true,
        enabled_by_default: true,
        effective_enabled: true,
        requires_credential: true,
        credential_env: "BRAVE_SEARCH_API_KEY",
        credential_status: "configured_optional",
        priority: 10,
        health_status: "online",
        allowed_modes: ["search", "fresh_web"],
        training_allowed: false,
        retention_policy: "metadata_only",
        via_tor_allowed: false,
        project_overrides: {},
        metadata: {},
        ready: true
      },
      {
        connector_id: "wikidata",
        label: "Wikidata",
        category: "structured_public_api",
        connector_kind: "structured_public_api",
        status: "ready",
        description: "Entidades públicas.",
        enabled_global: true,
        enabled_by_default: true,
        effective_enabled: true,
        requires_credential: false,
        credential_status: "not_required",
        priority: 40,
        health_status: "online",
        allowed_modes: ["search", "fetch"],
        training_allowed: false,
        retention_policy: "metadata_only",
        via_tor_allowed: false,
        project_overrides: {},
        metadata: {},
        ready: true
      }
    ]);
  }

  if (path === "/api/osint/source-registry") {
    return jsonResponse([
      {
        id: "registry-1",
        source_key: "manual-orquestra",
        connector_id: "brave",
        title: "Manual Orquestra Seed",
        category: "manual_seed",
        access_type: "web",
        base_url: "https://example.test/orquestra",
        description: "Fonte manual para o laboratório de OSINT.",
        retention_policy: "metadata_only",
        training_allowed: false,
        reliability: 0.8,
        jurisdiction_tags: ["global"],
        preset_tags: ["osint"],
        tor_supported: false,
        api_auth_required: false,
        robots_sensitive: false,
        metadata: {},
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString()
      }
    ]);
  }

  if (path === "/api/osint/investigations") {
    return jsonResponse([
      {
        id: OSINT_INVESTIGATION_ID,
        project_id: "project-1",
        session_id: SESSION_ID,
        title: "Investigação Orquestra",
        objective: "Coletar evidências rastreáveis e aprovar claims relevantes.",
        target_entity: "Orquestra AI",
        language: "pt-BR",
        jurisdiction: "global",
        mode: "balanced",
        status: "active",
        enabled_connector_ids: ["brave", "wikidata"],
        source_registry_ids: ["registry-1"],
        allowed_domains: [],
        blocked_domains: [],
        metadata: {},
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString()
      }
    ]);
  }

  if (path === `/api/osint/investigations/${OSINT_INVESTIGATION_ID}`) {
    return jsonResponse({
      id: OSINT_INVESTIGATION_ID,
      project_id: "project-1",
      session_id: SESSION_ID,
      title: "Investigação Orquestra",
      objective: "Coletar evidências rastreáveis e aprovar claims relevantes.",
      target_entity: "Orquestra AI",
      language: "pt-BR",
      jurisdiction: "global",
      mode: "balanced",
      status: "active",
      enabled_connector_ids: ["brave", "wikidata"],
      source_registry_ids: ["registry-1"],
      allowed_domains: [],
      blocked_domains: [],
      metadata: {},
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString()
    });
  }

  if (path === `/api/osint/investigations/${OSINT_INVESTIGATION_ID}/runs`) {
    return jsonResponse([
      {
        id: "osint-run-1",
        investigation_id: OSINT_INVESTIGATION_ID,
        run_kind: "search",
        status: "succeeded",
        query: "orquestra ai memory graph",
        connector_ids: ["brave"],
        via_tor: false,
        log_path: "/tmp/osint-run.log",
        metadata: {},
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString()
      }
    ]);
  }

  if (path === "/api/osint/evidence") {
    return jsonResponse([
      {
        id: "evidence-1",
        investigation_id: OSINT_INVESTIGATION_ID,
        source_id: "source-1",
        capture_id: "capture-1",
        title: "Orquestra Evidence",
        content: "O Orquestra mantém memória local-first com aprovação explícita.",
        validation_status: "approved",
        source_quality: 0.82,
        entity_ids: [],
        claim_ids: ["claim-1"],
        metadata: { url: "https://example.test/orquestra" },
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString()
      }
    ]);
  }

  if (path === "/api/osint/claims") {
    return jsonResponse([
      {
        id: "claim-1",
        investigation_id: OSINT_INVESTIGATION_ID,
        evidence_ids: ["evidence-1"],
        title: "Claim: memória local-first",
        content: "A memória do Orquestra é local-first e só promove conteúdo aprovado.",
        confidence: 0.76,
        status: "pending",
        memory_record_id: null,
        metadata: {},
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString()
      }
    ]);
  }

  if (path === `/api/osint/investigations/${OSINT_INVESTIGATION_ID}/plan`) {
    return jsonResponse({
      investigation: {
        id: OSINT_INVESTIGATION_ID,
        project_id: "project-1",
        session_id: SESSION_ID,
        title: "Investigação Orquestra",
        objective: "Coletar evidências rastreáveis e aprovar claims relevantes.",
        target_entity: "Orquestra AI",
        language: "pt-BR",
        jurisdiction: "global",
        mode: "balanced",
        status: "active",
        enabled_connector_ids: ["brave", "wikidata"],
        source_registry_ids: ["registry-1"],
        allowed_domains: [],
        blocked_domains: [],
        metadata: {},
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString()
      },
      queries: ["orquestra ai memory graph", "\"orquestra ai\" filetype:pdf"]
    });
  }

  if (path === `/api/osint/investigations/${OSINT_INVESTIGATION_ID}/search`) {
    return jsonResponse({
      run: {
        id: "osint-run-search",
        investigation_id: OSINT_INVESTIGATION_ID,
        run_kind: "search",
        status: "succeeded",
        query: "orquestra ai memory graph",
        connector_ids: ["brave"],
        via_tor: false,
        log_path: "/tmp/osint-search.log",
        metadata: {},
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString()
      },
      query: "orquestra ai memory graph",
      results: [
        {
          id: "source-1",
          investigation_id: OSINT_INVESTIGATION_ID,
          run_id: "osint-run-search",
          registry_entry_id: "registry-1",
          connector_id: "brave",
          provider: "brave",
          title: "Orquestra Evidence",
          url: "https://example.test/orquestra",
          canonical_url: "https://example.test/orquestra",
          snippet: "Resumo indexado para o OSINT Lab.",
          rank: 0,
          search_query: "orquestra ai memory graph",
          metadata: {},
          created_at: new Date().toISOString()
        }
      ],
      skipped: [],
      errors: [],
      connectors_used: ["brave"],
      connector_states: []
    });
  }

  if (path === `/api/osint/investigations/${OSINT_INVESTIGATION_ID}/fetch`) {
    return jsonResponse({
      run: {
        id: "osint-run-fetch",
        investigation_id: OSINT_INVESTIGATION_ID,
        run_kind: "fetch",
        status: "succeeded",
        query: "https://example.test/orquestra",
        connector_ids: ["brave"],
        via_tor: false,
        log_path: "/tmp/osint-fetch.log",
        metadata: {},
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString()
      },
      capture: {
        id: "capture-1",
        investigation_id: OSINT_INVESTIGATION_ID,
        source_id: "source-1",
        connector_id: "brave",
        url: "https://example.test/orquestra",
        canonical_url: "https://example.test/orquestra",
        title: "Orquestra Evidence",
        content_type: "text/html",
        content_hash: "abc123",
        snapshot_path: "/tmp/capture.bin",
        normalized_path: "/tmp/capture.md",
        fetched_at: new Date().toISOString(),
        via_tor: false,
        license_policy: "metadata_only",
        metadata: {},
        created_at: new Date().toISOString()
      },
      evidence: [
        {
          id: "evidence-1",
          investigation_id: OSINT_INVESTIGATION_ID,
          source_id: "source-1",
          capture_id: "capture-1",
          title: "Orquestra Evidence",
          content: "O Orquestra mantém memória local-first com aprovação explícita.",
          validation_status: "pending",
          source_quality: 0.82,
          entity_ids: [],
          claim_ids: ["claim-1"],
          metadata: { url: "https://example.test/orquestra" },
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString()
        }
      ],
      claims: [
        {
          id: "claim-1",
          investigation_id: OSINT_INVESTIGATION_ID,
          evidence_ids: ["evidence-1"],
          title: "Claim: memória local-first",
          content: "A memória do Orquestra é local-first e só promove conteúdo aprovado.",
          confidence: 0.76,
          status: "pending",
          metadata: {},
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString()
        }
      ]
    });
  }

  if (path === "/api/osint/evidence/evidence-1/approve") {
    return jsonResponse({
      id: "evidence-1",
      investigation_id: OSINT_INVESTIGATION_ID,
      source_id: "source-1",
      capture_id: "capture-1",
      title: "Orquestra Evidence",
      content: "O Orquestra mantém memória local-first com aprovação explícita.",
      validation_status: "approved",
      source_quality: 0.82,
      entity_ids: [],
      claim_ids: ["claim-1"],
      metadata: { url: "https://example.test/orquestra" },
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString()
    });
  }

  if (path === "/api/osint/claims/claim-1/approve") {
    return jsonResponse({
      claim: {
        id: "claim-1",
        investigation_id: OSINT_INVESTIGATION_ID,
        evidence_ids: ["evidence-1"],
        title: "Claim: memória local-first",
        content: "A memória do Orquestra é local-first e só promove conteúdo aprovado.",
        confidence: 0.76,
        status: "approved",
        memory_record_id: "memory-1",
        metadata: {},
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString()
      },
      memory_record: {
        id: "memory-1",
        project_id: "project-1",
        session_id: SESSION_ID,
        scope: "source_fact",
        memory_kind: "reference",
        source: "osint_claim:claim-1",
        content: "A memória do Orquestra é local-first e só promove conteúdo aprovado.",
        confidence: 0.76,
        approved_for_training: false,
        metadata: { channel: "osint", source_url: "https://example.test/orquestra" },
        created_at: new Date().toISOString()
      }
    });
  }

  if (path === "/api/osint/export/dataset-bundle") {
    return jsonResponse({
      investigation_id: OSINT_INVESTIGATION_ID,
      record_count: 1,
      skipped_count: 0,
      export_path: "/tmp/osint-dataset.json",
      records: [{ instruction: "Claim: memória local-first", response: "A memória do Orquestra é local-first." }]
    });
  }

  if (path === "/api/remote/trainplane/config") {
    return jsonResponse({
      id: "default",
      base_url: "http://127.0.0.1:8818",
      region: "us-east-1",
      instance_id: "i-123456789",
      bucket: "orquestra-trainplane",
      ssm_enabled: true,
      token_configured: true,
      token_keychain_service: "ai.orquestra.trainplane",
      default_training_profile: { execution_mode: "qlora", max_steps: 12 },
      default_serving_profile: { engine: "vllm", mode: "adapter-first" },
      metadata: {},
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString()
    });
  }

  if (path === "/api/remote/trainplane/base-models") {
    return jsonResponse([
      {
        id: "base-model-1",
        name: "Meta-Llama-3.1-8B-Instruct",
        source_kind: "huggingface_ref",
        source_ref: "meta-llama/Meta-Llama-3.1-8B-Instruct",
        storage_uri: "s3://trainplane/base-models/llama-3.1",
        size_bytes: 1024,
        checksum_sha256: "abc123",
        format: "huggingface",
        status: "ready",
        metadata: {},
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString()
      }
    ]);
  }

  if (path === "/api/remote/trainplane/dataset-bundles") {
    return jsonResponse([
      {
        id: "dataset-1",
        project_slug: "orquestra-lab",
        name: "approved-memory-bundle",
        source: "orquestra_local",
        storage_uri: "s3://trainplane/datasets/approved-memory-bundle",
        record_count: 42,
        stats: { records: 42 },
        schema_version: "orquestra-trainplane-v1",
        metadata: {},
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString()
      }
    ]);
  }

  if (path === "/api/remote/trainplane/runs") {
    return jsonResponse([
      {
        id: REMOTE_RUN_ID,
        project_slug: "orquestra-lab",
        name: "research-adapter-run",
        base_model_id: "base-model-1",
        dataset_bundle_id: "dataset-1",
        status: "running",
        summary: "Fine-tuning remoto adapter-first",
        profile: { execution_mode: "qlora", max_steps: 12 },
        logs_path: "/tmp/trainplane-run.log",
        artifact_id: REMOTE_ARTIFACT_ID,
        output: {},
        current_step: 6,
        total_steps: 12,
        cancel_requested: false,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        started_at: new Date().toISOString(),
        finished_at: null,
        metrics: [],
        checkpoints: [],
        artifact: null,
        mirrored_job_id: "job-remote-1"
      }
    ]);
  }

  if (path === `/api/remote/trainplane/runs/${REMOTE_RUN_ID}`) {
    return jsonResponse({
      id: REMOTE_RUN_ID,
      project_slug: "orquestra-lab",
      name: "research-adapter-run",
      base_model_id: "base-model-1",
      dataset_bundle_id: "dataset-1",
      status: "running",
      summary: "Fine-tuning remoto adapter-first",
      profile: { execution_mode: "qlora", max_steps: 12 },
      logs_path: "/tmp/trainplane-run.log",
      artifact_id: REMOTE_ARTIFACT_ID,
      output: { status: "running" },
      current_step: 6,
      total_steps: 12,
      cancel_requested: false,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      started_at: new Date().toISOString(),
      finished_at: null,
      metrics: [
        {
          id: "metric-1",
          run_id: REMOTE_RUN_ID,
          step_index: 1,
          epoch: 0.1,
          loss: 2.0,
          eval_loss: 2.1,
          learning_rate: 0.0002,
          grad_norm: 1.1,
          gpu_util: 70,
          gpu_mem_gb: 8.2,
          gpu_temp_c: 62,
          cpu_percent: 31,
          ram_percent: 44,
          disk_percent: 28,
          network_mbps: 21,
          metadata: {},
          created_at: new Date().toISOString()
        },
        {
          id: "metric-2",
          run_id: REMOTE_RUN_ID,
          step_index: 2,
          epoch: 0.2,
          loss: 1.6,
          eval_loss: 1.7,
          learning_rate: 0.0001,
          grad_norm: 1.2,
          gpu_util: 76,
          gpu_mem_gb: 8.8,
          gpu_temp_c: 64,
          cpu_percent: 34,
          ram_percent: 47,
          disk_percent: 29,
          network_mbps: 22,
          metadata: {},
          created_at: new Date().toISOString()
        }
      ],
      checkpoints: [
        {
          id: "checkpoint-1",
          run_id: REMOTE_RUN_ID,
          step_index: 6,
          label: "checkpoint-6",
          storage_uri: "s3://trainplane/checkpoints/step-6",
          metadata: {},
          created_at: new Date().toISOString()
        }
      ],
      artifact: {
        id: REMOTE_ARTIFACT_ID,
        run_id: REMOTE_RUN_ID,
        name: "research-adapter-run-adapter",
        artifact_type: "adapter",
        base_model_name: "Meta-Llama-3.1-8B-Instruct",
        storage_uri: "s3://trainplane/artifacts/research-adapter-run-adapter",
        format: "adapter-only",
        status: "ready",
        benchmark: { correctness: 0.84, faithfulness: 0.82 },
        serving_endpoint: { mode: "simulated" },
        metadata: {},
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString()
      }
    });
  }

  if (path === "/api/remote/trainplane/artifacts") {
    return jsonResponse([
      {
        id: REMOTE_ARTIFACT_ID,
        run_id: REMOTE_RUN_ID,
        name: "research-adapter-run-adapter",
        artifact_type: "adapter",
        base_model_name: "Meta-Llama-3.1-8B-Instruct",
        storage_uri: "s3://trainplane/artifacts/research-adapter-run-adapter",
        format: "adapter-only",
        status: "ready",
        benchmark: { correctness: 0.84, faithfulness: 0.82 },
        serving_endpoint: { mode: "simulated" },
        metadata: {},
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        mirrored_artifact_id: "registry-artifact-1"
      }
    ]);
  }

  if (path === "/api/remote/trainplane/evaluations") {
    return jsonResponse([
      {
        id: "evaluation-1",
        candidate_artifact_id: REMOTE_ARTIFACT_ID,
        baseline_mode: "lmstudio_local",
        baseline_ref: "lmstudio/ministral",
        suite_name: "orquestra-eval-lab",
        status: "succeeded",
        summary_scores: { correctness: 0.84, faithfulness: 0.82 },
        results: [],
        metadata: {},
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString()
      }
    ]);
  }

  if (path === "/api/remote/trainplane/comparisons") {
    return jsonResponse([
      {
        id: "comparison-1",
        candidate_artifact_id: REMOTE_ARTIFACT_ID,
        baseline_mode: "lmstudio_local",
        baseline_ref: "lmstudio/ministral",
        prompt_set_name: "orquestra-compare-lab",
        status: "succeeded",
        summary_scores: { correctness: 0.84, faithfulness: 0.82 },
        cases: [],
        metadata: {},
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString()
      }
    ]);
  }

  if (path === `/api/chat/sessions/${SESSION_ID}/messages`) {
    return jsonResponse([]);
  }

  if (path === `/api/chat/sessions/${SESSION_ID}/summary`) {
    return jsonResponse({
      session_id: SESSION_ID,
      current_state: "Resumo compacto ativo.",
      next_steps: "- Validar planner\n- Executar workflow",
      relevant_files: ["orquestra_ai/app.py"],
      commands_run: [],
      errors_and_fixes: [],
      worklog: ["user: revisar planner"],
      compacted_from_message_count: 4,
      metadata: {},
      updated_at: new Date().toISOString(),
      compaction_state: {
        session_id: SESSION_ID,
        summary_version: 2,
        next_steps: ["Validar planner", "Executar workflow"],
        preserved_recent_turns: 6,
        compacted_message_count: 4,
        compacted_at: new Date().toISOString(),
        metadata: {}
      }
    });
  }

  if (path === `/api/chat/sessions/${SESSION_ID}/transcript`) {
    return jsonResponse({
      session_id: SESSION_ID,
      storage_path: "/tmp/transcript.jsonl",
      message_count: 3,
      transcript_bytes: 120,
      metadata: {},
      entries: [
        { role: "user", content: "vamos revisar o planner" },
        { role: "assistant", content: "planner reconstruído" }
      ]
    });
  }

  if (path === `/api/chat/sessions/${SESSION_ID}/profile`) {
    return jsonResponse({
      objective: "Validar planner e compaction.",
      preset: "assistant",
      preset_label: "Assistente",
      memory_policy: { enabled: true, auto_capture: true, scopes: ["session_memory"] },
      rag_policy: { enabled: true, collections: ["knowledge_base"], include_workspace: true, include_sources: true },
      persona_config: { style_notes: "Operacional" }
    });
  }

  if (path === `/api/chat/sessions/${SESSION_ID}/planner` || path === `/api/chat/sessions/${SESSION_ID}/planner/rebuild`) {
    return jsonResponse({
      snapshot: {
        id: "planner-1",
        session_id: SESSION_ID,
        objective: "Validar planner e compaction.",
        strategy: "Seguir pelo resumo e tarefas.",
        next_steps: ["Validar planner", "Executar workflow"],
        risks: ["Sem dados externos"],
        metadata: {},
        last_planned_at: new Date().toISOString(),
        updated_at: new Date().toISOString()
      },
      tasks: [
        {
          id: TASK_ID,
          session_id: SESSION_ID,
          subject: "Validar planner",
          description: "Checar sincronização entre resumo e tasks.",
          active_form: "Validar planner",
          status: "pending",
          owner: "orquestra",
          blocked_by: [TASK_DEP_ID],
          blocks: [],
          position: 0,
          metadata: {},
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString()
        },
        {
          id: TASK_DEP_ID,
          session_id: SESSION_ID,
          subject: "Preparar memória base",
          description: "Organizar fatos e referências antes do workflow.",
          active_form: "Preparar memória base",
          status: "completed",
          owner: "orquestra",
          blocked_by: [],
          blocks: [TASK_ID],
          position: 1,
          metadata: {},
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString()
        }
      ]
    });
  }

  if (path === `/api/workflows/runs/${WORKFLOW_ID}`) {
    return jsonResponse({
      id: WORKFLOW_ID,
      session_id: SESSION_ID,
      task_id: TASK_ID,
      workflow_name: "session-validation",
      status: "interrupted",
      summary: "Executar validação local",
      log_path: "/tmp/workflow.log",
      output_path: "/tmp/workflow.json",
      progress: 0.5,
      cancel_requested: false,
      metadata: { recovered_after_restart: true },
      started_at: new Date().toISOString(),
      finished_at: new Date().toISOString(),
      log_tail: "[workflow] step=0 status=succeeded",
      output_exists: true,
      output_preview: {
        status: "interrupted",
        recovered: true,
        note: "resume from artifact",
        steps: [{ step: "Git diff", output: { exit_code: 0 } }]
      },
      steps: [
        {
          id: "step-1",
          run_id: WORKFLOW_ID,
          step_index: 0,
          step_type: "shell_safe",
          label: "Git diff",
          status: "interrupted",
          input: {},
          output: { exit_code: 0, log_path: "/tmp/workflow-step.log" },
          metadata: {}
        }
      ]
    });
  }

  throw new Error(`Unhandled fetch: ${path}`);
}

describe("App", () => {
  beforeEach(() => {
    vi
      .spyOn(globalThis, "fetch")
      .mockImplementation((input: RequestInfo | URL) => mockApi(String(input)) as Promise<Response>);
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("mostra compaction e planner no Assistant Workspace", async () => {
    render(<App />);

    await waitFor(() => expect(screen.getByText("Assistant Workspace")).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: /Assistant Workspace/i }));

    await waitFor(() => expect(screen.getByText("Compactar contexto")).toBeInTheDocument());
    expect(screen.getByText("Planner")).toBeInTheDocument();
    expect(screen.getAllByText("Validar planner").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Preparar memória base").length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Bloqueada por:/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Bloqueia:/i).length).toBeGreaterThan(0);
  });

  it("mostra workflows, artefatos e restart recovery no Execution Center", async () => {
    render(<App />);

    fireEvent.click(await screen.findByRole("button", { name: /Execution Center/i }));

    await waitFor(() => expect(screen.getByText("Execução multi-step")).toBeInTheDocument());
    expect(screen.getAllByText("session-validation").length).toBeGreaterThan(0);
    expect(screen.getAllByText(/task:Validar planner/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText("/tmp/workflow.json").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Interrompido e recuperado após restart").length).toBeGreaterThan(0);
    expect(screen.getAllByText(/resume from artifact/i).length).toBeGreaterThan(0);
  });

  it("mostra o painel Remote Train Plane com runs e evaluation lab", async () => {
    render(<App />);

    fireEvent.click(await screen.findByRole("button", { name: /Execution Center/i }));

    await waitFor(() => expect(screen.getByText("Remote Train Plane")).toBeInTheDocument());
    expect(screen.getAllByText("research-adapter-run").length).toBeGreaterThan(0);
    expect(screen.getAllByText("research-adapter-run-adapter").length).toBeGreaterThan(0);
    expect(screen.getByText(/EC2 train plane, avaliação comparativa/i)).toBeInTheDocument();
    expect(screen.getByText(/Sincronizar base model/i)).toBeInTheDocument();
    expect(screen.getByText(/Rodar comparison/i)).toBeInTheDocument();
  });

  it("mostra o OSINT Lab com conectores, evidências e claims aprováveis", async () => {
    render(<App />);

    fireEvent.click(await screen.findByRole("button", { name: /OSINT Lab/i }));

    await waitFor(() => expect(screen.getByText("Busca web, fetch e evidência rastreável")).toBeInTheDocument());
    expect(screen.getAllByText("Investigação Orquestra").length).toBeGreaterThan(0);
    expect(screen.getByText("Brave Search")).toBeInTheDocument();
    expect(screen.getByText("Orquestra Evidence")).toBeInTheDocument();
    expect(screen.getByText("Claim: memória local-first")).toBeInTheDocument();
    expect(screen.getByText(/Adicionar seed/i)).toBeInTheDocument();
  });
});
