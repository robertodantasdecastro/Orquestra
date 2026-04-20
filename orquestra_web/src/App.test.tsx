import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import App from "./App";

const SESSION_ID = "session-1";
const WORKFLOW_ID = "workflow-1";

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
            task_id: null,
            workflow_name: "session-validation",
            status: "running",
            summary: "Executar validação local",
            log_path: "/tmp/workflow.log",
            output_path: "/tmp/workflow.json",
            progress: 0.5,
            cancel_requested: false,
            metadata: {},
            started_at: new Date().toISOString(),
            finished_at: null,
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
            task_id: null,
            workflow_name: "session-validation",
            status: "running",
            summary: "Executar validação local",
            log_path: "/tmp/workflow.log",
            output_path: "/tmp/workflow.json",
            progress: 0.5,
            cancel_requested: false,
            metadata: {},
            started_at: new Date().toISOString(),
            finished_at: null,
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
          id: "task-1",
          session_id: SESSION_ID,
          subject: "Validar planner",
          description: "Checar sincronização entre resumo e tasks.",
          active_form: "Validar planner",
          status: "pending",
          owner: "orquestra",
          blocked_by: [],
          blocks: [],
          position: 0,
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
      task_id: null,
      workflow_name: "session-validation",
      status: "running",
      summary: "Executar validação local",
      log_path: "/tmp/workflow.log",
      output_path: "/tmp/workflow.json",
      progress: 0.5,
      cancel_requested: false,
      metadata: {},
      started_at: new Date().toISOString(),
      finished_at: null,
      log_tail: "[workflow] step=0 status=succeeded",
      steps: [
        {
          id: "step-1",
          run_id: WORKFLOW_ID,
          step_index: 0,
          step_type: "shell_safe",
          label: "Git diff",
          status: "succeeded",
          input: {},
          output: {},
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
  });

  it("mostra workflows no Execution Center", async () => {
    render(<App />);

    fireEvent.click(await screen.findByRole("button", { name: /Execution Center/i }));

    await waitFor(() => expect(screen.getByText("Execução multi-step")).toBeInTheDocument());
    expect(screen.getAllByText("session-validation").length).toBeGreaterThan(0);
  });
});
