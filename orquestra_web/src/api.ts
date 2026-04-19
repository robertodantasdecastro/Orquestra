export type HealthState = {
  ok: boolean;
  app: string;
  workspace_root: string;
  database_url: string;
  redis_url: string;
  qdrant_url?: string | null;
  qdrant_path: string;
  web_enabled: boolean;
  providers: number;
  projects: number;
  memory_topics: number;
  workspace_scans: number;
};

export type ProviderProfile = {
  id: string;
  provider_id: string;
  label: string;
  transport: string;
  base_url?: string | null;
  api_key_env?: string | null;
  default_model?: string | null;
  model_prefix?: string | null;
  enabled: boolean;
  capabilities: string[];
  config: Record<string, unknown>;
  updated_at: string;
};

export type Project = {
  id: string;
  slug: string;
  name: string;
  description: string;
  default_provider_id: string;
  default_model: string;
  created_at: string;
};

export type ChatSession = {
  id: string;
  project_id?: string | null;
  title: string;
  provider_id: string;
  model_name: string;
  status?: string;
  metadata?: Record<string, unknown>;
  created_at: string;
  updated_at?: string;
  last_message_at?: string;
};

export type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  provider_id?: string | null;
  model_name?: string | null;
  usage: Record<string, unknown>;
  latency_seconds?: number | null;
  created_at: string;
};

export type SessionSummary = {
  id?: string;
  session_id: string;
  current_state: string;
  next_steps: string;
  relevant_files: string[];
  commands_run: string[];
  errors_and_fixes: string[];
  worklog: string[];
  compacted_from_message_count: number;
  storage_path: string;
  metadata: Record<string, unknown>;
  updated_at?: string;
};

export type TranscriptEntry = {
  timestamp?: string;
  role?: string;
  content?: string;
  metadata?: Record<string, unknown>;
};

export type SessionTranscript = {
  session_id: string;
  storage_path: string;
  message_count: number;
  transcript_bytes: number;
  metadata: Record<string, unknown>;
  entries: TranscriptEntry[];
};

export type MemoryRecord = {
  id: string;
  project_id?: string | null;
  session_id?: string | null;
  topic_id?: string | null;
  scope: string;
  source: string;
  content: string;
  confidence: number;
  ttl_seconds?: number | null;
  approved_for_training: boolean;
  metadata: Record<string, unknown>;
  created_at: string;
};

export type MemoryTopic = {
  id: string;
  project_id?: string | null;
  scope: string;
  slug: string;
  title: string;
  description: string;
  topic_path: string;
  manifest_path: string;
  metadata: Record<string, unknown>;
  last_used_at: string;
  created_at: string;
  updated_at: string;
};

export type MemoryRecallItem = {
  id?: string;
  title: string;
  content: string;
  scope?: string;
  source?: string;
  relevance?: number;
  metadata?: Record<string, unknown>;
};

export type TrainingCandidate = {
  id: string;
  project_id?: string | null;
  session_id?: string | null;
  source: string;
  instruction: string;
  context: string;
  response: string;
  labels: Record<string, unknown>;
  approved: boolean;
  dataset_path: string;
  metadata: Record<string, unknown>;
  created_at: string;
};

export type WorkspaceScan = {
  id: string;
  project_id?: string | null;
  root_path: string;
  prompt_hint: string;
  status: string;
  total_assets: number;
  total_bytes: number;
  inventory_path: string;
  metadata: Record<string, unknown>;
  insights?: WorkspaceInsight[];
  created_at: string;
  updated_at: string;
};

export type WorkspaceAsset = {
  id: string;
  scan_id: string;
  absolute_path: string;
  relative_path: string;
  parent_relative_path?: string | null;
  asset_kind: string;
  mime_type?: string | null;
  extension?: string | null;
  size_bytes: number;
  sha256: string;
  depth: number;
  modified_at: string;
  title: string;
  summary_excerpt: string;
  extraction_state: string;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

export type WorkspaceDerivative = {
  id: string;
  asset_id: string;
  derivative_kind: string;
  storage_path: string;
  media_type?: string | null;
  expires_at?: string | null;
  metadata: Record<string, unknown>;
  created_at: string;
};

export type WorkspaceInsight = {
  id: string;
  scan_id: string;
  asset_id?: string | null;
  kind: string;
  title: string;
  content: string;
  relevance: number;
  metadata: Record<string, unknown>;
  created_at: string;
};

export type WorkspacePreview = {
  asset: WorkspaceAsset;
  derivatives: WorkspaceDerivative[];
  preview_text?: string;
  metadata: Record<string, unknown>;
};

export type WorkspaceQueryResult = {
  scan_id: string;
  answer: string;
  provider_id: string;
  model_name: string;
  usage: Record<string, unknown>;
  latency_seconds: number;
  assets: Array<{
    asset_id: string;
    title: string;
    relative_path: string;
    asset_kind: string;
    summary_excerpt: string;
    score: number;
    metadata: Record<string, unknown>;
  }>;
};

export type JobRecord = {
  id: string;
  project_id?: string | null;
  job_family: string;
  connector: string;
  status: string;
  spec: Record<string, unknown>;
  logs_path?: string | null;
  outputs: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

export type ModelArtifact = {
  id: string;
  project_id?: string | null;
  name: string;
  artifact_type: string;
  source_pipeline: string;
  base_model: string;
  storage_uri: string;
  format: string;
  benchmark: Record<string, unknown>;
  created_at: string;
};

export type ConnectorDescriptor = {
  connector_id: string;
  label: string;
  category: string;
  status: string;
  description: string;
  required_env: string[];
  capabilities: string[];
  config: Record<string, unknown>;
  ready: boolean;
};

export type RagResult = {
  answer: string;
  model_name?: string;
  provider_id?: string;
  citations?: Array<{ source?: string; title?: string; channel?: string }>;
  evaluation?: Record<string, number>;
  usage?: Record<string, unknown>;
  latency_seconds?: number;
};

export type RegistryCompareResult = {
  baseline: ModelArtifact;
  candidate: ModelArtifact;
  delta: Record<string, number>;
};

export type RuntimeService = {
  service_id: string;
  label: string;
  category: string;
  ready: boolean;
  status: string;
  summary: string;
  detail: string;
  metadata: Record<string, unknown>;
};

export type RuntimeMetric = {
  id: string;
  label: string;
  value: number;
  helper: string;
};

export type OpsAction = {
  action_id: string;
  label: string;
  summary: string;
  command_preview: string;
  kind: string;
};

export type OpsRun = {
  run_id: string;
  action_id: string;
  label: string;
  status: string;
  command: string;
  cwd: string;
  log_path: string;
  started_at: string;
  finished_at?: string | null;
  exit_code?: number | null;
  log_tail: string;
};

export type OpsDashboard = {
  generated_at: string;
  services: RuntimeService[];
  metrics: RuntimeMetric[];
  process_snapshot: {
    background_processes: Array<{ pid: number; command: string; summary: string }>;
    tmux_sessions: string[];
    listeners: { api: boolean; web: boolean };
    recent_sessions: ChatSession[];
    recent_scans: WorkspaceScan[];
    recent_jobs: JobRecord[];
    runtime_paths: Record<string, string>;
  };
  memory_snapshot: {
    topics: number;
    records: number;
    training_candidates: number;
    message_count: number;
    scope_breakdown: Array<{ scope: string; count: number }>;
    recent_records: MemoryRecord[];
    recent_topics: MemoryTopic[];
    recent_candidates: Array<{
      id: string;
      source: string;
      instruction: string;
      approved: boolean;
      created_at: string;
    }>;
    storage: {
      database_size_bytes: number;
      memorygraph_dir_exists: boolean;
      workspace_dir_exists: boolean;
      assets_indexed: number;
      scans_total: number;
    };
  };
  execution_snapshot: {
    providers: ProviderProfile[];
    projects: Project[];
    connectors: ConnectorDescriptor[];
    training_jobs: JobRecord[];
    remote_jobs: JobRecord[];
    registry_models: ModelArtifact[];
    actions: OpsAction[];
    runs: OpsRun[];
    artifacts: {
      app_bundle_path: string;
      app_bundle_exists: boolean;
      dmg_path: string;
      dmg_exists: boolean;
      installer_path: string;
      installer_exists: boolean;
      uninstaller_path: string;
      uninstaller_exists: boolean;
      connectors_ready: number;
    };
  };
};

const API_BASE = (import.meta.env.VITE_ORQUESTRA_API_BASE || "").replace(/\/$/, "");

function apiPath(path: string) {
  if (!API_BASE) return path;
  return `${API_BASE}${path}`;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(apiPath(path), {
    ...init,
    headers: {
      ...(init?.body ? { "Content-Type": "application/json" } : {}),
      ...(init?.headers ?? {})
    }
  });
  if (!response.ok) {
    throw new Error(await response.text());
  }
  return response.json() as Promise<T>;
}

export async function getHealth() {
  return request<HealthState>("/api/health");
}

export async function listProviders() {
  return request<ProviderProfile[]>("/api/providers");
}

export async function upsertProvider(payload: {
  provider_id: string;
  label: string;
  transport: string;
  base_url?: string | null;
  api_key_env?: string | null;
  default_model?: string | null;
  model_prefix?: string | null;
  enabled?: boolean;
  capabilities?: string[];
  config?: Record<string, unknown>;
}) {
  return request<ProviderProfile>("/api/providers", { method: "PUT", body: JSON.stringify(payload) });
}

export async function listProjects() {
  return request<Project[]>("/api/projects");
}

export async function createProject(payload: {
  slug: string;
  name: string;
  description: string;
  default_provider_id: string;
  default_model: string;
}) {
  return request<Project>("/api/projects", { method: "POST", body: JSON.stringify(payload) });
}

export async function listModels(providerId?: string) {
  const query = providerId ? `?provider_id=${encodeURIComponent(providerId)}` : "";
  return request<{ provider_id: string; models: string[] }>(`/api/models${query}`);
}

export async function createSession(payload: {
  project_id?: string | null;
  title: string;
  provider_id?: string | null;
  model_name?: string | null;
}) {
  return request<ChatSession>("/api/chat/sessions", { method: "POST", body: JSON.stringify(payload) });
}

export async function listSessions(projectId?: string) {
  const query = projectId ? `?project_id=${encodeURIComponent(projectId)}` : "";
  return request<ChatSession[]>(`/api/chat/sessions${query}`);
}

export async function listMessages(sessionId: string) {
  return request<ChatMessage[]>(`/api/chat/sessions/${sessionId}/messages`);
}

export async function resumeSession(sessionId: string) {
  return request<Record<string, unknown>>(`/api/chat/sessions/${sessionId}/resume`, { method: "POST" });
}

export async function getTranscript(sessionId: string) {
  return request<SessionTranscript>(`/api/chat/sessions/${sessionId}/transcript`);
}

export async function getSummary(sessionId: string) {
  return request<SessionSummary>(`/api/chat/sessions/${sessionId}/summary`);
}

export async function listMemory(projectId?: string, scope?: string) {
  const params = new URLSearchParams();
  if (projectId) params.set("project_id", projectId);
  if (scope) params.set("scope", scope);
  const query = params.toString();
  return request<MemoryRecord[]>(`/api/memory${query ? `?${query}` : ""}`);
}

export async function createMemory(payload: {
  project_id?: string | null;
  session_id?: string | null;
  topic_id?: string | null;
  scope: string;
  source: string;
  content: string;
  confidence: number;
  ttl_seconds?: number | null;
  approved_for_training: boolean;
  metadata?: Record<string, unknown>;
}) {
  return request<MemoryRecord>("/api/memory/upsert", { method: "POST", body: JSON.stringify(payload) });
}

export async function listMemoryTopics(projectId?: string, scope?: string) {
  const params = new URLSearchParams();
  if (projectId) params.set("project_id", projectId);
  if (scope) params.set("scope", scope);
  const query = params.toString();
  return request<MemoryTopic[]>(`/api/memory/topics${query ? `?${query}` : ""}`);
}

export async function recallMemory(payload: {
  query: string;
  project_id?: string | null;
  scopes?: string[];
  limit?: number;
}) {
  return request<{ query: string; items: MemoryRecallItem[] }>("/api/memory/recall", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export async function promoteMemory(payload: {
  project_id?: string | null;
  scope?: string;
  title: string;
  content: string;
  source?: string;
  metadata?: Record<string, unknown>;
}) {
  return request<{ topic: MemoryTopic; record: MemoryRecord }>("/api/memory/promote", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export async function listTrainingCandidates(projectId?: string) {
  const query = projectId ? `?project_id=${encodeURIComponent(projectId)}` : "";
  return request<TrainingCandidate[]>(`/api/memory/training-candidates${query}`);
}

export async function createTrainingCandidate(payload: {
  project_id?: string | null;
  session_id?: string | null;
  source?: string;
  instruction: string;
  context?: string;
  response: string;
  labels?: Record<string, unknown>;
  approved?: boolean;
  metadata?: Record<string, unknown>;
}) {
  return request<TrainingCandidate>("/api/memory/training-candidates", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export async function queryRag(payload: {
  question: string;
  project_id?: string | null;
  session_id?: string;
  collection_name?: string;
  provider_id?: string;
  model_name?: string;
  expected_output?: string;
  task_type?: string;
  remember?: boolean;
  mock_llm?: boolean;
}) {
  return request<RagResult>("/api/rag/query", { method: "POST", body: JSON.stringify(payload) });
}

export async function listWorkspaceScans(projectId?: string) {
  const query = projectId ? `?project_id=${encodeURIComponent(projectId)}` : "";
  return request<WorkspaceScan[]>(`/api/workspace/scans${query}`);
}

export async function attachDirectory(payload: {
  project_id?: string | null;
  root_path: string;
  prompt_hint?: string;
}) {
  return request<WorkspaceScan>("/api/workspace/attach-directory", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export async function getWorkspaceScan(scanId: string) {
  return request<WorkspaceScan>(`/api/workspace/scans/${scanId}`);
}

export async function listWorkspaceAssets(scanId: string, assetKind?: string) {
  const params = new URLSearchParams({ scan_id: scanId });
  if (assetKind) params.set("asset_kind", assetKind);
  return request<WorkspaceAsset[]>(`/api/workspace/assets?${params.toString()}`);
}

export async function queryWorkspace(payload: {
  scan_id: string;
  prompt: string;
  provider_id?: string | null;
  model_name?: string | null;
  force_extract?: boolean;
  mock_response?: boolean;
}) {
  return request<WorkspaceQueryResult>("/api/workspace/query", { method: "POST", body: JSON.stringify(payload) });
}

export async function extractWorkspaceAsset(assetId: string, payload?: { prompt_hint?: string; force?: boolean }) {
  return request<WorkspacePreview>(`/api/workspace/assets/${assetId}/extract`, {
    method: "POST",
    body: JSON.stringify(payload ?? {})
  });
}

export async function previewWorkspaceAsset(assetId: string) {
  return request<WorkspacePreview>(`/api/workspace/assets/${assetId}/preview`);
}

export function rawPreviewUrl(assetId: string) {
  return apiPath(`/api/workspace/assets/${assetId}/preview?raw=1`);
}

export async function openWorkspaceAsset(assetId: string) {
  return request<{ absolute_path: string; strategy: string; title: string }>(`/api/workspace/assets/${assetId}/open`, {
    method: "POST"
  });
}

export async function memorizeWorkspaceAsset(assetId: string, payload?: { project_id?: string | null; scope?: string; source?: string }) {
  return request<MemoryRecord>(`/api/workspace/assets/${assetId}/memorize`, {
    method: "POST",
    body: JSON.stringify(payload ?? {})
  });
}

export async function listTrainingJobs() {
  return request<JobRecord[]>("/api/training/jobs");
}

export async function listRemoteJobs() {
  return request<JobRecord[]>("/api/remote/jobs");
}

export async function createJob(kind: "training" | "remote", payload: { project_id?: string | null; connector: string; spec: Record<string, unknown> }) {
  return request<JobRecord>(`/api/${kind}/jobs`, { method: "POST", body: JSON.stringify(payload) });
}

export async function getRemoteJobLogs(jobId: string) {
  return request<{ job_id: string; logs_path?: string | null; content: string }>(`/api/remote/jobs/${jobId}/logs`);
}

export async function listRegistryModels() {
  return request<ModelArtifact[]>("/api/registry/models");
}

export async function createRegistryModel(payload: {
  project_id?: string | null;
  name: string;
  artifact_type: string;
  source_pipeline?: string;
  base_model?: string;
  storage_uri?: string;
  format?: string;
  benchmark?: Record<string, unknown>;
}) {
  return request<ModelArtifact>("/api/registry/models", { method: "POST", body: JSON.stringify(payload) });
}

export async function compareRegistryModels(payload: { baseline_artifact_id: string; candidate_artifact_id: string }) {
  return request<RegistryCompareResult>("/api/registry/compare", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export async function listConnectors() {
  return request<ConnectorDescriptor[]>("/api/connectors");
}

export async function createDeployment(projectId: string, payload: { artifact_id: string; environment?: string; notes?: string }) {
  return request<Record<string, unknown>>(`/api/projects/${projectId}/deployments`, {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export async function getOpsDashboard() {
  return request<OpsDashboard>("/api/ops/dashboard");
}

export async function listOpsActions() {
  return request<OpsAction[]>("/api/ops/actions");
}

export async function listOpsRuns() {
  return request<OpsRun[]>("/api/ops/runs");
}

export async function getOpsRun(runId: string) {
  return request<OpsRun>(`/api/ops/runs/${runId}`);
}

export async function createOpsRun(payload: { action_id: string }) {
  return request<OpsRun>("/api/ops/runs", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export async function streamChat(
  payload: {
    project_id?: string | null;
    session_id?: string | null;
    provider_id?: string | null;
    model_name?: string | null;
    message: string;
    temperature?: number;
    max_tokens?: number;
    remember?: boolean;
    mock_response?: boolean;
  },
  handlers: {
    onSession: (payload: { session_id: string; provider_id: string; model_name: string }) => void;
    onDelta: (text: string) => void;
    onSummary?: (payload: { current_state: string; updated_at: string }) => void;
    onDone: (payload: { provider_id: string; model_name: string; usage: Record<string, unknown>; latency_seconds: number }) => void;
  }
) {
  const response = await fetch(apiPath("/api/chat/stream"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  if (!response.ok || !response.body) {
    throw new Error(await response.text());
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) {
      break;
    }
    buffer += decoder.decode(value, { stream: true });
    const chunks = buffer.split("\n\n");
    buffer = chunks.pop() ?? "";
    for (const chunk of chunks) {
      const eventLine = chunk.split("\n").find((line) => line.startsWith("event: "));
      const dataLine = chunk.split("\n").find((line) => line.startsWith("data: "));
      if (!eventLine || !dataLine) {
        continue;
      }
      const event = eventLine.replace("event: ", "").trim();
      const data = JSON.parse(dataLine.replace("data: ", ""));
      if (event === "session") {
        handlers.onSession(data);
      } else if (event === "delta") {
        handlers.onDelta(data.content ?? "");
      } else if (event === "summary") {
        handlers.onSummary?.(data);
      } else if (event === "done") {
        handlers.onDone(data);
      }
    }
  }
}
