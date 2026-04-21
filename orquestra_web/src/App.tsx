import { useEffect, useMemo, useState } from "react";
import {
  ChatMessage,
  ChatSession,
  AgentProfile,
  HealthState,
  JobRecord,
  MemoryRecord,
  MemoryReviewCandidate,
  MemoryTopic,
  ModelArtifact,
  OsintClaim,
  OsintConfig,
  OsintConnectorState,
  OsintEvidence,
  OsintInvestigation,
  OsintRun,
  OsintSource,
  OsintSourceRegistryEntry,
  OpsDashboard,
  OpsRun,
  PlannerSnapshot,
  Project,
  RagResult,
  RemoteArtifact,
  RemoteBaseModel,
  RemoteComparisonRun,
  RemoteDatasetBundle,
  RemoteEvaluationRun,
  RemoteTrainPlaneConfig,
  RemoteTrainPlaneConnectionState,
  RemoteTrainingRun,
  RegistryCompareResult,
  RuntimeSettingsReport,
  SessionCompactionState,
  SessionSummary,
  SessionProfile,
  SessionTask,
  SessionTranscript,
  SecretMetadata,
  StorageLocation,
  StorageAssignment,
  TrainingCandidate,
  WorkflowRun,
  WorkspaceAsset,
  WorkspacePreview,
  WorkspaceQueryResult,
  WorkspaceScan,
  approveMemoryCandidate,
  approveOsintClaim,
  approveOsintEvidence,
  attachDirectory,
  cancelWorkflowRun,
  compactSession,
  compareRegistryModels,
  createDeployment,
  createJob,
  createMemory,
  createOpsRun,
  createProject,
  cancelRemoteTrainPlaneRun,
  createRemoteTrainPlaneComparison,
  createRemoteTrainPlaneEvaluation,
  createRemoteTrainPlaneRun,
  createSecret,
  createStorageLocation,
  createOsintInvestigation,
  createOsintSourceRegistryEntry,
  createSession,
  createSessionTask,
  createWorkflowRun,
  disableOsintConnector,
  enableOsintConnector,
  exportOsintDatasetBundle,
  extractWorkspaceAsset,
  fetchOsintInvestigation,
  getRemoteTrainPlaneConfig,
  getRemoteTrainPlaneRun,
  getHealth,
  getOpsDashboard,
  getOsintConfig,
  getOsintInvestigation,
  getOpsRun,
  getPlanner,
  getRemoteJobLogs,
  getSessionProfile,
  getSummary,
  getRuntimeSettings,
  getTranscript,
  getWorkflowRun,
  getWorkspaceScan,
  listRemoteTrainPlaneArtifacts,
  listRemoteTrainPlaneBaseModels,
  listRemoteTrainPlaneComparisons,
  listRemoteTrainPlaneDatasetBundles,
  listRemoteTrainPlaneEvaluations,
  listRemoteTrainPlaneRuns,
  mergeRemoteTrainPlaneArtifact,
  listMemory,
  listMemoryCandidates,
  listMemoryTopics,
  listMessages,
  listModels,
  listAgents,
  listModelRoutePolicies,
  listOsintClaims,
  listOsintConnectors,
  listOsintEvidence,
  listOsintInvestigations,
  listOsintRuns,
  listOsintSourceRegistry,
  listSessions,
  listSecrets,
  listStorageAssignments,
  listStorageLocations,
  listTrainingCandidates,
  listWorkflowRuns,
  listWorkspaceAssets,
  listWorkspaceScans,
  memorizeWorkspaceAsset,
  openWorkspaceAsset,
  patchSessionTask,
  patchOsintConnector,
  patchOsintInvestigation,
  patchOsintSourceRegistryEntry,
  planOsintInvestigation,
  previewWorkspaceAsset,
  promoteMemory,
  queryRag,
  queryWorkspace,
  rawPreviewUrl,
  recallMemory,
  rejectMemoryCandidate,
  rebuildPlanner,
  resumeSession,
  searchOsintInvestigation,
  promoteRemoteTrainPlaneArtifact,
  syncRemoteTrainPlaneBaseModel,
  syncRemoteTrainPlaneDatasetBundle,
  streamChat,
  testRemoteTrainPlaneConnection,
  refreshModelCatalog,
  simulateModelRouter,
  updateRemoteTrainPlaneConfig,
  updateOsintConfig,
  updateRuntimeSettings,
  updateStorageAssignment,
  updateSessionProfile
} from "./api";
import orquestraLogo from "./assets/orquestra-icon.png";

type ViewId = "dashboard" | "process" | "memory" | "execution" | "assistant" | "osint" | "workspace" | "settings" | "projects";

const views: Array<{ id: ViewId; title: string; helper: string }> = [
  { id: "dashboard", title: "Operations Dashboard", helper: "Serviços, artefatos, validação e estado vivo da stack." },
  { id: "process", title: "Process Center", helper: "Sessões, scans, listeners, tmux e fluxo operacional ativo." },
  { id: "memory", title: "Memory Studio", helper: "Memória durável, recall, training candidates e working memory." },
  { id: "execution", title: "Execution Center", helper: "Providers, conectores, jobs, registry e ações operacionais." },
  { id: "assistant", title: "Assistant Workspace", helper: "Conversa multi-provider com resumo e transcript separados." },
  { id: "osint", title: "OSINT Lab", helper: "Busca web nativa, conectores administráveis, evidência e claims com memória rastreável." },
  { id: "workspace", title: "Workspace Browser", helper: "Leitura multimodal inventory-first e extração sob demanda." },
  { id: "settings", title: "Settings Center", helper: "Runtime, storage multilocal, Keychain, providers, modelos e router interno." },
  { id: "projects", title: "Projects", helper: "Projetos, defaults e perfis operacionais do control plane." }
];

const serviceCategoryLabels: Record<string, string> = {
  core: "Core",
  ui: "Interface",
  runtime: "Runtime",
  external: "Externo",
  provider: "Providers",
  distribution: "Distribuição"
};

const presetOptions: Array<{ value: SessionProfile["preset"]; label: string; helper: string }> = [
  { value: "research", label: "Pesquisa", helper: "continuidade, fontes locais e citações" },
  { value: "osint", label: "OSINT", helper: "evidência, hipótese, confiança e data" },
  { value: "persona", label: "Persona", helper: "tom, vocabulário e restrições aprovadas" },
  { value: "assistant", label: "Assistente", helper: "preferências, comandos e modo de trabalho" },
  { value: "dataset", label: "Dataset", helper: "sinais revisáveis para fine-tuning futuro" }
];

function defaultSessionProfile(preset: SessionProfile["preset"] = "research"): SessionProfile {
  return {
    objective: "",
    preset,
    preset_label: presetOptions.find((item) => item.value === preset)?.label,
    memory_policy: {
      enabled: true,
      auto_capture: true,
      review_required: true,
      use_in_prompt: true,
      generate_training_candidates: preset === "dataset",
      retention: "durable_after_approval",
      scopes:
        preset === "persona"
          ? ["persona_memory", "session_memory", "semantic_memory"]
          : preset === "dataset"
            ? ["training_signal", "session_memory", "semantic_memory"]
            : ["session_memory", "episodic_memory", "semantic_memory", "workspace_memory", "source_fact"]
    },
    rag_policy: {
      enabled: true,
      collections: ["knowledge_base", "security_base"],
      memory_collection: "orquestra_memory_v1",
      include_memory: true,
      include_workspace: true,
      include_sources: true,
      top_k_memory: 6,
      top_k_sources: 4,
      top_k_workspace: 4,
      max_context_chars: 9000
    },
    persona_config: {
      tone: "",
      style_notes: presetOptions.find((item) => item.value === preset)?.helper ?? "",
      constraints: [],
      source_refs: []
    }
  };
}

function formatDate(value?: string | null) {
  if (!value) return "agora";
  return new Date(value).toLocaleString("pt-BR");
}

function formatBytes(value?: number | null) {
  const size = value ?? 0;
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
  if (size < 1024 * 1024 * 1024) return `${(size / (1024 * 1024)).toFixed(1)} MB`;
  return `${(size / (1024 * 1024 * 1024)).toFixed(2)} GB`;
}

function shortList(items: string[], empty = "Sem dados ainda.") {
  return items.length ? items.join(" • ") : empty;
}

function compactText(value: string, limit = 180) {
  const normalized = value.replace(/\s+/g, " ").trim();
  if (normalized.length <= limit) return normalized || "Sem conteúdo ainda.";
  return `${normalized.slice(0, limit - 1)}…`;
}

function safeJsonParse<T>(value: string, fallback: T): T {
  try {
    return value.trim() ? (JSON.parse(value) as T) : fallback;
  } catch {
    return fallback;
  }
}

function buildSparklinePoints(values: number[], width = 340, height = 120) {
  if (!values.length) return "";
  const max = Math.max(...values, 1);
  return values
    .map((value, index) => {
      const x = (index / Math.max(values.length - 1, 1)) * width;
      const y = height - ((value / max) * (height - 10)) - 5;
      return `${x},${y}`;
    })
    .join(" ");
}

function workflowStatusLabel(status?: string | null) {
  switch (status) {
    case "succeeded":
      return "Concluído com sucesso";
    case "failed":
      return "Falhou com saída parcial";
    case "cancelled":
      return "Cancelado";
    case "interrupted":
      return "Interrompido e recuperado após restart";
    case "running":
      return "Em execução";
    case "pending":
      return "Na fila";
    default:
      return status || "idle";
  }
}

function serviceTone(status: string, ready: boolean) {
  if (ready && status === "online") return "online";
  if (ready) return "ready";
  if (status === "idle") return "idle";
  return "offline";
}

export default function App() {
  const [view, setView] = useState<ViewId>("dashboard");
  const [health, setHealth] = useState<HealthState | null>(null);
  const [opsDashboard, setOpsDashboard] = useState<OpsDashboard | null>(null);

  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedProjectId, setSelectedProjectId] = useState("");

  const [selectedProviderId, setSelectedProviderId] = useState("lmstudio");
  const [selectedModel, setSelectedModel] = useState("");
  const [models, setModels] = useState<string[]>([]);

  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [selectedSessionId, setSelectedSessionId] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [sessionSummary, setSessionSummary] = useState<SessionSummary | null>(null);
  const [sessionTranscript, setSessionTranscript] = useState<SessionTranscript | null>(null);
  const [sessionCompaction, setSessionCompaction] = useState<SessionCompactionState | null>(null);
  const [plannerSnapshot, setPlannerSnapshot] = useState<PlannerSnapshot | null>(null);
  const [sessionTasks, setSessionTasks] = useState<SessionTask[]>([]);
  const [resumePayload, setResumePayload] = useState<Record<string, unknown> | null>(null);
  const [chatPrompt, setChatPrompt] = useState("");
  const [chatStreaming, setChatStreaming] = useState(false);
  const [chatMockMode, setChatMockMode] = useState(false);
  const [showSessionSetup, setShowSessionSetup] = useState(false);
  const [sessionSetup, setSessionSetup] = useState<SessionProfile>(() => defaultSessionProfile("research"));
  const [sessionProfile, setSessionProfile] = useState<SessionProfile | null>(null);
  const [memoryCandidates, setMemoryCandidates] = useState<MemoryReviewCandidate[]>([]);
  const [profileSaving, setProfileSaving] = useState(false);
  const [lastMemoryTelemetry, setLastMemoryTelemetry] = useState({ recallCount: 0, candidatesCreated: 0 });

  const [workspaceRootPath, setWorkspaceRootPath] = useState("");
  const [workspacePromptHint, setWorkspacePromptHint] = useState("Analisar pasta de forma inventory-first e lazy.");
  const [workspacePrompt, setWorkspacePrompt] = useState("Quais ativos do workspace devo abrir primeiro e por quê?");
  const [workspaceScans, setWorkspaceScans] = useState<WorkspaceScan[]>([]);
  const [selectedScanId, setSelectedScanId] = useState("");
  const [selectedScan, setSelectedScan] = useState<WorkspaceScan | null>(null);
  const [workspaceAssets, setWorkspaceAssets] = useState<WorkspaceAsset[]>([]);
  const [selectedAssetId, setSelectedAssetId] = useState("");
  const [assetPreview, setAssetPreview] = useState<WorkspacePreview | null>(null);
  const [workspaceResult, setWorkspaceResult] = useState<WorkspaceQueryResult | null>(null);
  const [workspaceMockMode, setWorkspaceMockMode] = useState(true);

  const [memoryRecords, setMemoryRecords] = useState<MemoryRecord[]>([]);
  const [memoryTopics, setMemoryTopics] = useState<MemoryTopic[]>([]);
  const [trainingCandidates, setTrainingCandidates] = useState<TrainingCandidate[]>([]);
  const [memoryRecallQuery, setMemoryRecallQuery] = useState("Quais são as memórias mais úteis para retomar este projeto?");
  const [memoryRecallResults, setMemoryRecallResults] = useState<Awaited<ReturnType<typeof recallMemory>> | null>(null);
  const [promoteTitle, setPromoteTitle] = useState("Arquitetura Orquestra");
  const [promoteContent, setPromoteContent] = useState("Control plane local-first com dashboard operacional, memória estruturada e execução assistida.");

  const [ragPrompt, setRagPrompt] = useState("Quais fontes devo priorizar para threat intelligence ativa?");
  const [ragResult, setRagResult] = useState<RagResult | null>(null);
  const [ragLoading, setRagLoading] = useState(false);
  const [osintConfig, setOsintConfig] = useState<OsintConfig | null>(null);
  const [osintConnectors, setOsintConnectors] = useState<OsintConnectorState[]>([]);
  const [osintRegistry, setOsintRegistry] = useState<OsintSourceRegistryEntry[]>([]);
  const [osintInvestigations, setOsintInvestigations] = useState<OsintInvestigation[]>([]);
  const [selectedInvestigationId, setSelectedInvestigationId] = useState("");
  const [selectedInvestigation, setSelectedInvestigation] = useState<OsintInvestigation | null>(null);
  const [osintRuns, setOsintRuns] = useState<OsintRun[]>([]);
  const [osintSources, setOsintSources] = useState<OsintSource[]>([]);
  const [osintEvidence, setOsintEvidence] = useState<OsintEvidence[]>([]);
  const [osintClaims, setOsintClaims] = useState<OsintClaim[]>([]);
  const [osintPlanQueries, setOsintPlanQueries] = useState<string[]>([]);
  const [osintSearchQuery, setOsintSearchQuery] = useState("orquestra ai memory graph osint");
  const [osintFetchUrl, setOsintFetchUrl] = useState("");
  const [osintInvestigationForm, setOsintInvestigationForm] = useState({
    title: "Investigação OSINT",
    objective: "Coletar fontes web rastreáveis e promover apenas claims aprovadas para memória.",
    target_entity: "Orquestra AI",
    language: "pt-BR",
    jurisdiction: "global",
    mode: "balanced"
  });
  const [osintRegistryForm, setOsintRegistryForm] = useState({
    source_key: "manual-seed",
    title: "Manual Seed",
    connector_id: "onion_manual",
    category: "manual_seed",
    access_type: "web",
    base_url: "https://example.org",
    description: "Fonte manual adicionada pelo operador."
  });

  const [projectForm, setProjectForm] = useState({
    slug: "orquestra-core",
    name: "Orquestra Core",
    description: "Projeto-base do control plane multitarefa do Orquestra.",
    default_provider_id: "lmstudio",
    default_model: "ministral"
  });

  const [registryBaselineId, setRegistryBaselineId] = useState("");
  const [registryCandidateId, setRegistryCandidateId] = useState("");
  const [registryCompare, setRegistryCompare] = useState<RegistryCompareResult | null>(null);
  const [remoteLog, setRemoteLog] = useState("");
  const [remoteTrainPlaneConfig, setRemoteTrainPlaneConfig] = useState<RemoteTrainPlaneConfig | null>(null);
  const [remoteTrainPlaneConnection, setRemoteTrainPlaneConnection] = useState<RemoteTrainPlaneConnectionState | null>(null);
  const [remoteBaseModels, setRemoteBaseModels] = useState<RemoteBaseModel[]>([]);
  const [remoteDatasetBundles, setRemoteDatasetBundles] = useState<RemoteDatasetBundle[]>([]);
  const [remoteTrainRuns, setRemoteTrainRuns] = useState<RemoteTrainingRun[]>([]);
  const [selectedRemoteTrainRunId, setSelectedRemoteTrainRunId] = useState("");
  const [selectedRemoteTrainRun, setSelectedRemoteTrainRun] = useState<RemoteTrainingRun | null>(null);
  const [remoteArtifacts, setRemoteArtifacts] = useState<RemoteArtifact[]>([]);
  const [remoteEvaluations, setRemoteEvaluations] = useState<RemoteEvaluationRun[]>([]);
  const [remoteComparisons, setRemoteComparisons] = useState<RemoteComparisonRun[]>([]);
  const [trainPlaneForm, setTrainPlaneForm] = useState({
    base_url: "http://127.0.0.1:8818",
    token: "",
    region: "us-east-1",
    instance_id: "",
    bucket: "",
    ssm_enabled: true,
    default_training_profile: '{\n  "execution_mode": "qlora",\n  "max_steps": 12\n}',
    default_serving_profile: '{\n  "engine": "vllm",\n  "mode": "adapter-first"\n}'
  });
  const [remoteBaseModelForm, setRemoteBaseModelForm] = useState({
    name: "Meta-Llama-3.1-8B-Instruct",
    source_kind: "huggingface_ref",
    source_ref: "meta-llama/Meta-Llama-3.1-8B-Instruct",
    local_path: "",
    format: "huggingface"
  });
  const [remoteDatasetForm, setRemoteDatasetForm] = useState({
    project_slug: "orquestra-lab",
    name: "approved-memory-bundle",
    approved_only: true,
    max_records: 120
  });
  const [remoteRunForm, setRemoteRunForm] = useState({
    name: "research-adapter-run",
    summary: "Fine-tuning remoto adapter-first a partir de memória aprovada e sinais de treino.",
    base_model_id: "",
    dataset_bundle_id: ""
  });
  const [remoteReviewForm, setRemoteReviewForm] = useState({
    candidate_artifact_id: "",
    baseline_mode: "lmstudio_local",
    baseline_provider_id: "lmstudio",
    baseline_model_name: "",
    prompt_blob: "Resuma as memórias mais relevantes para continuidade do projeto.\nCompare a eficácia do modelo treinado para responder com contexto operacional."
  });

  const [runtimeSettings, setRuntimeSettings] = useState<RuntimeSettingsReport | null>(null);
  const [storageLocations, setStorageLocations] = useState<StorageLocation[]>([]);
  const [storageAssignments, setStorageAssignments] = useState<StorageAssignment[]>([]);
  const [secretMetadata, setSecretMetadata] = useState<SecretMetadata[]>([]);
  const [routePolicies, setRoutePolicies] = useState<Array<{ id: string; label: string; mode: string; task_type: string; preferred_provider_id: string; preferred_model_name: string }>>([]);
  const [agentProfiles, setAgentProfiles] = useState<AgentProfile[]>([]);
  const [storageLocationForm, setStorageLocationForm] = useState({
    label: "SSD externo Orquestra",
    backend: "external_drive",
    base_uri: "/Volumes/SSDExterno/Orquestra/runtime",
    quota_bytes: ""
  });
  const [secretForm, setSecretForm] = useState({ provider_id: "openai", label: "OpenAI API Key", secret_ref: "openai.api_key", value: "" });
  const [routerSimulation, setRouterSimulation] = useState<Record<string, unknown> | null>(null);

  const [selectedRunId, setSelectedRunId] = useState("");
  const [selectedRun, setSelectedRun] = useState<OpsRun | null>(null);
  const [workflowRuns, setWorkflowRuns] = useState<WorkflowRun[]>([]);
  const [selectedWorkflowId, setSelectedWorkflowId] = useState("");
  const [selectedWorkflow, setSelectedWorkflow] = useState<WorkflowRun | null>(null);
  const [taskRelationDrafts, setTaskRelationDrafts] = useState<Record<string, { blockedBy: string; blocks: string }>>({});
  const [opsActionBusyId, setOpsActionBusyId] = useState("");
  const [statusLine, setStatusLine] = useState("Orquestra pronto para operar em modo local-first.");

  const providers = opsDashboard?.execution_snapshot.providers ?? [];
  const connectors = opsDashboard?.execution_snapshot.connectors ?? [];
  const trainingJobs = opsDashboard?.execution_snapshot.training_jobs ?? [];
  const remoteJobs = opsDashboard?.execution_snapshot.remote_jobs ?? [];
  const registryModels = opsDashboard?.execution_snapshot.registry_models ?? [];
  const opsActions = opsDashboard?.execution_snapshot.actions ?? [];
  const opsRuns = opsDashboard?.execution_snapshot.runs ?? [];
  const selectedProject = projects.find((project) => project.id === selectedProjectId) ?? null;
  const selectedAsset = workspaceAssets.find((asset) => asset.id === selectedAssetId) ?? null;
  const currentView = views.find((item) => item.id === view)!;
  const sessionTaskMap = useMemo(() => new Map(sessionTasks.map((task) => [task.id, task])), [sessionTasks]);

  const servicesByCategory = useMemo(() => {
    const groups = new Map<string, Array<OpsDashboard["services"][number]>>();
    for (const service of opsDashboard?.services ?? []) {
      const bucket = groups.get(service.category) ?? [];
      bucket.push(service);
      groups.set(service.category, bucket);
    }
    return [...groups.entries()];
  }, [opsDashboard]);

  async function refreshGlobal(preferredProjectId?: string) {
    const [healthPayload, dashboardPayload, runtimePayload, locationsPayload, assignmentsPayload, secretsPayload, policiesPayload, agentsPayload] = await Promise.all([
      getHealth(),
      getOpsDashboard(),
      getRuntimeSettings(),
      listStorageLocations(),
      listStorageAssignments(),
      listSecrets(),
      listModelRoutePolicies(),
      listAgents()
    ]);
    setHealth(healthPayload);
    setOpsDashboard(dashboardPayload);
    setRuntimeSettings(runtimePayload);
    setStorageLocations(locationsPayload);
    setStorageAssignments(assignmentsPayload.assignments);
    setSecretMetadata(secretsPayload);
    setRoutePolicies(policiesPayload);
    setAgentProfiles(agentsPayload);
    setWorkflowRuns(dashboardPayload.execution_snapshot.workflow_runs ?? []);

    const projectsPayload = dashboardPayload.execution_snapshot.projects;
    setProjects(projectsPayload);

    const nextProjectId = preferredProjectId || selectedProjectId || projectsPayload[0]?.id || "";
    setSelectedProjectId(nextProjectId);

    const nextProject = projectsPayload.find((item) => item.id === nextProjectId) ?? projectsPayload[0] ?? null;
    const nextProviderId = nextProject?.default_provider_id ?? dashboardPayload.execution_snapshot.providers[0]?.provider_id ?? "lmstudio";
    setSelectedProviderId(nextProviderId);

    if (!selectedRunId && dashboardPayload.execution_snapshot.runs[0]?.run_id) {
      setSelectedRunId(dashboardPayload.execution_snapshot.runs[0].run_id);
    }
    if (!selectedWorkflowId && dashboardPayload.execution_snapshot.workflow_runs[0]?.id) {
      setSelectedWorkflowId(dashboardPayload.execution_snapshot.workflow_runs[0].id);
    }
  }

  async function refreshProjectScoped(projectId: string) {
    if (!projectId) {
      setSessions([]);
      setMemoryRecords([]);
      setMemoryTopics([]);
      setTrainingCandidates([]);
      setMemoryCandidates([]);
      setWorkspaceScans([]);
      setSelectedSessionId("");
      setSelectedScanId("");
      return;
    }

    const [sessionPayload, memoryPayload, topicsPayload, trainingPayload, reviewPayload, scanPayload] = await Promise.all([
      listSessions(projectId),
      listMemory(projectId),
      listMemoryTopics(projectId),
      listTrainingCandidates(projectId),
      listMemoryCandidates(projectId, undefined, "pending"),
      listWorkspaceScans(projectId)
    ]);
    setSessions(sessionPayload);
    setMemoryRecords(memoryPayload);
    setMemoryTopics(topicsPayload);
    setTrainingCandidates(trainingPayload);
    setMemoryCandidates(reviewPayload);
    setWorkspaceScans(scanPayload);

    const nextSessionId = sessionPayload.find((item) => item.id === selectedSessionId)?.id ?? sessionPayload[0]?.id ?? "";
    const nextScanId = scanPayload.find((item) => item.id === selectedScanId)?.id ?? scanPayload[0]?.id ?? "";
    setSelectedSessionId(nextSessionId);
    setSelectedScanId(nextScanId);
  }

  async function refreshOsint(projectId?: string, preferredInvestigationId?: string) {
    const [configPayload, connectorsPayload, registryPayload, investigationsPayload] = await Promise.all([
      getOsintConfig(),
      listOsintConnectors(projectId || undefined),
      listOsintSourceRegistry(),
      listOsintInvestigations(projectId || undefined)
    ]);
    setOsintConfig(configPayload);
    setOsintConnectors(connectorsPayload);
    setOsintRegistry(registryPayload);
    setOsintInvestigations(investigationsPayload);
    const nextInvestigationId =
      preferredInvestigationId ||
      investigationsPayload.find((item) => item.id === selectedInvestigationId)?.id ||
      investigationsPayload.find((item) => (selectedSessionId ? item.session_id === selectedSessionId : false))?.id ||
      investigationsPayload[0]?.id ||
      "";
    setSelectedInvestigationId(nextInvestigationId);
  }

  async function refreshOsintInvestigation(investigationId: string) {
    if (!investigationId) {
      setSelectedInvestigation(null);
      setOsintRuns([]);
      setOsintSources([]);
      setOsintEvidence([]);
      setOsintClaims([]);
      setOsintPlanQueries([]);
      return;
    }
    const [investigationPayload, runsPayload, evidencePayload, claimsPayload] = await Promise.all([
      getOsintInvestigation(investigationId),
      listOsintRuns(investigationId),
      listOsintEvidence(investigationId),
      listOsintClaims(investigationId)
    ]);
    setSelectedInvestigation(investigationPayload);
    setOsintRuns(runsPayload);
    setOsintEvidence(evidencePayload);
    setOsintClaims(claimsPayload);
  }

  async function refreshProviderModels(providerId: string, preferredModel?: string) {
    if (!providerId) return;
    const payload = await listModels(providerId);
    setModels(payload.models);
    setSelectedModel(preferredModel || payload.models[0] || "");
  }

  async function refreshSession(sessionId: string) {
    if (!sessionId) {
      setMessages([]);
      setSessionSummary(null);
      setSessionTranscript(null);
      setSessionCompaction(null);
      setPlannerSnapshot(null);
      setSessionTasks([]);
      setTaskRelationDrafts({});
      setResumePayload(null);
      setSessionProfile(null);
      setMemoryCandidates([]);
      return;
    }
    const [messagesPayload, summaryPayload, transcriptPayload, profilePayload, candidatePayload, plannerPayload] = await Promise.all([
      listMessages(sessionId),
      getSummary(sessionId),
      getTranscript(sessionId),
      getSessionProfile(sessionId),
      listMemoryCandidates(undefined, sessionId, "pending"),
      getPlanner(sessionId)
    ]);
    setMessages(messagesPayload);
    setSessionSummary(summaryPayload);
    setSessionCompaction(summaryPayload.compaction_state ?? null);
    setSessionTranscript(transcriptPayload);
    setSessionProfile(profilePayload);
    setMemoryCandidates(candidatePayload);
    setPlannerSnapshot(plannerPayload.snapshot);
    setSessionTasks(plannerPayload.tasks);
    setTaskRelationDrafts({});
  }

  async function refreshWorkspace(scanId: string) {
    if (!scanId) {
      setSelectedScan(null);
      setWorkspaceAssets([]);
      setSelectedAssetId("");
      setAssetPreview(null);
      return;
    }
    const [scanPayload, assetsPayload] = await Promise.all([getWorkspaceScan(scanId), listWorkspaceAssets(scanId)]);
    setSelectedScan(scanPayload);
    setWorkspaceAssets(assetsPayload);
    const nextAssetId = assetsPayload.find((item) => item.id === selectedAssetId)?.id ?? assetsPayload[0]?.id ?? "";
    setSelectedAssetId(nextAssetId);
  }

  async function refreshRun(runId: string) {
    if (!runId) {
      setSelectedRun(null);
      return;
    }
    const payload = await getOpsRun(runId);
    setSelectedRun(payload);
  }

  async function refreshWorkflow(runId: string) {
    if (!runId) {
      setSelectedWorkflow(null);
      return;
    }
    const payload = await getWorkflowRun(runId);
    setSelectedWorkflow(payload);
  }

  async function refreshRemoteTrainPlane(syncForm = false) {
    const configPayload = await getRemoteTrainPlaneConfig();
    setRemoteTrainPlaneConfig(configPayload);
    if (syncForm || !remoteTrainPlaneConfig) {
      setTrainPlaneForm((current) => ({
        ...current,
        base_url: configPayload.base_url || current.base_url,
        region: configPayload.region || current.region,
        instance_id: configPayload.instance_id || "",
        bucket: configPayload.bucket || "",
        ssm_enabled: configPayload.ssm_enabled,
        default_training_profile: JSON.stringify(configPayload.default_training_profile ?? {}, null, 2),
        default_serving_profile: JSON.stringify(configPayload.default_serving_profile ?? {}, null, 2)
      }));
    }

    if (!configPayload.base_url || !configPayload.token_configured) {
      setRemoteBaseModels([]);
      setRemoteDatasetBundles([]);
      setRemoteTrainRuns([]);
      setRemoteArtifacts([]);
      setRemoteEvaluations([]);
      setRemoteComparisons([]);
      setSelectedRemoteTrainRunId("");
      setSelectedRemoteTrainRun(null);
      return;
    }

    const [baseModelsPayload, datasetBundlesPayload, runsPayload, artifactsPayload, evaluationsPayload, comparisonsPayload] = await Promise.all([
      listRemoteTrainPlaneBaseModels(),
      listRemoteTrainPlaneDatasetBundles(),
      listRemoteTrainPlaneRuns(selectedProjectId || undefined),
      listRemoteTrainPlaneArtifacts(selectedProjectId || undefined),
      listRemoteTrainPlaneEvaluations(),
      listRemoteTrainPlaneComparisons()
    ]);

    setRemoteBaseModels(baseModelsPayload);
    setRemoteDatasetBundles(datasetBundlesPayload);
    setRemoteTrainRuns(runsPayload);
    setRemoteArtifacts(artifactsPayload);
    setRemoteEvaluations(evaluationsPayload);
    setRemoteComparisons(comparisonsPayload);
    setRemoteRunForm((current) => ({
      ...current,
      base_model_id: current.base_model_id || baseModelsPayload[0]?.id || "",
      dataset_bundle_id: current.dataset_bundle_id || datasetBundlesPayload[0]?.id || ""
    }));

    const nextRunId = runsPayload.find((item) => item.id === selectedRemoteTrainRunId)?.id ?? runsPayload[0]?.id ?? "";
    setSelectedRemoteTrainRunId(nextRunId);
    if (!remoteReviewForm.candidate_artifact_id && artifactsPayload[0]?.id) {
      setRemoteReviewForm((current) => ({ ...current, candidate_artifact_id: artifactsPayload[0].id }));
    }
  }

  async function refreshRemoteTrainPlaneRun(runId: string) {
    if (!runId) {
      setSelectedRemoteTrainRun(null);
      return;
    }
    const payload = await getRemoteTrainPlaneRun(runId, selectedProjectId || undefined);
    setSelectedRemoteTrainRun(payload);
    if (payload.artifact?.id) {
      setRemoteReviewForm((current) => ({
        ...current,
        candidate_artifact_id: current.candidate_artifact_id || payload.artifact?.id || ""
      }));
    }
  }

  useEffect(() => {
    refreshGlobal()
      .then(() => setStatusLine("Bootstrap do dashboard operacional concluído."))
      .catch((error) => setStatusLine(`Falha no bootstrap: ${String(error)}`));
  }, []);

  useEffect(() => {
    refreshRemoteTrainPlane(true).catch((error) => setStatusLine(`Falha ao carregar Train Plane remoto: ${String(error)}`));
  }, []);

  useEffect(() => {
    if (!selectedProjectId) return;
    refreshProjectScoped(selectedProjectId).catch((error) => setStatusLine(`Falha ao carregar dados do projeto: ${String(error)}`));
  }, [selectedProjectId]);

  useEffect(() => {
    refreshOsint(selectedProjectId || undefined).catch((error) => setStatusLine(`Falha ao carregar OSINT Lab: ${String(error)}`));
  }, [selectedProjectId]);

  useEffect(() => {
    if (!selectedProviderId) return;
    const preferredModel = projects.find((item) => item.id === selectedProjectId)?.default_model;
    refreshProviderModels(selectedProviderId, preferredModel).catch((error) => setStatusLine(`Falha ao listar modelos: ${String(error)}`));
  }, [selectedProviderId, selectedProjectId, projects]);

  useEffect(() => {
    if (!selectedSessionId) return;
    refreshSession(selectedSessionId).catch((error) => setStatusLine(`Falha ao carregar sessão: ${String(error)}`));
  }, [selectedSessionId]);

  useEffect(() => {
    if (!selectedSessionId) return;
    listOsintInvestigations(undefined, selectedSessionId)
      .then((items) => {
        const sessionInvestigation = items[0];
        if (sessionInvestigation) {
          setSelectedInvestigationId((current) => current || sessionInvestigation.id);
        }
      })
      .catch(() => undefined);
  }, [selectedSessionId]);

  useEffect(() => {
    if (!selectedInvestigationId) {
      refreshOsintInvestigation("").catch(() => undefined);
      return;
    }
    refreshOsintInvestigation(selectedInvestigationId).catch((error) => setStatusLine(`Falha ao carregar investigação OSINT: ${String(error)}`));
  }, [selectedInvestigationId]);

  useEffect(() => {
    if (!selectedScanId) return;
    refreshWorkspace(selectedScanId).catch((error) => setStatusLine(`Falha ao carregar workspace: ${String(error)}`));
  }, [selectedScanId]);

  useEffect(() => {
    if (!selectedAssetId) {
      setAssetPreview(null);
      return;
    }
    previewWorkspaceAsset(selectedAssetId)
      .then(setAssetPreview)
      .catch(() => setAssetPreview(null));
  }, [selectedAssetId]);

  useEffect(() => {
    if (!selectedRunId) {
      setSelectedRun(null);
      return;
    }
    refreshRun(selectedRunId).catch((error) => setStatusLine(`Falha ao carregar execução: ${String(error)}`));

    const interval = window.setInterval(() => {
      refreshRun(selectedRunId).catch(() => undefined);
    }, 4000);
    return () => window.clearInterval(interval);
  }, [selectedRunId]);

  useEffect(() => {
    if (!selectedWorkflowId) {
      setSelectedWorkflow(null);
      return;
    }
    refreshWorkflow(selectedWorkflowId).catch((error) => setStatusLine(`Falha ao carregar workflow: ${String(error)}`));

    const interval = window.setInterval(() => {
      refreshWorkflow(selectedWorkflowId).catch(() => undefined);
    }, 3000);
    return () => window.clearInterval(interval);
  }, [selectedWorkflowId]);

  useEffect(() => {
    const shouldPoll = view === "dashboard" || view === "process" || view === "execution";
    if (!shouldPoll) return;
    const interval = window.setInterval(() => {
      refreshGlobal(selectedProjectId).catch(() => undefined);
    }, 12000);
    return () => window.clearInterval(interval);
  }, [view, selectedProjectId]);

  useEffect(() => {
    if (view !== "dashboard" && view !== "execution") return;
    const interval = window.setInterval(() => {
      refreshRemoteTrainPlane().catch(() => undefined);
    }, 15000);
    return () => window.clearInterval(interval);
  }, [view, selectedProjectId]);

  useEffect(() => {
    if (!selectedRemoteTrainRunId) {
      setSelectedRemoteTrainRun(null);
      return;
    }
    refreshRemoteTrainPlaneRun(selectedRemoteTrainRunId).catch((error) => setStatusLine(`Falha ao carregar run remoto: ${String(error)}`));
    const interval = window.setInterval(() => {
      refreshRemoteTrainPlaneRun(selectedRemoteTrainRunId).catch(() => undefined);
    }, 3500);
    return () => window.clearInterval(interval);
  }, [selectedRemoteTrainRunId, selectedProjectId]);

  function openSessionSetup() {
    setSessionSetup(defaultSessionProfile("research"));
    setShowSessionSetup(true);
    setView("assistant");
  }

  function updateDraftProfile(updater: (current: SessionProfile) => SessionProfile) {
    setSessionProfile((current) => (current ? updater(current) : current));
  }

  async function handleCreateSessionWithProfile() {
    if (!sessionSetup.objective.trim()) {
      setStatusLine("Defina um objetivo antes de iniciar a sessão.");
      return;
    }
    try {
      const session = await createSession({
        project_id: selectedProjectId || undefined,
        title: sessionSetup.objective.trim().slice(0, 72),
        provider_id: selectedProviderId,
        model_name: selectedModel,
        objective: sessionSetup.objective,
        preset: sessionSetup.preset,
        memory_policy: sessionSetup.memory_policy,
        rag_policy: sessionSetup.rag_policy,
        persona_config: sessionSetup.persona_config
      });
      setSelectedSessionId(session.id);
      setSessionProfile(session.profile ?? sessionSetup);
      setShowSessionSetup(false);
      setStatusLine(`Sessão criada com preset ${session.profile?.preset_label || sessionSetup.preset}.`);
      await refreshProjectScoped(selectedProjectId);
      await refreshSession(session.id);
    } catch (error) {
      setStatusLine(`Falha ao criar sessão com perfil: ${String(error)}`);
    }
  }

  async function handleSaveSessionProfile() {
    if (!selectedSessionId || !sessionProfile) return;
    try {
      setProfileSaving(true);
      const payload = await updateSessionProfile(selectedSessionId, sessionProfile);
      setSessionProfile(payload);
      setStatusLine("Perfil de sessão salvo.");
      await refreshProjectScoped(selectedProjectId);
    } catch (error) {
      setStatusLine(`Falha ao salvar perfil da sessão: ${String(error)}`);
    } finally {
      setProfileSaving(false);
    }
  }

  async function handleReviewMemoryCandidate(candidate: MemoryReviewCandidate, action: "approve" | "reject") {
    try {
      if (action === "approve") {
        await approveMemoryCandidate(candidate.id, {
          create_training_candidate: Boolean(sessionProfile?.memory_policy.generate_training_candidates),
          metadata: { reviewed_from: "assistant_memory_panel" }
        });
        setStatusLine("Candidato aprovado, memória criada e indexação RAG solicitada.");
      } else {
        await rejectMemoryCandidate(candidate.id, { metadata: { reviewed_from: "assistant_memory_panel" } });
        setStatusLine("Candidato rejeitado.");
      }
      if (selectedSessionId) {
        await refreshSession(selectedSessionId);
      }
      await refreshProjectScoped(selectedProjectId);
      await refreshGlobal(selectedProjectId);
    } catch (error) {
      setStatusLine(`Falha ao revisar candidato: ${String(error)}`);
    }
  }

  async function handleSendChat() {
    if (!chatPrompt.trim() || chatStreaming) return;
    const prompt = chatPrompt.trim();
    setChatPrompt("");
    setChatStreaming(true);
    setStatusLine("Streaming do Assistant Workspace em andamento.");
    let activeSessionId = selectedSessionId;
    const memoryPolicy = sessionProfile?.memory_policy ?? defaultSessionProfile("assistant").memory_policy;
    const ragPolicy = sessionProfile?.rag_policy ?? defaultSessionProfile("assistant").rag_policy;

    const optimisticUser: ChatMessage = {
      id: `local-user-${Date.now()}`,
      role: "user",
      content: prompt,
      usage: {},
      created_at: new Date().toISOString()
    };
    const optimisticAssistant: ChatMessage = {
      id: `local-assistant-${Date.now()}`,
      role: "assistant",
      content: "",
      provider_id: selectedProviderId,
      model_name: selectedModel,
      usage: {},
      created_at: new Date().toISOString()
    };
    setMessages((current) => [...current, optimisticUser, optimisticAssistant]);

    try {
      await streamChat(
        {
          project_id: selectedProjectId || undefined,
          session_id: selectedSessionId || undefined,
          provider_id: selectedProviderId || undefined,
          model_name: selectedModel || undefined,
          message: prompt,
          remember: true,
          mock_response: chatMockMode,
          memory_enabled: Boolean(memoryPolicy.enabled),
          memory_scopes: memoryPolicy.scopes ?? [],
          include_workspace: Boolean(ragPolicy.include_workspace),
          include_sources: Boolean(ragPolicy.include_sources),
          max_context_chars: Number(ragPolicy.max_context_chars ?? 9000),
          compaction_enabled: true,
          planner_enabled: true,
          task_context_enabled: true,
          memory_selector_mode: "hybrid",
          context_budget: Number(ragPolicy.max_context_chars ?? 9000),
          investigation_id: selectedInvestigationId || undefined,
          osint_mode: sessionProfile?.preset === "osint",
          fresh_web_enabled: false,
          evidence_enabled: sessionProfile?.preset === "osint",
          source_registry_ids: selectedInvestigation?.source_registry_ids ?? [],
          enabled_connector_ids: selectedInvestigation?.enabled_connector_ids ?? [],
          via_tor: false
        },
        {
          onSession: ({ session_id }) => {
            activeSessionId = session_id;
            setSelectedSessionId(session_id);
          },
          onDelta: (text) => {
            setMessages((current) =>
              current.map((message, index) =>
                index === current.length - 1 && message.role === "assistant"
                  ? { ...message, content: `${message.content}${message.content ? " " : ""}${text}` }
                  : message
              )
            );
          },
          onSummary: (payload) => {
            setSessionSummary((current) =>
              current
                ? { ...current, current_state: payload.current_state, next_steps: payload.next_steps ?? current.next_steps, updated_at: payload.updated_at }
                : {
                    session_id: selectedSessionId,
                    current_state: payload.current_state,
                    next_steps: payload.next_steps ?? "",
                    relevant_files: [],
                    commands_run: [],
                    errors_and_fixes: [],
                    worklog: [],
                    compacted_from_message_count: 0,
                    storage_path: "",
                    metadata: {},
                    updated_at: payload.updated_at
                  }
            );
          },
          onDone: ({ provider_id, model_name, usage, latency_seconds, memory_candidates_created, memory_recall_count, osint_evidence_count }) => {
            setMessages((current) =>
              current.map((message, index) =>
                index === current.length - 1 && message.role === "assistant"
                  ? { ...message, provider_id, model_name, usage, latency_seconds }
                  : message
              )
            );
            setLastMemoryTelemetry({ recallCount: memory_recall_count ?? 0, candidatesCreated: memory_candidates_created ?? 0 });
            setStatusLine(
              `Resposta concluída via ${provider_id}/${model_name} em ${latency_seconds.toFixed(2)}s; memória recall ${memory_recall_count ?? 0}, evidência OSINT ${osint_evidence_count ?? 0}, inbox +${memory_candidates_created ?? 0}.`
            );
          }
        }
      );
      await refreshProjectScoped(selectedProjectId);
      await refreshGlobal(selectedProjectId);
      if (activeSessionId) {
        await refreshSession(activeSessionId);
      }
    } catch (error) {
      setStatusLine(`Falha no streaming: ${String(error)}`);
    } finally {
      setChatStreaming(false);
    }
  }

  async function handleResumeSession() {
    if (!selectedSessionId) return;
    try {
      const payload = await resumeSession(selectedSessionId);
      setResumePayload(payload);
      setStatusLine("Payload de retomada atualizado.");
      await refreshSession(selectedSessionId);
    } catch (error) {
      setStatusLine(`Falha ao retomar sessão: ${String(error)}`);
    }
  }

  async function handleCompactSession() {
    if (!selectedSessionId) return;
    try {
      const payload = await compactSession(selectedSessionId);
      setSessionCompaction(payload.compaction_state);
      setStatusLine(`Compactação atualizada: ${payload.compacted_from_message_count} mensagens consolidadas.`);
      await refreshSession(selectedSessionId);
    } catch (error) {
      setStatusLine(`Falha ao compactar sessão: ${String(error)}`);
    }
  }

  async function handleRebuildPlanner() {
    if (!selectedSessionId) return;
    try {
      const payload = await rebuildPlanner(selectedSessionId);
      setPlannerSnapshot(payload.snapshot);
      setSessionTasks(payload.tasks);
      setStatusLine(`Planner reconstruído com ${payload.tasks.length} tarefas.`);
      await refreshSession(selectedSessionId);
    } catch (error) {
      setStatusLine(`Falha ao reconstruir planner: ${String(error)}`);
    }
  }

  async function handleTaskStatus(task: SessionTask, status: SessionTask["status"]) {
    if (!selectedSessionId) return;
    try {
      const updated = await patchSessionTask(selectedSessionId, task.id, { status, metadata: { updated_from: "assistant_panel" } });
      setSessionTasks((current) => current.map((item) => (item.id === updated.id ? updated : item)));
      setStatusLine(`Tarefa ${updated.subject} marcada como ${status}.`);
    } catch (error) {
      setStatusLine(`Falha ao atualizar tarefa: ${String(error)}`);
    }
  }

  function handleTaskRelationDraft(taskId: string, relation: "blockedBy" | "blocks", value: string) {
    setTaskRelationDrafts((current) => ({
      ...current,
      [taskId]: {
        blockedBy: current[taskId]?.blockedBy ?? "",
        blocks: current[taskId]?.blocks ?? "",
        [relation]: value
      }
    }));
  }

  async function handleTaskRelation(task: SessionTask, relation: "blocked_by" | "blocks") {
    if (!selectedSessionId) return;
    const draft = taskRelationDrafts[task.id];
    const relatedTaskId = relation === "blocked_by" ? draft?.blockedBy : draft?.blocks;
    if (!relatedTaskId || relatedTaskId === task.id) return;
    const relatedTask = sessionTasks.find((item) => item.id === relatedTaskId);
    if (!relatedTask) return;

    try {
      const nextPrimary = relation === "blocked_by"
        ? await patchSessionTask(selectedSessionId, task.id, {
            blocked_by: Array.from(new Set([...(task.blocked_by ?? []), relatedTaskId])),
            metadata: { updated_from: "assistant_planner_relations" }
          })
        : await patchSessionTask(selectedSessionId, task.id, {
            blocks: Array.from(new Set([...(task.blocks ?? []), relatedTaskId])),
            metadata: { updated_from: "assistant_planner_relations" }
          });

      const nextSecondary = relation === "blocked_by"
        ? await patchSessionTask(selectedSessionId, relatedTask.id, {
            blocks: Array.from(new Set([...(relatedTask.blocks ?? []), task.id])),
            metadata: { updated_from: "assistant_planner_relations" }
          })
        : await patchSessionTask(selectedSessionId, relatedTask.id, {
            blocked_by: Array.from(new Set([...(relatedTask.blocked_by ?? []), task.id])),
            metadata: { updated_from: "assistant_planner_relations" }
          });

      setSessionTasks((current) =>
        current.map((item) => {
          if (item.id === nextPrimary.id) return nextPrimary;
          if (item.id === nextSecondary.id) return nextSecondary;
          return item;
        })
      );
      setTaskRelationDrafts((current) => ({
        ...current,
        [task.id]: { blockedBy: "", blocks: "" }
      }));
      setStatusLine(`Dependência registrada entre ${task.subject} e ${relatedTask.subject}.`);
    } catch (error) {
      setStatusLine(`Falha ao registrar dependência: ${String(error)}`);
    }
  }

  async function handleAddNextTask() {
    if (!selectedSessionId || !chatPrompt.trim()) return;
    try {
      const task = await createSessionTask(selectedSessionId, {
        subject: chatPrompt.trim().slice(0, 140),
        description: chatPrompt.trim(),
        status: "pending",
        metadata: { created_from: "assistant_prompt" }
      });
      setSessionTasks((current) => [...current, task].sort((a, b) => a.position - b.position));
      setStatusLine("Tarefa adicionada ao planner.");
    } catch (error) {
      setStatusLine(`Falha ao criar tarefa: ${String(error)}`);
    }
  }

  async function handleStartValidationWorkflow() {
    if (!selectedSessionId) return;
    try {
      const payload = await createWorkflowRun({
        session_id: selectedSessionId,
        workflow_name: "session-validation",
        summary: "Executar validação local controlada da stack Orquestra.",
        steps: [
          { step_type: "shell_safe", label: "Git diff check", payload: { command: "git diff --check" } },
          { step_type: "ops_action", label: "Validate stack", payload: { action_id: "validate" } }
        ]
      });
      setSelectedWorkflowId(payload.id);
      setSelectedWorkflow(payload);
      setStatusLine("Workflow local iniciado.");
      await refreshGlobal(selectedProjectId);
    } catch (error) {
      setStatusLine(`Falha ao iniciar workflow: ${String(error)}`);
    }
  }

  async function handleStartTaskWorkflow(task: SessionTask) {
    if (!selectedSessionId) return;
    try {
      const payload = await createWorkflowRun({
        session_id: selectedSessionId,
        task_id: task.id,
        workflow_name: "task-linked-validation",
        summary: `Executar workflow local vinculado à tarefa: ${task.subject}`,
        steps: [
          { step_type: "shell_safe", label: "Git diff check", payload: { command: "git diff --check" } },
          {
            step_type: "rag_query",
            label: "Task context",
            payload: {
              question: `Qual é o próximo passo operacional para a tarefa: ${task.subject}?`,
              session_id: selectedSessionId,
              mock_llm: true,
              memory_enabled: true,
              planner_enabled: true,
              task_context_enabled: true
            }
          }
        ]
      });
      setSelectedWorkflowId(payload.id);
      setSelectedWorkflow(payload);
      setStatusLine(`Workflow iniciado para a tarefa ${task.subject}.`);
      await refreshGlobal(selectedProjectId);
    } catch (error) {
      setStatusLine(`Falha ao iniciar workflow da tarefa: ${String(error)}`);
    }
  }

  async function handleCancelWorkflow() {
    if (!selectedWorkflowId) return;
    try {
      const payload = await cancelWorkflowRun(selectedWorkflowId);
      setSelectedWorkflow(payload);
      setStatusLine("Cancelamento solicitado para o workflow.");
    } catch (error) {
      setStatusLine(`Falha ao cancelar workflow: ${String(error)}`);
    }
  }

  async function handleAttachDirectory() {
    if (!workspaceRootPath.trim()) return;
    try {
      const scan = await attachDirectory({
        project_id: selectedProjectId || undefined,
        root_path: workspaceRootPath.trim(),
        prompt_hint: workspacePromptHint
      });
      setSelectedScanId(scan.id);
      setWorkspaceResult(null);
      setStatusLine(`Diretório anexado: ${scan.root_path}`);
      await refreshProjectScoped(selectedProjectId);
      await refreshGlobal(selectedProjectId);
    } catch (error) {
      setStatusLine(`Falha ao anexar diretório: ${String(error)}`);
    }
  }

  async function handleWorkspaceQuery() {
    if (!selectedScanId || !workspacePrompt.trim()) return;
    try {
      const result = await queryWorkspace({
        scan_id: selectedScanId,
        prompt: workspacePrompt,
        provider_id: selectedProviderId || undefined,
        model_name: selectedModel || undefined,
        mock_response: workspaceMockMode
      });
      setWorkspaceResult(result);
      setStatusLine(`Workspace respondeu usando ${result.provider_id}/${result.model_name}.`);
      await refreshWorkspace(selectedScanId);
      await refreshGlobal(selectedProjectId);
    } catch (error) {
      setStatusLine(`Falha na consulta multimodal: ${String(error)}`);
    }
  }

  async function handleExtractAsset() {
    if (!selectedAssetId) return;
    try {
      const payload = await extractWorkspaceAsset(selectedAssetId, { prompt_hint: workspacePromptHint, force: true });
      setAssetPreview(payload);
      setStatusLine("Derivados do asset atualizados.");
      await refreshWorkspace(selectedScanId);
      await refreshGlobal(selectedProjectId);
    } catch (error) {
      setStatusLine(`Falha ao extrair asset: ${String(error)}`);
    }
  }

  async function handleOpenAsset() {
    if (!selectedAssetId) return;
    try {
      const payload = await openWorkspaceAsset(selectedAssetId);
      setStatusLine(`Abrindo asset via ${payload.strategy}: ${payload.absolute_path}`);
      window.open(rawPreviewUrl(selectedAssetId), "_blank", "noopener,noreferrer");
    } catch (error) {
      setStatusLine(`Falha ao abrir asset: ${String(error)}`);
    }
  }

  async function handleMemorizeAsset() {
    if (!selectedAssetId) return;
    try {
      await memorizeWorkspaceAsset(selectedAssetId, { project_id: selectedProjectId || undefined });
      setStatusLine("Asset promovido para memória.");
      await refreshProjectScoped(selectedProjectId);
      await refreshGlobal(selectedProjectId);
    } catch (error) {
      setStatusLine(`Falha ao memorizar asset: ${String(error)}`);
    }
  }

  async function handleRecallMemory() {
    try {
      const payload = await recallMemory({
        query: memoryRecallQuery,
        project_id: selectedProjectId || undefined,
        limit: 8
      });
      setMemoryRecallResults(payload);
      setStatusLine("Recall de memória executado.");
    } catch (error) {
      setStatusLine(`Falha no recall de memória: ${String(error)}`);
    }
  }

  async function handlePromoteMemory() {
    try {
      await promoteMemory({
        project_id: selectedProjectId || undefined,
        scope: "project_memory",
        title: promoteTitle,
        content: promoteContent,
        source: "memory_studio"
      });
      setStatusLine("Memória promovida para tópico durável.");
      await refreshProjectScoped(selectedProjectId);
      await refreshGlobal(selectedProjectId);
    } catch (error) {
      setStatusLine(`Falha ao promover memória: ${String(error)}`);
    }
  }

  async function handleCreateManualMemory() {
    try {
      await createMemory({
        project_id: selectedProjectId || undefined,
        session_id: selectedSessionId || undefined,
        scope: "semantic_memory",
        source: "memory_studio",
        content: promoteContent,
        confidence: 0.82,
        approved_for_training: false
      });
      setStatusLine("Memória manual registrada.");
      await refreshProjectScoped(selectedProjectId);
      await refreshGlobal(selectedProjectId);
    } catch (error) {
      setStatusLine(`Falha ao criar memória: ${String(error)}`);
    }
  }

  async function handleRagQuery() {
    setRagLoading(true);
    try {
      const result = await queryRag({
        question: ragPrompt,
        project_id: selectedProjectId || undefined,
        session_id: selectedSessionId || undefined,
        collection_name: "knowledge_base",
        provider_id: selectedProviderId || undefined,
        model_name: selectedModel || undefined,
        task_type: "orquestra_execution",
        remember: true,
        mock_llm: chatMockMode,
        memory_enabled: Boolean(sessionProfile?.memory_policy.enabled ?? true),
        memory_scopes: sessionProfile?.memory_policy.scopes ?? [],
        include_workspace: Boolean(sessionProfile?.rag_policy.include_workspace ?? true),
        include_sources: Boolean(sessionProfile?.rag_policy.include_sources ?? true),
        max_context_chars: Number(sessionProfile?.rag_policy.max_context_chars ?? 9000),
        compaction_enabled: true,
        planner_enabled: true,
        task_context_enabled: true,
        memory_selector_mode: "hybrid",
        context_budget: Number(sessionProfile?.rag_policy.max_context_chars ?? 9000),
        include_osint_evidence: Boolean(selectedInvestigationId || sessionProfile?.preset === "osint"),
        investigation_id: selectedInvestigationId || undefined,
        evidence_budget: 4,
        fresh_web_enabled: false,
        source_registry_ids: selectedInvestigation?.source_registry_ids ?? [],
        enabled_connector_ids: selectedInvestigation?.enabled_connector_ids ?? [],
        via_tor: false
      });
      setRagResult(result);
      setStatusLine("Consulta do RAG concluída.");
      await refreshProjectScoped(selectedProjectId);
      await refreshGlobal(selectedProjectId);
    } catch (error) {
      setStatusLine(`Falha no RAG Studio: ${String(error)}`);
    } finally {
      setRagLoading(false);
    }
  }

  async function handleSaveOsintConfig() {
    if (!osintConfig) return;
    try {
      const payload = await updateOsintConfig(osintConfig);
      setOsintConfig(payload);
      setStatusLine("Configuração do OSINT Lab salva.");
    } catch (error) {
      setStatusLine(`Falha ao salvar configuração OSINT: ${String(error)}`);
    }
  }

  async function handleCreateOsintInvestigation() {
    try {
      const payload = await createOsintInvestigation({
        project_id: selectedProjectId || undefined,
        session_id: selectedSessionId || undefined,
        ...osintInvestigationForm
      });
      setSelectedInvestigationId(payload.id);
      setOsintSearchQuery(payload.target_entity || payload.objective || payload.title);
      setStatusLine(`Investigação OSINT criada: ${payload.title}.`);
      await refreshOsint(selectedProjectId || undefined, payload.id);
      await refreshOsintInvestigation(payload.id);
    } catch (error) {
      setStatusLine(`Falha ao criar investigação OSINT: ${String(error)}`);
    }
  }

  async function handleInvestigationConnectorToggle(connectorId: string) {
    if (!selectedInvestigation) return;
    const enabled = new Set(selectedInvestigation.enabled_connector_ids ?? []);
    if (enabled.has(connectorId)) {
      enabled.delete(connectorId);
    } else {
      enabled.add(connectorId);
    }
    try {
      const payload = await patchOsintInvestigation(selectedInvestigation.id, {
        enabled_connector_ids: [...enabled]
      });
      setSelectedInvestigation(payload);
      setStatusLine(`Conectores da investigação atualizados para ${payload.title}.`);
      await refreshOsint(selectedProjectId || undefined, payload.id);
      await refreshOsintInvestigation(payload.id);
    } catch (error) {
      setStatusLine(`Falha ao atualizar conectores da investigação: ${String(error)}`);
    }
  }

  async function handleToggleOsintConnector(connector: OsintConnectorState) {
    try {
      if (connector.enabled_global) {
        await disableOsintConnector(connector.connector_id);
        setStatusLine(`Conector ${connector.label} desligado globalmente.`);
      } else {
        await enableOsintConnector(connector.connector_id);
        setStatusLine(`Conector ${connector.label} ligado globalmente.`);
      }
      await refreshOsint(selectedProjectId || undefined, selectedInvestigationId || undefined);
    } catch (error) {
      setStatusLine(`Falha ao alterar conector OSINT: ${String(error)}`);
    }
  }

  async function handlePlanOsint() {
    if (!selectedInvestigationId) return;
    try {
      const payload = await planOsintInvestigation(selectedInvestigationId, osintSearchQuery);
      setOsintPlanQueries(payload.queries);
      setStatusLine(`Plano de consulta OSINT atualizado com ${payload.queries.length} queries.`);
    } catch (error) {
      setStatusLine(`Falha ao planejar investigação OSINT: ${String(error)}`);
    }
  }

  async function handleSearchOsint() {
    if (!selectedInvestigationId || !osintSearchQuery.trim()) return;
    try {
      const payload = await searchOsintInvestigation(selectedInvestigationId, {
        query: osintSearchQuery.trim(),
        connector_ids: selectedInvestigation?.enabled_connector_ids ?? [],
        source_registry_ids: selectedInvestigation?.source_registry_ids ?? [],
        via_tor: false,
        limit: Number(osintConfig?.default_max_results ?? 5)
      });
      setOsintSources(payload.results);
      setOsintRuns((current) => [payload.run, ...current.filter((item) => item.id !== payload.run.id)]);
      setStatusLine(`Busca OSINT concluída com ${payload.results.length} fontes.`);
      await refreshOsintInvestigation(selectedInvestigationId);
    } catch (error) {
      setStatusLine(`Falha na busca OSINT: ${String(error)}`);
    }
  }

  async function handleFetchOsint(sourceId?: string, url?: string) {
    if (!selectedInvestigationId) return;
    try {
      const payload = await fetchOsintInvestigation(selectedInvestigationId, {
        source_id: sourceId,
        url: url || osintFetchUrl || undefined,
        via_tor: false
      });
      if (payload.capture) {
        setOsintEvidence((current) => [...payload.evidence, ...current.filter((item) => !payload.evidence.some((next) => next.id === item.id))]);
        setOsintClaims((current) => [...payload.claims, ...current.filter((item) => !payload.claims.some((next) => next.id === item.id))]);
        setStatusLine(`Fetch OSINT concluído para ${payload.capture.title || payload.capture.url}.`);
      } else {
        setStatusLine(`Fetch OSINT retornou: ${payload.error || payload.status || "sem captura"}.`);
      }
      await refreshOsintInvestigation(selectedInvestigationId);
    } catch (error) {
      setStatusLine(`Falha no fetch OSINT: ${String(error)}`);
    }
  }

  async function handleApproveEvidence(evidenceId: string) {
    try {
      await approveOsintEvidence(evidenceId);
      setStatusLine("Evidência OSINT aprovada.");
      await refreshOsintInvestigation(selectedInvestigationId);
    } catch (error) {
      setStatusLine(`Falha ao aprovar evidência OSINT: ${String(error)}`);
    }
  }

  async function handleApproveClaim(claimId: string) {
    try {
      await approveOsintClaim(claimId, { create_memory: true });
      setStatusLine("Claim aprovada e promovida para memória rastreável.");
      await refreshOsintInvestigation(selectedInvestigationId);
      await refreshProjectScoped(selectedProjectId);
      await refreshGlobal(selectedProjectId);
    } catch (error) {
      setStatusLine(`Falha ao aprovar claim OSINT: ${String(error)}`);
    }
  }

  async function handleExportOsintDataset() {
    if (!selectedInvestigationId) return;
    try {
      const payload = await exportOsintDatasetBundle({ investigation_id: selectedInvestigationId });
      setStatusLine(`Dataset OSINT exportado com ${payload.record_count} registros em ${payload.export_path}.`);
    } catch (error) {
      setStatusLine(`Falha ao exportar dataset OSINT: ${String(error)}`);
    }
  }

  async function handleCreateOsintRegistryEntry() {
    try {
      const payload = await createOsintSourceRegistryEntry(osintRegistryForm);
      setStatusLine(`Fonte ${payload.title} adicionada ao Source Registry.`);
      await refreshOsint(selectedProjectId || undefined, selectedInvestigationId || undefined);
    } catch (error) {
      setStatusLine(`Falha ao criar fonte no registry OSINT: ${String(error)}`);
    }
  }

  async function handleCreateProject() {
    try {
      const project = await createProject(projectForm);
      setStatusLine(`Projeto ${project.name} criado.`);
      await refreshGlobal(project.id);
      await refreshProjectScoped(project.id);
    } catch (error) {
      setStatusLine(`Falha ao criar projeto: ${String(error)}`);
    }
  }

  async function handleCreateJob(kind: "training" | "remote", connectorId: string) {
    try {
      await createJob(kind, {
        project_id: selectedProjectId || undefined,
        connector: connectorId,
        spec: {
          project_id: selectedProjectId,
          provider_id: selectedProviderId,
          model_name: selectedModel,
          source: "execution_center"
        }
      });
      setStatusLine(`Job ${kind} criado no conector ${connectorId}.`);
      await refreshGlobal(selectedProjectId);
    } catch (error) {
      setStatusLine(`Falha ao criar job ${kind}: ${String(error)}`);
    }
  }

  async function handleLoadRemoteLogs(jobId: string) {
    try {
      const payload = await getRemoteJobLogs(jobId);
      setRemoteLog(payload.content || "Sem logs ainda.");
      setStatusLine("Logs remotos carregados.");
    } catch (error) {
      setStatusLine(`Falha ao carregar logs remotos: ${String(error)}`);
    }
  }

  async function handleCompareRegistry() {
    if (!registryBaselineId || !registryCandidateId) return;
    try {
      const payload = await compareRegistryModels({
        baseline_artifact_id: registryBaselineId,
        candidate_artifact_id: registryCandidateId
      });
      setRegistryCompare(payload);
      setStatusLine("Comparação de modelos concluída.");
    } catch (error) {
      setStatusLine(`Falha ao comparar registry: ${String(error)}`);
    }
  }

  async function handleCreateDeployment() {
    if (!selectedProjectId || !registryCandidateId) return;
    try {
      await createDeployment(selectedProjectId, {
        artifact_id: registryCandidateId,
        environment: "local",
        notes: "Deploy registrado pelo Execution Center."
      });
      setStatusLine("Deploy registrado no projeto.");
      await refreshGlobal(selectedProjectId);
    } catch (error) {
      setStatusLine(`Falha ao registrar deploy: ${String(error)}`);
    }
  }

  async function handleSaveRemoteTrainPlaneConfig() {
    try {
      const payload = await updateRemoteTrainPlaneConfig({
        base_url: trainPlaneForm.base_url.trim(),
        token: trainPlaneForm.token.trim() || undefined,
        region: trainPlaneForm.region.trim(),
        instance_id: trainPlaneForm.instance_id.trim(),
        bucket: trainPlaneForm.bucket.trim(),
        ssm_enabled: trainPlaneForm.ssm_enabled,
        default_training_profile: safeJsonParse<Record<string, unknown>>(trainPlaneForm.default_training_profile, {}),
        default_serving_profile: safeJsonParse<Record<string, unknown>>(trainPlaneForm.default_serving_profile, {}),
        metadata: { updated_from: "execution_center" }
      });
      setRemoteTrainPlaneConfig(payload);
      setTrainPlaneForm((current) => ({ ...current, token: "" }));
      setStatusLine("Configuração do Remote Train Plane salva.");
      await refreshRemoteTrainPlane(true);
      await refreshGlobal(selectedProjectId);
    } catch (error) {
      setStatusLine(`Falha ao salvar configuração do Train Plane: ${String(error)}`);
    }
  }

  async function handleTestRemoteTrainPlaneConnection() {
    try {
      const payload = await testRemoteTrainPlaneConnection();
      setRemoteTrainPlaneConnection(payload);
      setStatusLine(payload.ok ? "Remote Train Plane respondeu ao teste de conexão." : `Train Plane indisponível: ${payload.error || "erro desconhecido"}`);
      if (payload.ok) {
        await refreshRemoteTrainPlane(true);
      }
    } catch (error) {
      setStatusLine(`Falha ao testar conexão do Train Plane: ${String(error)}`);
    }
  }

  async function handleSyncRemoteBaseModel() {
    try {
      const payload = await syncRemoteTrainPlaneBaseModel({
        project_id: selectedProjectId || undefined,
        name: remoteBaseModelForm.name,
        source_kind: remoteBaseModelForm.source_kind,
        source_ref: remoteBaseModelForm.source_ref,
        local_path: remoteBaseModelForm.local_path,
        format: remoteBaseModelForm.format,
        metadata: { synced_from: "execution_center" }
      });
      setStatusLine(`Base model sincronizado: ${payload.name}.`);
      await refreshRemoteTrainPlane();
    } catch (error) {
      setStatusLine(`Falha ao sincronizar base model: ${String(error)}`);
    }
  }

  async function handleSyncRemoteDatasetBundle() {
    try {
      const payload = await syncRemoteTrainPlaneDatasetBundle({
        project_id: selectedProjectId || undefined,
        session_id: selectedSessionId || undefined,
        project_slug: remoteDatasetForm.project_slug || selectedProject?.slug || "",
        name: remoteDatasetForm.name,
        approved_only: remoteDatasetForm.approved_only,
        max_records: remoteDatasetForm.max_records,
        metadata: { synced_from: "execution_center" }
      });
      setStatusLine(`Dataset bundle sincronizado: ${payload.name} com ${payload.record_count} registros.`);
      await refreshRemoteTrainPlane();
    } catch (error) {
      setStatusLine(`Falha ao sincronizar dataset bundle: ${String(error)}`);
    }
  }

  async function handleCreateRemoteTrainRun() {
    const baseModelId = remoteRunForm.base_model_id || remoteBaseModels[0]?.id;
    const datasetBundleId = remoteRunForm.dataset_bundle_id || remoteDatasetBundles[0]?.id;
    if (!baseModelId || !datasetBundleId) {
      setStatusLine("Sincronize pelo menos um base model e um dataset bundle antes de iniciar o treino remoto.");
      return;
    }
    try {
      const payload = await createRemoteTrainPlaneRun({
        project_id: selectedProjectId || undefined,
        project_slug: selectedProject?.slug || remoteDatasetForm.project_slug,
        name: remoteRunForm.name,
        base_model_id: baseModelId,
        dataset_bundle_id: datasetBundleId,
        summary: remoteRunForm.summary,
        training_profile: safeJsonParse<Record<string, unknown>>(trainPlaneForm.default_training_profile, {})
      });
      setSelectedRemoteTrainRunId(payload.id);
      setStatusLine(`Training run remoto criado: ${payload.name}.`);
      await refreshRemoteTrainPlane();
      await refreshGlobal(selectedProjectId);
    } catch (error) {
      setStatusLine(`Falha ao criar training run remoto: ${String(error)}`);
    }
  }

  async function handleCancelRemoteTrainRun() {
    if (!selectedRemoteTrainRunId) return;
    try {
      const payload = await cancelRemoteTrainPlaneRun(selectedRemoteTrainRunId, selectedProjectId || undefined);
      setSelectedRemoteTrainRun(payload);
      setStatusLine("Cancelamento solicitado para o training run remoto.");
      await refreshRemoteTrainPlane();
      await refreshGlobal(selectedProjectId);
    } catch (error) {
      setStatusLine(`Falha ao cancelar training run remoto: ${String(error)}`);
    }
  }

  async function handleRemoteArtifactAction(artifactId: string, action: "merge" | "promote") {
    try {
      if (action === "merge") {
        await mergeRemoteTrainPlaneArtifact(artifactId, selectedProjectId || undefined);
        setStatusLine("Merge do artefato remoto solicitado.");
      } else {
        await promoteRemoteTrainPlaneArtifact(artifactId, selectedProjectId || undefined);
        setStatusLine("Artefato remoto promovido para o registry.");
      }
      await refreshRemoteTrainPlane();
      await refreshGlobal(selectedProjectId);
    } catch (error) {
      setStatusLine(`Falha na ação do artefato remoto: ${String(error)}`);
    }
  }

  async function handleRemoteReview(kind: "evaluation" | "comparison") {
    if (!remoteReviewForm.candidate_artifact_id) {
      setStatusLine("Selecione um artefato remoto para avaliar ou comparar.");
      return;
    }
    const prompts = remoteReviewForm.prompt_blob
      .split("\n")
      .map((item) => item.trim())
      .filter(Boolean);
    try {
      if (kind === "evaluation") {
        const payload = await createRemoteTrainPlaneEvaluation({
          project_id: selectedProjectId || undefined,
          session_id: selectedSessionId || undefined,
          candidate_artifact_id: remoteReviewForm.candidate_artifact_id,
          baseline_mode: remoteReviewForm.baseline_mode,
          baseline_provider_id: remoteReviewForm.baseline_provider_id || undefined,
          baseline_model_name: remoteReviewForm.baseline_model_name || undefined,
          suite_name: "orquestra-eval-lab",
          prompts,
          metadata: { created_from: "execution_center" }
        });
        setStatusLine(`Evaluation run remoto criado: ${payload.suite_name}.`);
      } else {
        const payload = await createRemoteTrainPlaneComparison({
          project_id: selectedProjectId || undefined,
          session_id: selectedSessionId || undefined,
          candidate_artifact_id: remoteReviewForm.candidate_artifact_id,
          baseline_mode: remoteReviewForm.baseline_mode,
          baseline_provider_id: remoteReviewForm.baseline_provider_id || undefined,
          baseline_model_name: remoteReviewForm.baseline_model_name || undefined,
          prompt_set_name: "orquestra-compare-lab",
          prompts,
          metadata: { created_from: "execution_center" }
        });
        setStatusLine(`Comparison run remoto criado: ${payload.prompt_set_name}.`);
      }
      await refreshRemoteTrainPlane();
    } catch (error) {
      setStatusLine(`Falha ao rodar ${kind === "evaluation" ? "evaluation" : "comparison"} remoto: ${String(error)}`);
    }
  }

  async function handleCreateStorageLocation() {
    try {
      await createStorageLocation({
        label: storageLocationForm.label,
        backend: storageLocationForm.backend,
        base_uri: storageLocationForm.base_uri,
        quota_bytes: storageLocationForm.quota_bytes ? Number(storageLocationForm.quota_bytes) : undefined,
        metadata: { created_from: "settings_center" }
      });
      setStatusLine("Local de armazenamento adicionado ao Storage Fabric.");
      await refreshGlobal(selectedProjectId);
    } catch (error) {
      setStatusLine(`Falha ao criar storage location: ${String(error)}`);
    }
  }

  async function handleSaveRuntimeConfig() {
    try {
      const payload = await updateRuntimeSettings({
        data_root: runtimeSettings?.runtime?.data_root,
        database_url: runtimeSettings?.runtime?.database_url,
        qdrant_path: runtimeSettings?.runtime?.qdrant_path,
        storage_policy: "local_processing_hub"
      });
      setRuntimeSettings(payload);
      setStatusLine("runtime.json atualizado com política local-first.");
    } catch (error) {
      setStatusLine(`Falha ao salvar runtime.json: ${String(error)}`);
    }
  }

  async function handleCreateSecret() {
    if (!secretForm.value.trim()) {
      setStatusLine("Informe a chave localmente para salvar no Keychain. Ela não será exibida depois.");
      return;
    }
    try {
      await createSecret({
        provider_id: secretForm.provider_id,
        label: secretForm.label,
        secret_ref: secretForm.secret_ref,
        value: secretForm.value,
        metadata: { created_from: "settings_center" }
      });
      setSecretForm((current) => ({ ...current, value: "" }));
      setStatusLine("Segredo salvo no cofre seguro.");
      await refreshGlobal(selectedProjectId);
    } catch (error) {
      setStatusLine(`Falha ao salvar segredo: ${String(error)}`);
    }
  }

  async function handleRefreshModelCatalog() {
    try {
      await refreshModelCatalog(selectedProviderId, false);
      setStatusLine("Catálogo de modelos atualizado.");
      await refreshGlobal(selectedProjectId);
    } catch (error) {
      setStatusLine(`Falha ao atualizar catálogo: ${String(error)}`);
    }
  }

  async function handleSimulateRouter() {
    try {
      const payload = await simulateModelRouter({
        session_id: selectedSessionId || undefined,
        task_type: "chat",
        preset: sessionProfile?.preset || "assistant",
        provider_id: selectedProviderId,
        model_name: selectedModel
      });
      setRouterSimulation(payload);
      setStatusLine("Router interno simulou a decisão para o contexto atual.");
    } catch (error) {
      setStatusLine(`Falha ao simular router: ${String(error)}`);
    }
  }

  async function handleRunOperation(actionId: string) {
    try {
      setOpsActionBusyId(actionId);
      const run = await createOpsRun({ action_id: actionId });
      setSelectedRunId(run.run_id);
      setSelectedRun(run);
      setStatusLine(`Execução operacional iniciada: ${run.label}.`);
      await refreshGlobal(selectedProjectId);
    } catch (error) {
      setStatusLine(`Falha ao iniciar ação operacional: ${String(error)}`);
    } finally {
      setOpsActionBusyId("");
    }
  }

  return (
    <div className="orquestra-shell">
      <aside className="rail">
        <div className="rail-brand">
          <div className="brand-chip">
            <img src={orquestraLogo} alt="Ícone Orquestra AI" />
          </div>
          <div>
            <strong>Orquestra AI</strong>
            <span>Dashboard + Processo + Memória + Execução</span>
          </div>
        </div>

        <nav className="rail-nav">
          {views.map((item) => (
            <button
              key={item.id}
              type="button"
              className={view === item.id ? "rail-item active" : "rail-item"}
              onClick={() => setView(item.id)}
            >
              <strong>{item.title}</strong>
              <span>{item.helper}</span>
            </button>
          ))}
        </nav>

        <div className="rail-status">
          <div className="pulse" />
          <p>{statusLine}</p>
        </div>
      </aside>

      <main className="main-shell">
        <header className="topbar">
          <div>
            <p className="eyebrow">macOS-first control plane</p>
            <h1>{currentView.title}</h1>
            <span className="subtitle">{currentView.helper}</span>
          </div>

          <div className="topbar-controls">
            <label>
              Projeto
              <select value={selectedProjectId} onChange={(event) => setSelectedProjectId(event.target.value)}>
                {projects.map((project) => (
                  <option key={project.id} value={project.id}>
                    {project.name}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Provider
              <select value={selectedProviderId} onChange={(event) => setSelectedProviderId(event.target.value)}>
                {providers.map((provider) => (
                  <option key={provider.provider_id} value={provider.provider_id}>
                    {provider.label}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Modelo
              <select value={selectedModel} onChange={(event) => setSelectedModel(event.target.value)}>
                {models.map((model) => (
                  <option key={model} value={model}>
                    {model}
                  </option>
                ))}
              </select>
            </label>
            <button
              type="button"
              className="ghost-button"
              onClick={() =>
                refreshGlobal(selectedProjectId)
                  .then(() => refreshProjectScoped(selectedProjectId))
                  .catch((error) => setStatusLine(`Falha ao atualizar: ${String(error)}`))
              }
            >
              Atualizar
            </button>
          </div>
        </header>

        <section className="hero-strip">
          <div className="hero-copy">
            <h2>O Orquestra agora expõe a operação inteira em uma única superfície para web e desktop macOS.</h2>
            <p>
              O dashboard mostra serviços que fazem a stack funcionar, o centro de processo acompanha sessões e scans,
              a memória fica visível como sistema vivo e o centro de execução controla validação, build, instalação,
              jobs, providers e registry.
            </p>
          </div>
          <div className="hero-metrics">
            {(opsDashboard?.metrics ?? []).map((metric) => (
              <article key={metric.id}>
                <span>{metric.label}</span>
                <strong>{metric.value}</strong>
                <small>{metric.helper}</small>
              </article>
            ))}
            {!opsDashboard && (
              <article>
                <span>Runtime</span>
                <strong>Carregando</strong>
                <small>Aguardando snapshot operacional.</small>
              </article>
            )}
          </div>
        </section>

        <div className="workspace-grid">
          <section className="primary-stage">
            {view === "dashboard" && (
              <div className="stage-grid">
                <section className="panel">
                  <div className="panel-head">
                    <div>
                      <p className="eyebrow">Service fabric</p>
                      <h3>Todos os serviços que fazem o Orquestra funcionar</h3>
                    </div>
                    <span className="panel-meta">snapshot {formatDate(opsDashboard?.generated_at)}</span>
                  </div>

                  {servicesByCategory.map(([category, services]) => (
                    <div key={category} className="service-cluster">
                      <div className="cluster-head">
                        <strong>{serviceCategoryLabels[category] || category}</strong>
                        <span>{services.length} itens</span>
                      </div>
                      <div className="service-grid">
                        {services.map((service) => (
                          <article key={service.service_id} className={`service-card ${serviceTone(service.status, service.ready)}`}>
                            <div className="service-head">
                              <strong>{service.label}</strong>
                              <span className={`state-pill ${serviceTone(service.status, service.ready)}`}>{service.status}</span>
                            </div>
                            <p>{service.summary}</p>
                            <small>{service.detail}</small>
                          </article>
                        ))}
                      </div>
                    </div>
                  ))}
                </section>

                <section className="panel two-column-panel">
                  <div>
                    <div className="panel-head slim">
                      <div>
                        <p className="eyebrow">Quick control</p>
                        <h3>Ações gerenciadas</h3>
                      </div>
                    </div>
                    <div className="action-grid">
                      {opsActions.map((action) => (
                        <button
                          key={action.action_id}
                          type="button"
                          className={`action-card ${opsActionBusyId === action.action_id ? "active" : ""}`}
                          onClick={() => handleRunOperation(action.action_id)}
                          disabled={Boolean(opsActionBusyId)}
                        >
                          <strong>{action.label}</strong>
                          <span>{action.kind}</span>
                          <p>{action.summary}</p>
                          <small>{action.command_preview}</small>
                        </button>
                      ))}
                    </div>
                  </div>

                  <div>
                    <div className="panel-head slim">
                      <div>
                        <p className="eyebrow">Distribution</p>
                        <h3>Artefatos de instalação</h3>
                      </div>
                    </div>
                    <div className="artifact-grid">
                      <article className="provider-card">
                        <strong>App Bundle</strong>
                        <span>{opsDashboard?.execution_snapshot.artifacts.app_bundle_exists ? "ready" : "missing"}</span>
                        <p>{opsDashboard?.execution_snapshot.artifacts.app_bundle_path || "-"}</p>
                      </article>
                      <article className="provider-card">
                        <strong>DMG</strong>
                        <span>{opsDashboard?.execution_snapshot.artifacts.dmg_exists ? "ready" : "missing"}</span>
                        <p>{opsDashboard?.execution_snapshot.artifacts.dmg_path || "-"}</p>
                      </article>
                      <article className="provider-card">
                        <strong>Instalador CLI completo</strong>
                        <span>{opsDashboard?.execution_snapshot.artifacts.full_installer_exists ? "ready" : "missing"}</span>
                        <p>{opsDashboard?.execution_snapshot.artifacts.full_installer_path || opsDashboard?.execution_snapshot.artifacts.installer_path || "-"}</p>
                      </article>
                      <article className="provider-card">
                        <strong>Desinstalador CLI completo</strong>
                        <span>{opsDashboard?.execution_snapshot.artifacts.full_uninstaller_exists ? "ready" : "missing"}</span>
                        <p>{opsDashboard?.execution_snapshot.artifacts.full_uninstaller_path || opsDashboard?.execution_snapshot.artifacts.uninstaller_path || "-"}</p>
                      </article>
                      <article className="provider-card">
                        <strong>Instalador gráfico</strong>
                        <span>{opsDashboard?.execution_snapshot.artifacts.graphical_installer_app_exists ? "ready" : "missing"}</span>
                        <p>{opsDashboard?.execution_snapshot.artifacts.graphical_installer_app_path || "-"}</p>
                      </article>
                      <article className="provider-card">
                        <strong>DMG gráfico completo</strong>
                        <span>{opsDashboard?.execution_snapshot.artifacts.graphical_installer_dmg_exists ? "ready" : "missing"}</span>
                        <p>{opsDashboard?.execution_snapshot.artifacts.graphical_installer_dmg_path || "-"}</p>
                      </article>
                    </div>
                  </div>
                </section>
              </div>
            )}

            {view === "process" && (
              <div className="stage-grid">
                <section className="panel two-column-panel">
                  <div>
                    <div className="panel-head slim">
                      <div>
                        <p className="eyebrow">Listeners</p>
                        <h3>Estado vivo da stack</h3>
                      </div>
                    </div>
                    <div className="metric-grid">
                      <article className="provider-card">
                        <strong>API</strong>
                        <span>{opsDashboard?.process_snapshot.listeners.api ? "online" : "offline"}</span>
                        <p>{health?.workspace_root || "-"}</p>
                      </article>
                      <article className="provider-card">
                        <strong>Versão</strong>
                        <span>{health?.app_version ? `v${health.app_version}` : "-"}</span>
                        <p>{health?.runtime.mode || "workspace"}</p>
                      </article>
                      <article className="provider-card">
                        <strong>Web</strong>
                        <span>{opsDashboard?.process_snapshot.listeners.web ? "online" : "idle"}</span>
                        <p>http://127.0.0.1:4177</p>
                      </article>
                      <article className="provider-card">
                        <strong>tmux</strong>
                        <span>{opsDashboard?.process_snapshot.tmux_sessions.length || 0} sessões</span>
                        <p>{shortList(opsDashboard?.process_snapshot.tmux_sessions ?? [])}</p>
                      </article>
                      <article className="provider-card">
                        <strong>Runtime</strong>
                        <span>{Object.keys(opsDashboard?.process_snapshot.runtime_paths ?? {}).length} paths</span>
                        <p>
                          Schema v{health?.schema_version ?? "-"}/{health?.schema_target_version ?? "-"} · {opsDashboard?.process_snapshot.runtime_state?.backup_count ?? 0} backups
                        </p>
                      </article>
                    </div>
                  </div>

                  <div>
                    <div className="panel-head slim">
                      <div>
                        <p className="eyebrow">Background processes</p>
                        <h3>Processos observados no sistema</h3>
                      </div>
                    </div>
                    <div className="stack-list">
                      {(opsDashboard?.process_snapshot.background_processes ?? []).map((process) => (
                        <article key={`${process.pid}-${process.command}`} className="stack-row">
                          <strong>{process.pid || "pid?"}</strong>
                          <span>{compactText(process.command, 140)}</span>
                        </article>
                      ))}
                      {!(opsDashboard?.process_snapshot.background_processes.length) && (
                        <div className="empty-state">
                          <h4>Nenhum processo relevante ativo.</h4>
                          <p>O ambiente está pronto, mas sem web/API/tmux rodando agora.</p>
                        </div>
                      )}
                    </div>
                  </div>
                </section>

                <section className="panel two-column-panel">
                  <div>
                    <div className="panel-head slim">
                      <div>
                        <p className="eyebrow">Sessions</p>
                        <h3>Fluxo de trabalho ativo</h3>
                      </div>
                      <button
                        type="button"
                        className="ghost-button"
                        onClick={openSessionSetup}
                      >
                        Nova sessão
                      </button>
                    </div>
                    <div className="session-list tall">
                      {sessions.map((session) => (
                        <button
                          key={session.id}
                          type="button"
                          className={selectedSessionId === session.id ? "session-card active" : "session-card"}
                          onClick={() => setSelectedSessionId(session.id)}
                        >
                          <strong>{session.title}</strong>
                          <span>{session.provider_id}/{session.model_name}</span>
                          <small>{formatDate(session.last_message_at || session.updated_at || session.created_at)}</small>
                        </button>
                      ))}
                    </div>
                  </div>

                  <div>
                    <div className="panel-head slim">
                      <div>
                        <p className="eyebrow">Workspace scans</p>
                        <h3>Inventário e execução de leitura</h3>
                      </div>
                    </div>
                    <div className="scan-grid tall">
                      {workspaceScans.map((scan) => (
                        <button
                          key={scan.id}
                          type="button"
                          className={selectedScanId === scan.id ? "scan-card active" : "scan-card"}
                          onClick={() => setSelectedScanId(scan.id)}
                        >
                          <strong>{scan.root_path}</strong>
                          <span>{scan.total_assets} ativos</span>
                          <small>{formatBytes(scan.total_bytes)}</small>
                        </button>
                      ))}
                    </div>
                  </div>
                </section>
              </div>
            )}

            {view === "memory" && (
              <div className="stage-grid">
                <section className="panel">
                  <div className="panel-head">
                    <div>
                      <p className="eyebrow">Memory fabric</p>
                      <h3>Sistema de memória do Orquestra</h3>
                    </div>
                  </div>

                  <div className="metric-grid">
                    <article className="provider-card">
                      <strong>Tópicos</strong>
                      <span>{opsDashboard?.memory_snapshot.topics ?? 0}</span>
                      <p>Memória durável consolidada.</p>
                    </article>
                    <article className="provider-card">
                      <strong>Registros</strong>
                      <span>{opsDashboard?.memory_snapshot.records ?? 0}</span>
                      <p>Memória episódica, semântica e workspace.</p>
                    </article>
                    <article className="provider-card">
                      <strong>Candidates</strong>
                      <span>{opsDashboard?.memory_snapshot.training_candidates ?? 0}</span>
                      <p>Candidatos de treino a partir do uso real.</p>
                    </article>
                    <article className="provider-card">
                      <strong>Memory Inbox</strong>
                      <span>{opsDashboard?.memory_snapshot.review_pending ?? memoryCandidates.length}</span>
                      <p>Candidatos revisáveis antes de virar memória durável.</p>
                    </article>
                    <article className="provider-card">
                      <strong>Transcript events</strong>
                      <span>{opsDashboard?.memory_snapshot.message_count ?? 0}</span>
                      <p>Eventos persistidos na camada bruta.</p>
                    </article>
                  </div>

                  <div className="scope-strip">
                    {(opsDashboard?.memory_snapshot.scope_breakdown ?? []).map((scope) => (
                      <span key={scope.scope}>{scope.scope}: {scope.count}</span>
                    ))}
                  </div>
                </section>

                <section className="panel two-column-panel">
                  <div>
                    <div className="panel-head slim">
                      <div>
                        <p className="eyebrow">Recall</p>
                        <h3>Seleção semântica + lexical</h3>
                      </div>
                    </div>
                    <div className="form-stack">
                      <textarea value={memoryRecallQuery} onChange={(event) => setMemoryRecallQuery(event.target.value)} />
                      <div className="composer-actions">
                        <button type="button" className="primary-button" onClick={handleRecallMemory}>
                          Executar recall
                        </button>
                        <button type="button" className="ghost-button" onClick={handleCreateManualMemory}>
                          Criar memória manual
                        </button>
                      </div>
                    </div>
                    <div className="memory-column">
                      {(memoryRecallResults?.items ?? []).map((item, index) => (
                        <article key={`${item.title}-${index}`} className="memory-card">
                          <strong>{item.title}</strong>
                          <span>{item.scope || "memory"}</span>
                          <p>{item.content}</p>
                        </article>
                      ))}
                    </div>
                  </div>

                  <div>
                    <div className="panel-head slim">
                      <div>
                        <p className="eyebrow">Promotion</p>
                        <h3>Memória durável e candidates</h3>
                      </div>
                    </div>
                    <div className="form-stack">
                      <input value={promoteTitle} onChange={(event) => setPromoteTitle(event.target.value)} />
                      <textarea value={promoteContent} onChange={(event) => setPromoteContent(event.target.value)} />
                      <div className="composer-actions">
                        <button type="button" className="primary-button" onClick={handlePromoteMemory}>
                          Promover memória
                        </button>
                      </div>
                    </div>
                    <div className="memory-grid dense">
                      <div className="memory-column">
                        <h4>Registros recentes</h4>
                        {memoryRecords.map((record) => (
                          <article key={record.id} className="memory-card">
                            <strong>{record.scope}</strong>
                            <span>{record.source}</span>
                            <p>{record.content}</p>
                          </article>
                        ))}
                      </div>
                      <div className="memory-column">
                        <h4>Training candidates</h4>
                        {trainingCandidates.map((candidate) => (
                          <article key={candidate.id} className="memory-card">
                            <strong>{candidate.source}</strong>
                            <span>{candidate.approved ? "approved" : "draft"}</span>
                            <p>{candidate.instruction}</p>
                          </article>
                        ))}
                        <h4>Memory Inbox</h4>
                        {memoryCandidates.map((candidate) => (
                          <article key={candidate.id} className="memory-card">
                            <strong>{candidate.title}</strong>
                            <span>{candidate.scope} · {candidate.status}</span>
                            <p>{compactText(candidate.content, 180)}</p>
                          </article>
                        ))}
                      </div>
                    </div>
                  </div>
                </section>
              </div>
            )}

            {view === "execution" && (
              <div className="stage-grid">
                <section className="panel two-column-panel">
                  <div>
                    <div className="panel-head slim">
                      <div>
                        <p className="eyebrow">Providers</p>
                        <h3>Mesh gateway e modelos</h3>
                      </div>
                    </div>
                    <div className="provider-grid">
                      {providers.map((provider) => (
                        <article key={provider.id} className="provider-card">
                          <strong>{provider.label}</strong>
                          <span>{provider.transport}</span>
                          <p>{provider.default_model || "sem default"}</p>
                          <div className="token-list">
                            {provider.capabilities.map((capability) => (
                              <span key={capability}>{capability}</span>
                            ))}
                          </div>
                        </article>
                      ))}
                    </div>
                  </div>

                  <div>
                    <div className="panel-head slim">
                      <div>
                        <p className="eyebrow">Execution management</p>
                        <h3>Ações, runs e logs</h3>
                      </div>
                    </div>
                    <div className="action-grid compact">
                      {opsActions.map((action) => (
                        <button
                          key={action.action_id}
                          type="button"
                          className={`action-card ${selectedRun?.action_id === action.action_id ? "active" : ""}`}
                          onClick={() => handleRunOperation(action.action_id)}
                          disabled={Boolean(opsActionBusyId)}
                        >
                          <strong>{action.label}</strong>
                          <span>{action.kind}</span>
                          <p>{action.summary}</p>
                        </button>
                      ))}
                    </div>
                    <div className="run-grid">
                      {opsRuns.map((run) => (
                        <button
                          key={run.run_id}
                          type="button"
                          className={selectedRunId === run.run_id ? "job-row active" : "job-row"}
                          onClick={() => setSelectedRunId(run.run_id)}
                        >
                          <strong>{run.label}</strong>
                          <span>{run.status}</span>
                          <small>{formatDate(run.started_at)}</small>
                        </button>
                      ))}
                    </div>
                    <pre className="preview-text terminal">
                      {selectedRun?.log_tail || "Selecione uma execução operacional para acompanhar os logs."}
                    </pre>

                    <div className="panel-head slim">
                      <div>
                        <p className="eyebrow">Local workflows</p>
                        <h3>Execução multi-step</h3>
                      </div>
                      <div className="composer-actions">
                        <button type="button" className="ghost-button" onClick={handleStartValidationWorkflow} disabled={!selectedSessionId}>
                          Novo workflow
                        </button>
                        <button type="button" className="ghost-button" onClick={handleCancelWorkflow} disabled={!selectedWorkflowId || selectedWorkflow?.status !== "running"}>
                          Cancelar
                        </button>
                      </div>
                    </div>
                    <div className="run-grid">
                      {workflowRuns.map((run) => (
                        <button
                          key={run.id}
                          type="button"
                          className={selectedWorkflowId === run.id ? "job-row active" : "job-row"}
                          onClick={() => setSelectedWorkflowId(run.id)}
                        >
                          <strong>{run.workflow_name}</strong>
                          <span>{run.status}</span>
                          <small>{run.task_id ? `task:${sessionTaskMap.get(run.task_id)?.subject || run.task_id.slice(0, 8)}` : "sem task"}</small>
                          <small>{run.output_exists ? "com artefato" : "sem artefato"}</small>
                          <small>{Math.round((run.progress ?? 0) * 100)}%</small>
                        </button>
                      ))}
                    </div>
                    <div className="workflow-step-list">
                      {(selectedWorkflow?.steps ?? []).map((step) => (
                        <article key={step.id} className="stack-row">
                          <strong>{step.step_index + 1}</strong>
                          <span>{step.label}</span>
                          <small>{step.status}</small>
                          <small>{Object.keys(step.output ?? {}).length ? compactText(JSON.stringify(step.output), 90) : "sem saída"}</small>
                        </article>
                      ))}
                    </div>
                    <div className="context-list">
                      <span><strong>Log:</strong> {selectedWorkflow?.log_path || "-"}</span>
                      <span><strong>Output:</strong> {selectedWorkflow?.output_path || "-"}</span>
                      <span><strong>Resultado:</strong> {workflowStatusLabel(selectedWorkflow?.status)}</span>
                    </div>
                    <pre className="preview-text terminal">
                      {selectedWorkflow?.log_tail || "Selecione um workflow para acompanhar progresso, passos e logs."}
                    </pre>
                    <pre className="preview-text compact">
                      {selectedWorkflow?.output_preview
                        ? JSON.stringify(selectedWorkflow.output_preview, null, 2)
                        : "O preview do output do workflow aparece aqui quando existir."}
                    </pre>
                  </div>
                </section>

                <section className="panel two-column-panel">
                  <div>
                    <div className="panel-head slim">
                      <div>
                        <p className="eyebrow">Connectors & jobs</p>
                        <h3>Train Ops e remote orchestration</h3>
                      </div>
                    </div>
                    <div className="provider-grid">
                      {connectors.map((connector) => (
                        <article key={connector.connector_id} className="provider-card">
                          <strong>{connector.label}</strong>
                          <span>{connector.ready ? "ready" : connector.status}</span>
                          <p>{connector.description}</p>
                          <div className="token-list">
                            {connector.capabilities.map((capability) => (
                              <span key={capability}>{capability}</span>
                            ))}
                          </div>
                          <div className="composer-actions">
                            <button type="button" className="ghost-button" onClick={() => handleCreateJob("training", connector.connector_id)}>
                              Job treino
                            </button>
                            <button type="button" className="primary-button" onClick={() => handleCreateJob("remote", connector.connector_id)}>
                              Job remoto
                            </button>
                          </div>
                        </article>
                      ))}
                    </div>

                    <article className="result-panel">
                      <header>
                        <strong>OSINT Connector Hub</strong>
                        <span>{osintConnectors.filter((item) => item.ready).length} prontos</span>
                      </header>
                      <div className="context-list">
                        <span><strong>Investigação ativa:</strong> {selectedInvestigation?.title || "nenhuma"}</span>
                        <span><strong>Tor proxy:</strong> {osintConfig?.tor_proxy_url || "não configurado"}</span>
                        <span><strong>Evidências:</strong> {osintEvidence.length}</span>
                        <span><strong>Claims:</strong> {osintClaims.length}</span>
                      </div>
                      <div className="token-list">
                        {osintConnectors.slice(0, 6).map((connector) => (
                          <span key={connector.connector_id}>{connector.label}:{connector.enabled_global ? "on" : "off"}</span>
                        ))}
                      </div>
                      <div className="composer-actions">
                        <button type="button" className="ghost-button" onClick={() => setView("osint")}>
                          Abrir OSINT Lab
                        </button>
                        <button type="button" className="ghost-button" onClick={handleExportOsintDataset} disabled={!selectedInvestigationId}>
                          Exportar bundle OSINT
                        </button>
                      </div>
                    </article>

                    <div className="jobs-grid">
                      <div>
                        <h4>Training jobs</h4>
                        {trainingJobs.map((job) => (
                          <button key={job.id} type="button" className="job-row">
                            <strong>{job.connector}</strong>
                            <span>{job.status}</span>
                            <small>{formatDate(job.created_at)}</small>
                          </button>
                        ))}
                      </div>
                      <div>
                        <h4>Remote jobs</h4>
                        {remoteJobs.map((job) => (
                          <button key={job.id} type="button" className="job-row" onClick={() => handleLoadRemoteLogs(job.id)}>
                            <strong>{job.connector}</strong>
                            <span>{job.status}</span>
                            <small>{formatDate(job.created_at)}</small>
                          </button>
                        ))}
                      </div>
                    </div>
                    <pre className="preview-text terminal">{remoteLog || "Selecione um job remoto para carregar logs."}</pre>
                  </div>

                  <div>
                    <div className="panel-head slim">
                      <div>
                        <p className="eyebrow">Registry & RAG</p>
                        <h3>Comparação, deploy e consulta executável</h3>
                      </div>
                    </div>
                    <div className="split-form">
                      <label>
                        Baseline
                        <select value={registryBaselineId} onChange={(event) => setRegistryBaselineId(event.target.value)}>
                          <option value="">Selecione</option>
                          {registryModels.map((item) => (
                            <option key={item.id} value={item.id}>
                              {item.name}
                            </option>
                          ))}
                        </select>
                      </label>
                      <label>
                        Candidate
                        <select value={registryCandidateId} onChange={(event) => setRegistryCandidateId(event.target.value)}>
                          <option value="">Selecione</option>
                          {registryModels.map((item) => (
                            <option key={item.id} value={item.id}>
                              {item.name}
                            </option>
                          ))}
                        </select>
                      </label>
                    </div>
                    <div className="composer-actions">
                      <button type="button" className="ghost-button" onClick={handleCreateDeployment} disabled={!registryCandidateId}>
                        Registrar deploy
                      </button>
                      <button type="button" className="primary-button" onClick={handleCompareRegistry} disabled={!registryBaselineId || !registryCandidateId}>
                        Comparar
                      </button>
                    </div>

                    {registryCompare && (
                      <div className="compare-grid">
                        <article className="result-panel">
                          <h4>Baseline</h4>
                          <p>{registryCompare.baseline.name}</p>
                        </article>
                        <article className="result-panel">
                          <h4>Candidate</h4>
                          <p>{registryCompare.candidate.name}</p>
                        </article>
                        <article className="result-panel">
                          <h4>Delta</h4>
                          <pre className="preview-text">{JSON.stringify(registryCompare.delta, null, 2)}</pre>
                        </article>
                      </div>
                    )}

                    <div className="form-stack">
                      <textarea value={ragPrompt} onChange={(event) => setRagPrompt(event.target.value)} />
                      <div className="composer-actions">
                        <button type="button" className="primary-button" onClick={handleRagQuery} disabled={ragLoading}>
                          {ragLoading ? "Consultando..." : "Executar consulta"}
                        </button>
                      </div>
                    </div>
                    {ragResult && (
                      <article className="result-panel">
                        <header>
                          <strong>{ragResult.provider_id || selectedProviderId}/{ragResult.model_name || selectedModel}</strong>
                          <span>{ragResult.latency_seconds?.toFixed(2) ?? "0.00"}s</span>
                        </header>
                        <p>{ragResult.answer}</p>
                      </article>
                    )}
                  </div>
                </section>

                <section className="panel">
                  <div className="panel-head">
                    <div>
                      <p className="eyebrow">Remote Train Plane</p>
                      <h3>EC2 train plane, avaliação comparativa e promotion lab</h3>
                    </div>
                    <div className="composer-actions">
                      <button type="button" className="ghost-button" onClick={handleTestRemoteTrainPlaneConnection}>
                        Testar conexão
                      </button>
                      <button type="button" className="primary-button" onClick={handleSaveRemoteTrainPlaneConfig}>
                        Salvar acesso
                      </button>
                    </div>
                  </div>

                  <div className="two-column-panel">
                    <div>
                      <div className="panel-head slim">
                        <div>
                          <p className="eyebrow">Access & config</p>
                          <h3>Endpoint, token e defaults operacionais</h3>
                        </div>
                      </div>
                      <div className="split-form">
                        <label>
                          Base URL
                          <input value={trainPlaneForm.base_url} onChange={(event) => setTrainPlaneForm((current) => ({ ...current, base_url: event.target.value }))} />
                        </label>
                        <label>
                          Token
                          <input value={trainPlaneForm.token} onChange={(event) => setTrainPlaneForm((current) => ({ ...current, token: event.target.value }))} placeholder="PAT do Train Plane" />
                        </label>
                        <label>
                          Região AWS
                          <input value={trainPlaneForm.region} onChange={(event) => setTrainPlaneForm((current) => ({ ...current, region: event.target.value }))} />
                        </label>
                        <label>
                          Instance ID
                          <input value={trainPlaneForm.instance_id} onChange={(event) => setTrainPlaneForm((current) => ({ ...current, instance_id: event.target.value }))} />
                        </label>
                        <label>
                          Bucket
                          <input value={trainPlaneForm.bucket} onChange={(event) => setTrainPlaneForm((current) => ({ ...current, bucket: event.target.value }))} />
                        </label>
                        <label className="toggle">
                          <input
                            type="checkbox"
                            checked={trainPlaneForm.ssm_enabled}
                            onChange={(event) => setTrainPlaneForm((current) => ({ ...current, ssm_enabled: event.target.checked }))}
                          />
                          <span>usar SSM / Session Manager</span>
                        </label>
                      </div>
                      <div className="form-stack">
                        <label className="full-label">
                          Default training profile (JSON)
                          <textarea value={trainPlaneForm.default_training_profile} onChange={(event) => setTrainPlaneForm((current) => ({ ...current, default_training_profile: event.target.value }))} />
                        </label>
                        <label className="full-label">
                          Default serving profile (JSON)
                          <textarea value={trainPlaneForm.default_serving_profile} onChange={(event) => setTrainPlaneForm((current) => ({ ...current, default_serving_profile: event.target.value }))} />
                        </label>
                      </div>
                      <div className="context-list">
                        <span><strong>Token:</strong> {remoteTrainPlaneConfig?.token_configured ? "configurado" : "ausente"}</span>
                        <span><strong>Base:</strong> {remoteTrainPlaneConfig?.base_url || "não configurada"}</span>
                        <span><strong>Conexão:</strong> {remoteTrainPlaneConnection?.ok ? "online" : remoteTrainPlaneConnection?.error || "não testada"}</span>
                        <span><strong>SSM:</strong> {remoteTrainPlaneConfig?.ssm_enabled ? "ativo" : "desligado"}</span>
                      </div>
                      {remoteTrainPlaneConnection?.health && (
                        <pre className="preview-text compact">
                          {JSON.stringify(remoteTrainPlaneConnection.health, null, 2)}
                        </pre>
                      )}
                    </div>

                    <div>
                      <div className="panel-head slim">
                        <div>
                          <p className="eyebrow">Base models & datasets</p>
                          <h3>Sync local para o train plane</h3>
                        </div>
                      </div>
                      <div className="split-form">
                        <label>
                          Nome do base model
                          <input value={remoteBaseModelForm.name} onChange={(event) => setRemoteBaseModelForm((current) => ({ ...current, name: event.target.value }))} />
                        </label>
                        <label>
                          Source kind
                          <select value={remoteBaseModelForm.source_kind} onChange={(event) => setRemoteBaseModelForm((current) => ({ ...current, source_kind: event.target.value }))}>
                            <option value="huggingface_ref">huggingface_ref</option>
                            <option value="uploaded_bundle">uploaded_bundle</option>
                          </select>
                        </label>
                        <label>
                          Hugging Face ref / URI
                          <input value={remoteBaseModelForm.source_ref} onChange={(event) => setRemoteBaseModelForm((current) => ({ ...current, source_ref: event.target.value }))} />
                        </label>
                        <label>
                          Caminho local opcional
                          <input value={remoteBaseModelForm.local_path} onChange={(event) => setRemoteBaseModelForm((current) => ({ ...current, local_path: event.target.value }))} />
                        </label>
                      </div>
                      <div className="composer-actions">
                        <button type="button" className="ghost-button" onClick={handleSyncRemoteBaseModel}>
                          Sincronizar base model
                        </button>
                      </div>

                      <div className="split-form">
                        <label>
                          Project slug
                          <input value={remoteDatasetForm.project_slug} onChange={(event) => setRemoteDatasetForm((current) => ({ ...current, project_slug: event.target.value }))} />
                        </label>
                        <label>
                          Dataset bundle name
                          <input value={remoteDatasetForm.name} onChange={(event) => setRemoteDatasetForm((current) => ({ ...current, name: event.target.value }))} />
                        </label>
                        <label>
                          Max records
                          <input
                            type="number"
                            value={remoteDatasetForm.max_records}
                            onChange={(event) => setRemoteDatasetForm((current) => ({ ...current, max_records: Number(event.target.value || 0) }))}
                          />
                        </label>
                        <label className="toggle">
                          <input
                            type="checkbox"
                            checked={remoteDatasetForm.approved_only}
                            onChange={(event) => setRemoteDatasetForm((current) => ({ ...current, approved_only: event.target.checked }))}
                          />
                          <span>apenas aprovados</span>
                        </label>
                      </div>
                      <div className="composer-actions">
                        <button type="button" className="primary-button" onClick={handleSyncRemoteDatasetBundle}>
                          Exportar dataset bundle
                        </button>
                      </div>

                      <div className="provider-grid">
                        {remoteBaseModels.map((item) => (
                          <article key={item.id} className="provider-card">
                            <strong>{item.name}</strong>
                            <span>{item.source_kind}</span>
                            <p>{compactText(item.source_ref || item.storage_uri, 96)}</p>
                          </article>
                        ))}
                      </div>
                      <div className="provider-grid">
                        {remoteDatasetBundles.map((item) => (
                          <article key={item.id} className="provider-card">
                            <strong>{item.name}</strong>
                            <span>{item.record_count} registros</span>
                            <p>{item.project_slug}</p>
                          </article>
                        ))}
                      </div>
                    </div>
                  </div>

                  <div className="two-column-panel">
                    <div>
                      <div className="panel-head slim">
                        <div>
                          <p className="eyebrow">Training runs</p>
                          <h3>Fila, progresso e checkpoints remotos</h3>
                        </div>
                        <div className="composer-actions">
                          <button type="button" className="ghost-button" onClick={handleCreateRemoteTrainRun}>
                            Criar run
                          </button>
                          <button type="button" className="ghost-button" onClick={handleCancelRemoteTrainRun} disabled={!selectedRemoteTrainRunId || selectedRemoteTrainRun?.status !== "running"}>
                            Cancelar run
                          </button>
                        </div>
                      </div>
                      <div className="form-stack">
                        <input value={remoteRunForm.name} onChange={(event) => setRemoteRunForm((current) => ({ ...current, name: event.target.value }))} />
                        <div className="split-form">
                          <label>
                            Base model
                            <select value={remoteRunForm.base_model_id} onChange={(event) => setRemoteRunForm((current) => ({ ...current, base_model_id: event.target.value }))}>
                              <option value="">Selecione</option>
                              {remoteBaseModels.map((item) => (
                                <option key={item.id} value={item.id}>
                                  {item.name}
                                </option>
                              ))}
                            </select>
                          </label>
                          <label>
                            Dataset bundle
                            <select value={remoteRunForm.dataset_bundle_id} onChange={(event) => setRemoteRunForm((current) => ({ ...current, dataset_bundle_id: event.target.value }))}>
                              <option value="">Selecione</option>
                              {remoteDatasetBundles.map((item) => (
                                <option key={item.id} value={item.id}>
                                  {item.name}
                                </option>
                              ))}
                            </select>
                          </label>
                        </div>
                        <textarea value={remoteRunForm.summary} onChange={(event) => setRemoteRunForm((current) => ({ ...current, summary: event.target.value }))} />
                      </div>
                      <div className="run-grid">
                        {remoteTrainRuns.map((run) => (
                          <button
                            key={run.id}
                            type="button"
                            className={selectedRemoteTrainRunId === run.id ? "job-row active" : "job-row"}
                            onClick={() => setSelectedRemoteTrainRunId(run.id)}
                          >
                            <strong>{run.name}</strong>
                            <span>{run.status}</span>
                            <small>{run.project_slug}</small>
                            <small>{run.current_step}/{run.total_steps || 0} passos</small>
                          </button>
                        ))}
                      </div>
                      <div className="context-list">
                        <span><strong>Status:</strong> {selectedRemoteTrainRun?.status || "idle"}</span>
                        <span><strong>Progresso:</strong> {selectedRemoteTrainRun ? `${selectedRemoteTrainRun.current_step}/${selectedRemoteTrainRun.total_steps || 0}` : "-"}</span>
                        <span><strong>Logs:</strong> {selectedRemoteTrainRun?.logs_path || "-"}</span>
                        <span><strong>Artefato:</strong> {selectedRemoteTrainRun?.artifact?.name || selectedRemoteTrainRun?.artifact_id || "pendente"}</span>
                      </div>
                      <svg viewBox="0 0 340 120" preserveAspectRatio="none" style={{ width: "100%", height: 120, background: "rgba(247, 234, 205, 0.38)", borderRadius: 16 }}>
                        <polyline
                          fill="none"
                          stroke="#0d6b5f"
                          strokeWidth="4"
                          points={buildSparklinePoints((selectedRemoteTrainRun?.metrics ?? []).map((item) => Number(item.loss || 0)).filter((value) => Number.isFinite(value)))}
                        />
                      </svg>
                      <pre className="preview-text compact">
                        {selectedRemoteTrainRun
                          ? JSON.stringify(
                              {
                                output: selectedRemoteTrainRun.output,
                                checkpoints: selectedRemoteTrainRun.checkpoints.map((item) => ({
                                  label: item.label,
                                  step_index: item.step_index,
                                  storage_uri: item.storage_uri
                                }))
                              },
                              null,
                              2
                            )
                          : "Selecione um training run remoto para acompanhar a evolução."}
                      </pre>
                    </div>

                    <div>
                      <div className="panel-head slim">
                        <div>
                          <p className="eyebrow">Evaluation lab</p>
                          <h3>Artifacts, benchmark e comparação baseline vs candidate</h3>
                        </div>
                      </div>
                      <div className="split-form">
                        <label>
                          Candidate artifact
                          <select
                            value={remoteReviewForm.candidate_artifact_id}
                            onChange={(event) => setRemoteReviewForm((current) => ({ ...current, candidate_artifact_id: event.target.value }))}
                          >
                            <option value="">Selecione</option>
                            {remoteArtifacts.map((item) => (
                              <option key={item.id} value={item.id}>
                                {item.name}
                              </option>
                            ))}
                          </select>
                        </label>
                        <label>
                          Baseline mode
                          <select value={remoteReviewForm.baseline_mode} onChange={(event) => setRemoteReviewForm((current) => ({ ...current, baseline_mode: event.target.value }))}>
                            <option value="lmstudio_local">lmstudio_local</option>
                            <option value="provider_api">provider_api</option>
                            <option value="trainplane_artifact">trainplane_artifact</option>
                          </select>
                        </label>
                        <label>
                          Provider baseline
                          <input value={remoteReviewForm.baseline_provider_id} onChange={(event) => setRemoteReviewForm((current) => ({ ...current, baseline_provider_id: event.target.value }))} />
                        </label>
                        <label>
                          Modelo baseline
                          <input value={remoteReviewForm.baseline_model_name} onChange={(event) => setRemoteReviewForm((current) => ({ ...current, baseline_model_name: event.target.value }))} />
                        </label>
                      </div>
                      <div className="form-stack">
                        <textarea value={remoteReviewForm.prompt_blob} onChange={(event) => setRemoteReviewForm((current) => ({ ...current, prompt_blob: event.target.value }))} />
                        <div className="composer-actions">
                          <button type="button" className="ghost-button" onClick={() => handleRemoteReview("evaluation")}>
                            Rodar evaluation
                          </button>
                          <button type="button" className="primary-button" onClick={() => handleRemoteReview("comparison")}>
                            Rodar comparison
                          </button>
                        </div>
                      </div>

                      <div className="provider-grid">
                        {remoteArtifacts.map((item) => (
                          <article key={item.id} className="provider-card">
                            <strong>{item.name}</strong>
                            <span>{item.format}</span>
                            <p>{compactText(item.storage_uri, 96)}</p>
                            <div className="composer-actions">
                              <button type="button" className="ghost-button" onClick={() => handleRemoteArtifactAction(item.id, "merge")}>
                                Merge
                              </button>
                              <button type="button" className="primary-button" onClick={() => handleRemoteArtifactAction(item.id, "promote")}>
                                Promote
                              </button>
                            </div>
                          </article>
                        ))}
                      </div>

                      <div className="compare-grid">
                        <article className="result-panel">
                          <h4>Evaluations</h4>
                          <pre className="preview-text compact">
                            {remoteEvaluations.length
                              ? JSON.stringify(
                                  remoteEvaluations.slice(0, 3).map((item) => ({
                                    suite: item.suite_name,
                                    status: item.status,
                                    scores: item.summary_scores
                                  })),
                                  null,
                                  2
                                )
                              : "Sem evaluation runs ainda."}
                          </pre>
                        </article>
                        <article className="result-panel">
                          <h4>Comparisons</h4>
                          <pre className="preview-text compact">
                            {remoteComparisons.length
                              ? JSON.stringify(
                                  remoteComparisons.slice(0, 3).map((item) => ({
                                    prompt_set_name: item.prompt_set_name,
                                    status: item.status,
                                    scores: item.summary_scores
                                  })),
                                  null,
                                  2
                                )
                              : "Sem comparison runs ainda."}
                          </pre>
                        </article>
                      </div>
                    </div>
                  </div>
                </section>
              </div>
            )}

            {view === "assistant" && (
              <div className="assistant-layout">
                <section className="panel session-list-panel">
                  <div className="panel-head">
                    <div>
                      <p className="eyebrow">Sessões</p>
                      <h3>Histórico pesquisável</h3>
                    </div>
                    <button
                      type="button"
                      className="ghost-button"
                      onClick={openSessionSetup}
                    >
                      Nova sessão
                    </button>
                  </div>
                  {showSessionSetup && (
                    <div className="session-setup-card">
                      <p className="eyebrow">Setup rápido</p>
                      <label className="full-label">
                        Objetivo obrigatório
                        <textarea
                          value={sessionSetup.objective}
                          onChange={(event) => setSessionSetup((current) => ({ ...current, objective: event.target.value }))}
                          placeholder="Ex.: pesquisar fontes locais sobre uma investigação OSINT e manter hipóteses rastreáveis."
                        />
                      </label>
                      <label className="full-label">
                        Preset operacional
                        <select
                          value={sessionSetup.preset}
                          onChange={(event) => {
                            const next = defaultSessionProfile(event.target.value as SessionProfile["preset"]);
                            setSessionSetup((current) => ({ ...next, objective: current.objective }));
                          }}
                        >
                          {presetOptions.map((preset) => (
                            <option key={preset.value} value={preset.value}>
                              {preset.label} · {preset.helper}
                            </option>
                          ))}
                        </select>
                      </label>
                      <div className="quick-toggle-grid">
                        <label className="toggle">
                          <input
                            type="checkbox"
                            checked={Boolean(sessionSetup.rag_policy.enabled)}
                            onChange={(event) =>
                              setSessionSetup((current) => ({ ...current, rag_policy: { ...current.rag_policy, enabled: event.target.checked } }))
                            }
                          />
                          <span>usar RAG</span>
                        </label>
                        <label className="toggle">
                          <input
                            type="checkbox"
                            checked={Boolean(sessionSetup.rag_policy.include_workspace)}
                            onChange={(event) =>
                              setSessionSetup((current) => ({
                                ...current,
                                rag_policy: { ...current.rag_policy, include_workspace: event.target.checked }
                              }))
                            }
                          />
                          <span>usar Workspace</span>
                        </label>
                        <label className="toggle">
                          <input
                            type="checkbox"
                            checked={Boolean(sessionSetup.memory_policy.auto_capture)}
                            onChange={(event) =>
                              setSessionSetup((current) => ({
                                ...current,
                                memory_policy: { ...current.memory_policy, auto_capture: event.target.checked }
                              }))
                            }
                          />
                          <span>capturar memórias</span>
                        </label>
                        <label className="toggle">
                          <input
                            type="checkbox"
                            checked={Boolean(sessionSetup.memory_policy.generate_training_candidates)}
                            onChange={(event) =>
                              setSessionSetup((current) => ({
                                ...current,
                                memory_policy: { ...current.memory_policy, generate_training_candidates: event.target.checked }
                              }))
                            }
                          />
                          <span>modo dataset</span>
                        </label>
                      </div>
                      <div className="composer-actions">
                        <button type="button" className="ghost-button" onClick={() => setShowSessionSetup(false)}>
                          Cancelar
                        </button>
                        <button type="button" className="primary-button" onClick={handleCreateSessionWithProfile}>
                          Iniciar chat
                        </button>
                      </div>
                    </div>
                  )}
                  <div className="session-list">
                    {sessions.map((session) => (
                      <button
                        key={session.id}
                        type="button"
                        className={selectedSessionId === session.id ? "session-card active" : "session-card"}
                        onClick={() => setSelectedSessionId(session.id)}
                      >
                        <strong>{session.title}</strong>
                        <span>{session.provider_id}/{session.model_name}</span>
                        <small>{formatDate(session.last_message_at || session.updated_at || session.created_at)}</small>
                      </button>
                    ))}
                  </div>
                </section>

                <section className="panel chat-panel">
                  <div className="panel-head">
                    <div>
                      <p className="eyebrow">Conversation</p>
                      <h3>Assistant Workspace</h3>
                    </div>
                    <label className="toggle">
                      <input type="checkbox" checked={chatMockMode} onChange={(event) => setChatMockMode(event.target.checked)} />
                      <span>modo mock seguro</span>
                    </label>
                  </div>

                  <div className="messages">
                    {messages.length === 0 ? (
                      <div className="empty-state">
                        <h4>Nenhuma mensagem ainda.</h4>
                        <p>Comece uma sessão e o resumo operacional será mantido separado do transcript bruto.</p>
                      </div>
                    ) : (
                      messages.map((message) => (
                        <article key={message.id} className={`message-bubble ${message.role}`}>
                          <header>
                            <strong>{message.role === "user" ? "Você" : "Orquestra"}</strong>
                            <span>{formatDate(message.created_at)}</span>
                          </header>
                          <p>{message.content}</p>
                          {(message.provider_id || message.model_name) && (
                            <footer>
                              <span>{message.provider_id}</span>
                              <span>{message.model_name}</span>
                              {typeof message.latency_seconds === "number" && <span>{message.latency_seconds.toFixed(2)}s</span>}
                            </footer>
                          )}
                        </article>
                      ))
                    )}
                  </div>

                  <div className="composer-shell">
                    <textarea
                      value={chatPrompt}
                      onChange={(event) => setChatPrompt(event.target.value)}
                      placeholder="Pergunte sobre decisões, próxima etapa, estrutura do projeto, arquivos relevantes ou compare estratégias."
                    />
                    <div className="composer-actions">
                      <button type="button" className="ghost-button" onClick={handleResumeSession} disabled={!selectedSessionId}>
                        Atualizar resume
                      </button>
                      <button type="button" className="primary-button" onClick={handleSendChat} disabled={chatStreaming}>
                        {chatStreaming ? "Respondendo..." : "Enviar"}
                      </button>
                    </div>
                  </div>
                </section>

                <section className="panel memory-rag-panel">
                  <div className="panel-head">
                    <div>
                      <p className="eyebrow">Memória & RAG</p>
                      <h3>Painel lateral da sessão</h3>
                    </div>
                    <button type="button" className="ghost-button" onClick={handleSaveSessionProfile} disabled={!sessionProfile || profileSaving}>
                      {profileSaving ? "Salvando..." : "Salvar"}
                    </button>
                  </div>

                  {sessionProfile ? (
                    <>
                      <div className="form-stack tight">
                        <label className="full-label">
                          Objetivo
                          <textarea
                            value={sessionProfile.objective}
                            onChange={(event) => updateDraftProfile((current) => ({ ...current, objective: event.target.value }))}
                          />
                        </label>
                        <label className="full-label">
                          Preset
                          <select
                            value={sessionProfile.preset}
                            onChange={(event) => {
                              const next = defaultSessionProfile(event.target.value as SessionProfile["preset"]);
                              updateDraftProfile((current) => ({ ...next, objective: current.objective }));
                            }}
                          >
                            {presetOptions.map((preset) => (
                              <option key={preset.value} value={preset.value}>
                                {preset.label}
                              </option>
                            ))}
                          </select>
                        </label>
                      </div>

                      <div className="quick-toggle-grid">
                        <label className="toggle">
                          <input
                            type="checkbox"
                            checked={Boolean(sessionProfile.memory_policy.enabled)}
                            onChange={(event) =>
                              updateDraftProfile((current) => ({
                                ...current,
                                memory_policy: { ...current.memory_policy, enabled: event.target.checked }
                              }))
                            }
                          />
                          <span>memória no prompt</span>
                        </label>
                        <label className="toggle">
                          <input
                            type="checkbox"
                            checked={Boolean(sessionProfile.rag_policy.enabled)}
                            onChange={(event) =>
                              updateDraftProfile((current) => ({
                                ...current,
                                rag_policy: { ...current.rag_policy, enabled: event.target.checked }
                              }))
                            }
                          />
                          <span>RAG ativo</span>
                        </label>
                        <label className="toggle">
                          <input
                            type="checkbox"
                            checked={Boolean(sessionProfile.rag_policy.include_workspace)}
                            onChange={(event) =>
                              updateDraftProfile((current) => ({
                                ...current,
                                rag_policy: { ...current.rag_policy, include_workspace: event.target.checked }
                              }))
                            }
                          />
                          <span>Workspace</span>
                        </label>
                        <label className="toggle">
                          <input
                            type="checkbox"
                            checked={Boolean(sessionProfile.memory_policy.generate_training_candidates)}
                            onChange={(event) =>
                              updateDraftProfile((current) => ({
                                ...current,
                                memory_policy: { ...current.memory_policy, generate_training_candidates: event.target.checked }
                              }))
                            }
                          />
                          <span>dataset após aprovação</span>
                        </label>
                      </div>

                      <div className="memory-telemetry">
                        <article>
                          <span>Último recall</span>
                          <strong>{lastMemoryTelemetry.recallCount}</strong>
                        </article>
                        <article>
                          <span>Inbox criada</span>
                          <strong>{lastMemoryTelemetry.candidatesCreated}</strong>
                        </article>
                        <article>
                          <span>Compactação</span>
                          <strong>{sessionCompaction?.compacted_message_count ?? 0}</strong>
                        </article>
                      </div>

                      <div className="token-list">
                        {(sessionProfile.rag_policy.collections ?? []).map((collection) => (
                          <span key={collection}>{collection}</span>
                        ))}
                        <span>{sessionProfile.rag_policy.memory_collection || "orquestra_memory_v1"}</span>
                        {selectedInvestigationId ? <span>investigation:{selectedInvestigationId.slice(0, 8)}</span> : null}
                      </div>

                      {(sessionProfile.preset === "osint" || selectedInvestigation) && (
                        <article className="memory-card candidate-card">
                          <strong>{selectedInvestigation?.title || "Investigação OSINT não vinculada"}</strong>
                          <span>{selectedInvestigation?.status || "sem investigação"} · {selectedInvestigation?.mode || "balanced"}</span>
                          <p>{selectedInvestigation?.objective || "Use o OSINT Lab para ligar a sessão a uma investigação, fontes e claims aprovadas."}</p>
                          <div className="context-list">
                            <span><strong>Evidências:</strong> {osintEvidence.length}</span>
                            <span><strong>Claims:</strong> {osintClaims.length}</span>
                            <span><strong>Fontes recentes:</strong> {osintSources.length}</span>
                          </div>
                          <div className="composer-actions">
                            <button type="button" className="ghost-button" onClick={() => setView("osint")}>
                              Abrir OSINT Lab
                            </button>
                            <button type="button" className="ghost-button" onClick={handleSearchOsint} disabled={!selectedInvestigationId}>
                              Buscar web
                            </button>
                          </div>
                        </article>
                      )}

                      <div className="composer-actions">
                        <button type="button" className="ghost-button" onClick={handleCompactSession} disabled={!selectedSessionId}>
                          Compactar contexto
                        </button>
                        <button type="button" className="ghost-button" onClick={handleRebuildPlanner} disabled={!selectedSessionId}>
                          Rebuild planner
                        </button>
                        <button type="button" className="ghost-button" onClick={handleAddNextTask} disabled={!selectedSessionId || !chatPrompt.trim()}>
                          Virar tarefa
                        </button>
                      </div>

                      <div className="context-list">
                        <span><strong>Summary version:</strong> {sessionCompaction?.summary_version ?? 0}</span>
                        <span><strong>Recent tail:</strong> {sessionCompaction?.preserved_recent_turns ?? 0} turns</span>
                        <span><strong>Planner:</strong> {plannerSnapshot?.next_steps.length ?? 0} próximos passos</span>
                      </div>

                      <div className="memory-inbox">
                        <div className="panel-head slim">
                          <div>
                            <p className="eyebrow">Planner</p>
                            <h3>{sessionTasks.length} tarefas</h3>
                          </div>
                        </div>
                        <article className="memory-card candidate-card">
                          <strong>{plannerSnapshot?.objective || sessionProfile?.objective || "Objetivo não definido"}</strong>
                          <span>{plannerSnapshot?.strategy || "Estratégia ainda não consolidada."}</span>
                          <p>{plannerSnapshot?.metadata?.source ? `Fonte: ${String(plannerSnapshot.metadata.source)}` : "Snapshot operacional do planner."}</p>
                          <div className="context-list">
                            <span><strong>Próximos passos:</strong> {plannerSnapshot?.next_steps.length ?? 0}</span>
                            <span><strong>Riscos:</strong> {plannerSnapshot?.risks.length ?? 0}</span>
                            <span><strong>Último rebuild:</strong> {plannerSnapshot?.last_planned_at ? formatDate(plannerSnapshot.last_planned_at) : "nunca"}</span>
                          </div>
                          <div className="token-list">
                            {(plannerSnapshot?.next_steps ?? []).map((step) => (
                              <span key={step}>{step}</span>
                            ))}
                          </div>
                          {(plannerSnapshot?.risks ?? []).length > 0 ? (
                            <div className="context-list">
                              {(plannerSnapshot?.risks ?? []).map((risk) => (
                                <span key={risk}><strong>Risco:</strong> {risk}</span>
                              ))}
                            </div>
                          ) : null}
                        </article>
                        {sessionTasks.length === 0 ? (
                          <div className="empty-state compact">
                            <h4>Planner vazio.</h4>
                            <p>Reconstrua o planner para sincronizar objetivo, resumo e próximos passos.</p>
                          </div>
                        ) : (
                          sessionTasks.map((task) => (
                            <article key={task.id} className="memory-card candidate-card">
                              <strong>{task.subject}</strong>
                              <span>{task.status} · {task.owner}</span>
                              <p>{task.active_form || task.description}</p>
                              <div className="context-list">
                                <span>
                                  <strong>Bloqueada por:</strong>{" "}
                                  {task.blocked_by.length
                                    ? task.blocked_by.map((item) => sessionTaskMap.get(item)?.subject || item.slice(0, 8)).join(" • ")
                                    : "ninguém"}
                                </span>
                                <span>
                                  <strong>Bloqueia:</strong>{" "}
                                  {task.blocks.length
                                    ? task.blocks.map((item) => sessionTaskMap.get(item)?.subject || item.slice(0, 8)).join(" • ")
                                    : "ninguém"}
                                </span>
                              </div>
                              <div className="split-form">
                                <label>
                                  Bloqueada por
                                  <select
                                    value={taskRelationDrafts[task.id]?.blockedBy ?? ""}
                                    onChange={(event) => handleTaskRelationDraft(task.id, "blockedBy", event.target.value)}
                                  >
                                    <option value="">Selecione</option>
                                    {sessionTasks
                                      .filter((candidate) => candidate.id !== task.id)
                                      .map((candidate) => (
                                        <option key={candidate.id} value={candidate.id}>
                                          {candidate.subject}
                                        </option>
                                      ))}
                                  </select>
                                </label>
                                <label>
                                  Bloqueia
                                  <select
                                    value={taskRelationDrafts[task.id]?.blocks ?? ""}
                                    onChange={(event) => handleTaskRelationDraft(task.id, "blocks", event.target.value)}
                                  >
                                    <option value="">Selecione</option>
                                    {sessionTasks
                                      .filter((candidate) => candidate.id !== task.id)
                                      .map((candidate) => (
                                        <option key={candidate.id} value={candidate.id}>
                                          {candidate.subject}
                                        </option>
                                      ))}
                                  </select>
                                </label>
                              </div>
                              <div className="composer-actions">
                                <button type="button" className="ghost-button" onClick={() => handleTaskRelation(task, "blocked_by")}>
                                  Salvar bloqueio
                                </button>
                                <button type="button" className="ghost-button" onClick={() => handleTaskRelation(task, "blocks")}>
                                  Salvar dependente
                                </button>
                                <button type="button" className="ghost-button" onClick={() => handleTaskStatus(task, "blocked")}>
                                  Bloquear
                                </button>
                                <button type="button" className="ghost-button" onClick={() => handleTaskStatus(task, "in_progress")}>
                                  Em curso
                                </button>
                                <button type="button" className="primary-button" onClick={() => handleTaskStatus(task, "completed")}>
                                  Concluir
                                </button>
                                <button type="button" className="ghost-button" onClick={() => handleStartTaskWorkflow(task)}>
                                  Rodar workflow
                                </button>
                              </div>
                            </article>
                          ))
                        )}
                      </div>

                      <div className="memory-inbox">
                        <div className="panel-head slim">
                          <div>
                            <p className="eyebrow">Memory Inbox</p>
                            <h3>{memoryCandidates.length} pendentes</h3>
                          </div>
                        </div>
                        {memoryCandidates.length === 0 ? (
                          <div className="empty-state compact">
                            <h4>Sem candidatos pendentes.</h4>
                            <p>Novas interações sugerem memórias aqui sem promover nada automaticamente.</p>
                          </div>
                        ) : (
                          memoryCandidates.map((candidate) => (
                            <article key={candidate.id} className="memory-card candidate-card">
                              <strong>{candidate.title}</strong>
                              <span>{candidate.scope} · confiança {candidate.confidence.toFixed(2)}</span>
                              <p>{compactText(candidate.content, 240)}</p>
                              <div className="composer-actions">
                                <button type="button" className="ghost-button" onClick={() => handleReviewMemoryCandidate(candidate, "reject")}>
                                  Rejeitar
                                </button>
                                <button type="button" className="primary-button" onClick={() => handleReviewMemoryCandidate(candidate, "approve")}>
                                  Aprovar
                                </button>
                              </div>
                            </article>
                          ))
                        )}
                      </div>
                    </>
                  ) : (
                    <div className="empty-state">
                      <h4>Nenhuma sessão selecionada.</h4>
                      <p>Crie uma sessão para configurar objetivo, preset, política de memória e ligação com RAG.</p>
                    </div>
                  )}
                </section>
              </div>
            )}

            {view === "osint" && (
              <div className="workspace-layout">
                <section className="panel attach-panel">
                  <div className="panel-head">
                    <div>
                      <p className="eyebrow">OSINT Control Plane</p>
                      <h3>Investigação, políticas e configuração nativa</h3>
                    </div>
                    <div className="composer-actions">
                      <button type="button" className="ghost-button" onClick={handleSaveOsintConfig} disabled={!osintConfig}>
                        Salvar config
                      </button>
                      <button type="button" className="primary-button" onClick={handleCreateOsintInvestigation}>
                        Nova investigação
                      </button>
                    </div>
                  </div>

                  {osintConfig ? (
                    <div className="split-form">
                      <label>
                        Search timeout
                        <input
                          type="number"
                          value={osintConfig.search_timeout_seconds}
                          onChange={(event) =>
                            setOsintConfig((current) => (current ? { ...current, search_timeout_seconds: Number(event.target.value || 0) } : current))
                          }
                        />
                      </label>
                      <label>
                        Fetch timeout
                        <input
                          type="number"
                          value={osintConfig.fetch_timeout_seconds}
                          onChange={(event) =>
                            setOsintConfig((current) => (current ? { ...current, fetch_timeout_seconds: Number(event.target.value || 0) } : current))
                          }
                        />
                      </label>
                      <label>
                        Max resultados
                        <input
                          type="number"
                          value={osintConfig.default_max_results}
                          onChange={(event) =>
                            setOsintConfig((current) => (current ? { ...current, default_max_results: Number(event.target.value || 0) } : current))
                          }
                        />
                      </label>
                      <label>
                        Fetch limit
                        <input
                          type="number"
                          value={osintConfig.default_fetch_limit}
                          onChange={(event) =>
                            setOsintConfig((current) => (current ? { ...current, default_fetch_limit: Number(event.target.value || 0) } : current))
                          }
                        />
                      </label>
                      <label className="full-label">
                        Tor proxy
                        <input
                          value={osintConfig.tor_proxy_url}
                          onChange={(event) =>
                            setOsintConfig((current) => (current ? { ...current, tor_proxy_url: event.target.value } : current))
                          }
                        />
                      </label>
                    </div>
                  ) : null}

                  <div className="form-stack">
                    <input
                      value={osintInvestigationForm.title}
                      onChange={(event) => setOsintInvestigationForm((current) => ({ ...current, title: event.target.value }))}
                      placeholder="Título da investigação"
                    />
                    <textarea
                      value={osintInvestigationForm.objective}
                      onChange={(event) => setOsintInvestigationForm((current) => ({ ...current, objective: event.target.value }))}
                      placeholder="Objetivo investigativo"
                    />
                    <div className="split-form">
                      <label>
                        Entidade-alvo
                        <input
                          value={osintInvestigationForm.target_entity}
                          onChange={(event) => setOsintInvestigationForm((current) => ({ ...current, target_entity: event.target.value }))}
                        />
                      </label>
                      <label>
                        Idioma
                        <input value={osintInvestigationForm.language} onChange={(event) => setOsintInvestigationForm((current) => ({ ...current, language: event.target.value }))} />
                      </label>
                      <label>
                        Jurisdição
                        <input value={osintInvestigationForm.jurisdiction} onChange={(event) => setOsintInvestigationForm((current) => ({ ...current, jurisdiction: event.target.value }))} />
                      </label>
                      <label>
                        Modo
                        <input value={osintInvestigationForm.mode} onChange={(event) => setOsintInvestigationForm((current) => ({ ...current, mode: event.target.value }))} />
                      </label>
                    </div>
                  </div>

                  <div className="scan-grid">
                    {osintInvestigations.map((investigation) => (
                      <button
                        key={investigation.id}
                        type="button"
                        className={selectedInvestigationId === investigation.id ? "scan-card active" : "scan-card"}
                        onClick={() => setSelectedInvestigationId(investigation.id)}
                      >
                        <strong>{investigation.title}</strong>
                        <span>{investigation.status} · {investigation.mode}</span>
                        <small>{compactText(investigation.objective, 96)}</small>
                      </button>
                    ))}
                  </div>
                </section>

                <section className="panel workspace-panel">
                  <div className="panel-head">
                    <div>
                      <p className="eyebrow">Search Console</p>
                      <h3>Busca web, fetch e evidência rastreável</h3>
                    </div>
                    <div className="composer-actions">
                      <button type="button" className="ghost-button" onClick={handlePlanOsint} disabled={!selectedInvestigationId}>
                        Planejar queries
                      </button>
                      <button type="button" className="primary-button" onClick={handleSearchOsint} disabled={!selectedInvestigationId}>
                        Buscar web
                      </button>
                    </div>
                  </div>

                  <div className="form-stack">
                    <textarea value={osintSearchQuery} onChange={(event) => setOsintSearchQuery(event.target.value)} placeholder="Consulta OSINT, aliases, site: e filtros." />
                    <div className="composer-actions">
                      <input
                        value={osintFetchUrl}
                        onChange={(event) => setOsintFetchUrl(event.target.value)}
                        placeholder="URL opcional para fetch direto"
                      />
                      <button type="button" className="ghost-button" onClick={() => handleFetchOsint(undefined, osintFetchUrl)} disabled={!selectedInvestigationId}>
                        Fetch direto
                      </button>
                      <button type="button" className="ghost-button" onClick={handleExportOsintDataset} disabled={!selectedInvestigationId}>
                        Exportar dataset
                      </button>
                    </div>
                    {(osintPlanQueries ?? []).length > 0 ? (
                      <div className="token-list">
                        {osintPlanQueries.map((item) => (
                          <span key={item}>{item}</span>
                        ))}
                      </div>
                    ) : null}
                  </div>

                  <div className="provider-grid">
                    {osintConnectors.map((connector) => {
                      const investigationEnabled = selectedInvestigation?.enabled_connector_ids?.includes(connector.connector_id) ?? false;
                      return (
                        <article key={connector.connector_id} className="provider-card">
                          <strong>{connector.label}</strong>
                          <span>{connector.status}</span>
                          <p>{connector.description}</p>
                          <div className="token-list">
                            <span>{connector.category}</span>
                            <span>{connector.credential_status}</span>
                            <span>{connector.health_status}</span>
                          </div>
                          <div className="composer-actions">
                            <button type="button" className="ghost-button" onClick={() => handleToggleOsintConnector(connector)}>
                              {connector.enabled_global ? "Desligar global" : "Ligar global"}
                            </button>
                            <button type="button" className="ghost-button" onClick={() => handleInvestigationConnectorToggle(connector.connector_id)} disabled={!selectedInvestigation}>
                              {investigationEnabled ? "Remover da investigação" : "Usar na investigação"}
                            </button>
                          </div>
                        </article>
                      );
                    })}
                  </div>

                  <div className="memory-grid dense">
                    <div className="memory-column">
                      <h4>Fontes recentes</h4>
                      {osintSources.length === 0 ? (
                        <div className="empty-state compact">
                          <h4>Sem resultados recentes.</h4>
                          <p>Planeje uma query e rode a busca para preencher as fontes.</p>
                        </div>
                      ) : (
                        osintSources.map((source) => (
                          <article key={source.id} className="memory-card">
                            <strong>{source.title}</strong>
                            <span>{source.connector_id} · rank {source.rank + 1}</span>
                            <p>{compactText(source.snippet || source.url, 220)}</p>
                            <div className="composer-actions">
                              <button type="button" className="ghost-button" onClick={() => handleFetchOsint(source.id)}>
                                Fetch
                              </button>
                              <button type="button" className="ghost-button" onClick={() => window.open(source.url, "_blank")}>
                                Abrir
                              </button>
                            </div>
                          </article>
                        ))
                      )}
                    </div>
                    <div className="memory-column">
                      <h4>Evidências</h4>
                      {osintEvidence.length === 0 ? (
                        <div className="empty-state compact">
                          <h4>Nenhuma evidência ainda.</h4>
                          <p>As capturas normalizadas e os trechos relevantes aparecem aqui.</p>
                        </div>
                      ) : (
                        osintEvidence.map((evidence) => (
                          <article key={evidence.id} className="memory-card candidate-card">
                            <strong>{evidence.title}</strong>
                            <span>{evidence.validation_status} · quality {evidence.source_quality.toFixed(2)}</span>
                            <p>{compactText(evidence.content, 220)}</p>
                            <div className="composer-actions">
                              <button type="button" className="primary-button" onClick={() => handleApproveEvidence(evidence.id)}>
                                Aprovar evidência
                              </button>
                            </div>
                          </article>
                        ))
                      )}
                    </div>
                  </div>

                  <div className="memory-grid dense">
                    <div className="memory-column">
                      <h4>Claims</h4>
                      {osintClaims.map((claim) => (
                        <article key={claim.id} className="memory-card candidate-card">
                          <strong>{claim.title}</strong>
                          <span>{claim.status} · confiança {claim.confidence.toFixed(2)}</span>
                          <p>{compactText(claim.content, 220)}</p>
                          <div className="composer-actions">
                            <button type="button" className="primary-button" onClick={() => handleApproveClaim(claim.id)}>
                              Aprovar claim
                            </button>
                          </div>
                        </article>
                      ))}
                    </div>
                    <div className="memory-column">
                      <h4>Source Registry</h4>
                      <div className="form-stack">
                        <input value={osintRegistryForm.source_key} onChange={(event) => setOsintRegistryForm((current) => ({ ...current, source_key: event.target.value }))} />
                        <input value={osintRegistryForm.title} onChange={(event) => setOsintRegistryForm((current) => ({ ...current, title: event.target.value }))} />
                        <input value={osintRegistryForm.base_url} onChange={(event) => setOsintRegistryForm((current) => ({ ...current, base_url: event.target.value }))} />
                        <textarea value={osintRegistryForm.description} onChange={(event) => setOsintRegistryForm((current) => ({ ...current, description: event.target.value }))} />
                        <div className="composer-actions">
                          <button type="button" className="ghost-button" onClick={handleCreateOsintRegistryEntry}>
                            Adicionar seed
                          </button>
                        </div>
                      </div>
                      <div className="run-grid">
                        {osintRegistry.slice(0, 12).map((entry) => (
                          <button key={entry.id} type="button" className="job-row">
                            <strong>{entry.title}</strong>
                            <span>{entry.connector_id || entry.category}</span>
                            <small>{compactText(entry.base_url, 68)}</small>
                          </button>
                        ))}
                      </div>
                      <pre className="preview-text compact">
                        {JSON.stringify(
                          {
                            selected_investigation: selectedInvestigation
                              ? {
                                  id: selectedInvestigation.id,
                                  connectors: selectedInvestigation.enabled_connector_ids,
                                  source_registry_ids: selectedInvestigation.source_registry_ids
                                }
                              : null,
                            recent_runs: osintRuns.slice(0, 5).map((run) => ({
                              kind: run.run_kind,
                              status: run.status,
                              query: run.query,
                              created_at: run.created_at
                            }))
                          },
                          null,
                          2
                        )}
                      </pre>
                    </div>
                  </div>
                </section>
              </div>
            )}

            {view === "workspace" && (
              <div className="workspace-layout">
                <section className="panel attach-panel">
                  <div className="panel-head">
                    <div>
                      <p className="eyebrow">Attach Directory</p>
                      <h3>Workspace Multimodal</h3>
                    </div>
                    <label className="toggle">
                      <input type="checkbox" checked={workspaceMockMode} onChange={(event) => setWorkspaceMockMode(event.target.checked)} />
                      <span>query em mock seguro</span>
                    </label>
                  </div>

                  <div className="form-stack">
                    <input
                      value={workspaceRootPath}
                      onChange={(event) => setWorkspaceRootPath(event.target.value)}
                      placeholder="/Users/roberto/alguma-pasta"
                    />
                    <textarea
                      value={workspacePromptHint}
                      onChange={(event) => setWorkspacePromptHint(event.target.value)}
                      placeholder="Orientação para o scan"
                    />
                    <div className="composer-actions">
                      <button type="button" className="primary-button" onClick={handleAttachDirectory}>
                        Anexar diretório
                      </button>
                    </div>
                  </div>

                  <div className="scan-grid">
                    {workspaceScans.map((scan) => (
                      <button
                        key={scan.id}
                        type="button"
                        className={selectedScanId === scan.id ? "scan-card active" : "scan-card"}
                        onClick={() => setSelectedScanId(scan.id)}
                      >
                        <strong>{scan.root_path}</strong>
                        <span>{scan.total_assets} ativos</span>
                        <small>{formatBytes(scan.total_bytes)}</small>
                      </button>
                    ))}
                  </div>
                </section>

                <section className="panel workspace-panel">
                  <div className="panel-head">
                    <div>
                      <p className="eyebrow">Query over inventory</p>
                      <h3>Leitura lazy orientada por prompt</h3>
                    </div>
                  </div>

                  <div className="form-stack">
                    <textarea
                      value={workspacePrompt}
                      onChange={(event) => setWorkspacePrompt(event.target.value)}
                      placeholder="Pergunte pelo conteúdo do diretório anexado."
                    />
                    <div className="composer-actions">
                      <button type="button" className="ghost-button" onClick={handleExtractAsset} disabled={!selectedAssetId}>
                        Extrair asset atual
                      </button>
                      <button type="button" className="primary-button" onClick={handleWorkspaceQuery} disabled={!selectedScanId}>
                        Consultar workspace
                      </button>
                    </div>
                  </div>

                  <div className="asset-layout">
                    <div className="asset-list">
                      {workspaceAssets.map((asset) => (
                        <button
                          key={asset.id}
                          type="button"
                          className={selectedAssetId === asset.id ? "asset-row active" : "asset-row"}
                          onClick={() => setSelectedAssetId(asset.id)}
                        >
                          <strong>{asset.relative_path}</strong>
                          <span>{asset.asset_kind}</span>
                          <small>{formatBytes(asset.size_bytes)}</small>
                        </button>
                      ))}
                    </div>

                    <div className="preview-panel">
                      {selectedAsset ? (
                        <>
                          <div className="preview-header">
                            <div>
                              <h4>{selectedAsset.relative_path}</h4>
                              <span>{selectedAsset.asset_kind} • {selectedAsset.mime_type || selectedAsset.extension || "sem mime"}</span>
                            </div>
                            <div className="composer-actions">
                              <button type="button" className="ghost-button" onClick={handleOpenAsset}>
                                Abrir
                              </button>
                              <button type="button" className="ghost-button" onClick={handleMemorizeAsset}>
                                Memorizar
                              </button>
                            </div>
                          </div>

                          {selectedAsset.asset_kind === "image" && (
                            <img className="image-preview" src={rawPreviewUrl(selectedAsset.id)} alt={selectedAsset.title} />
                          )}
                          {selectedAsset.asset_kind === "pdf" && (
                            <iframe className="file-frame" src={rawPreviewUrl(selectedAsset.id)} title={selectedAsset.relative_path} />
                          )}
                          {selectedAsset.asset_kind === "audio" && (
                            <audio className="media-player" controls src={rawPreviewUrl(selectedAsset.id)} />
                          )}
                          {selectedAsset.asset_kind === "video" && (
                            <video className="media-player" controls src={rawPreviewUrl(selectedAsset.id)} />
                          )}
                          {!["image", "pdf", "audio", "video"].includes(selectedAsset.asset_kind) && (
                            <pre className="preview-text">
                              {assetPreview?.preview_text || selectedAsset.summary_excerpt || "Sem preview textual disponível."}
                            </pre>
                          )}

                          {assetPreview?.derivatives?.length ? (
                            <div className="token-list">
                              {assetPreview.derivatives.map((derivative) => (
                                <span key={derivative.id}>{derivative.derivative_kind}</span>
                              ))}
                            </div>
                          ) : null}
                        </>
                      ) : (
                        <div className="empty-state">
                          <h4>Selecione um ativo.</h4>
                          <p>O preview interno muda conforme o tipo do arquivo e os derivados disponíveis.</p>
                        </div>
                      )}
                    </div>
                  </div>

                  {workspaceResult && (
                    <article className="result-panel">
                      <header>
                        <strong>{workspaceResult.provider_id}/{workspaceResult.model_name}</strong>
                        <span>{workspaceResult.latency_seconds.toFixed(2)}s</span>
                      </header>
                      <p>{workspaceResult.answer}</p>
                      <div className="result-assets">
                        {workspaceResult.assets.map((asset) => (
                          <div key={asset.asset_id} className="result-asset">
                            <strong>{asset.relative_path}</strong>
                            <span>{asset.asset_kind}</span>
                            <small>score {asset.score.toFixed(2)}</small>
                          </div>
                        ))}
                      </div>
                    </article>
                  )}
                </section>
              </div>
            )}

            {view === "settings" && (
              <div className="stage-grid">
                <section className="panel">
                  <div className="panel-head">
                    <div>
                      <p className="eyebrow">Runtime & Storage</p>
                      <h3>Processing Hub e Storage Fabric</h3>
                    </div>
                    <button type="button" className="ghost-button" onClick={handleSaveRuntimeConfig}>
                      Gravar runtime.json
                    </button>
                  </div>
                  <div className="metric-grid">
                    <article className="provider-card">
                      <strong>Runtime</strong>
                      <span>{String(runtimeSettings?.runtime?.runtime_dir || health?.runtime.runtime_dir || "-")}</span>
                      <p>{String(runtimeSettings?.runtime?.data_root || health?.runtime.data_root || "-")}</p>
                    </article>
                    <article className="provider-card">
                      <strong>Política</strong>
                      <span>hub local obrigatório</span>
                      <p>SQLite/RAG ativos ficam em local_path, external_drive ou cloud_mounted confiável.</p>
                    </article>
                    <article className="provider-card">
                      <strong>Remoto frio</strong>
                      <span>S3/SFTP/archive</span>
                      <p>Usado para backups, exports, datasets, evidências frias e modelos grandes.</p>
                    </article>
                  </div>

                  <div className="split-form">
                    <label>
                      Nome do local
                      <input value={storageLocationForm.label} onChange={(event) => setStorageLocationForm((current) => ({ ...current, label: event.target.value }))} />
                    </label>
                    <label>
                      Backend
                      <select value={storageLocationForm.backend} onChange={(event) => setStorageLocationForm((current) => ({ ...current, backend: event.target.value }))}>
                        <option value="local_path">local_path</option>
                        <option value="external_drive">external_drive</option>
                        <option value="cloud_mounted">cloud_mounted</option>
                        <option value="s3_compatible">s3_compatible frio</option>
                        <option value="sftp">sftp frio</option>
                        <option value="readonly_archive">readonly_archive</option>
                      </select>
                    </label>
                    <label>
                      Base URI
                      <input value={storageLocationForm.base_uri} onChange={(event) => setStorageLocationForm((current) => ({ ...current, base_uri: event.target.value }))} />
                    </label>
                    <label>
                      Quota bytes
                      <input value={storageLocationForm.quota_bytes} onChange={(event) => setStorageLocationForm((current) => ({ ...current, quota_bytes: event.target.value }))} />
                    </label>
                  </div>
                  <button type="button" className="primary-button" onClick={handleCreateStorageLocation}>
                    Adicionar local
                  </button>

                  <div className="provider-grid">
                    {storageLocations.map((location) => (
                      <article key={location.id} className="provider-card">
                        <strong>{location.label}</strong>
                        <span>{location.backend} · {location.health_status}</span>
                        <p>{location.base_uri}</p>
                        <small>quota {location.quota_bytes ? formatBytes(location.quota_bytes) : "sem limite definido"}</small>
                      </article>
                    ))}
                  </div>
                </section>

                <section className="panel two-column-panel">
                  <div>
                    <div className="panel-head slim">
                      <div>
                        <p className="eyebrow">Assignments</p>
                        <h3>Domínios de dados</h3>
                      </div>
                    </div>
                    <div className="stack-list">
                      {storageAssignments.map((assignment) => (
                        <article key={assignment.id} className="stack-row">
                          <strong>{assignment.domain}</strong>
                          <span>{assignment.mode} · {assignment.relative_path} · {assignment.location_id}</span>
                        </article>
                      ))}
                    </div>
                  </div>
                  <div>
                    <div className="panel-head slim">
                      <div>
                        <p className="eyebrow">Secrets & Providers</p>
                        <h3>Keychain sem revelar valores</h3>
                      </div>
                    </div>
                    <div className="form-stack">
                      <select value={secretForm.provider_id} onChange={(event) => setSecretForm((current) => ({ ...current, provider_id: event.target.value }))}>
                        {providers.map((provider) => (
                          <option key={provider.provider_id} value={provider.provider_id}>{provider.label}</option>
                        ))}
                      </select>
                      <input value={secretForm.label} onChange={(event) => setSecretForm((current) => ({ ...current, label: event.target.value }))} />
                      <input value={secretForm.secret_ref} onChange={(event) => setSecretForm((current) => ({ ...current, secret_ref: event.target.value }))} />
                      <input type="password" value={secretForm.value} onChange={(event) => setSecretForm((current) => ({ ...current, value: event.target.value }))} placeholder="Cole a chave; ela não será exibida depois" />
                      <button type="button" className="primary-button" onClick={handleCreateSecret}>Salvar no cofre</button>
                    </div>
                    <div className="token-list">
                      {secretMetadata.map((secret) => (
                        <span key={secret.id}>{secret.provider_id}: {secret.secret_ref} · {secret.storage_backend}</span>
                      ))}
                    </div>
                  </div>
                </section>

                <section className="panel two-column-panel">
                  <div>
                    <div className="panel-head slim">
                      <div>
                        <p className="eyebrow">Models & Router</p>
                        <h3>Decisão interna por tarefa</h3>
                      </div>
                      <button type="button" className="ghost-button" onClick={handleRefreshModelCatalog}>Atualizar modelos</button>
                    </div>
                    <div className="provider-grid">
                      {routePolicies.map((policy) => (
                        <article key={policy.id} className="provider-card">
                          <strong>{policy.label}</strong>
                          <span>{policy.mode} · {policy.task_type}</span>
                          <p>{policy.preferred_provider_id}/{policy.preferred_model_name || "default"}</p>
                        </article>
                      ))}
                    </div>
                    <button type="button" className="primary-button" onClick={handleSimulateRouter}>Simular router</button>
                    <pre className="preview-text compact">
                      {routerSimulation ? JSON.stringify(routerSimulation, null, 2) : "A decisão do router aparece aqui."}
                    </pre>
                  </div>
                  <div>
                    <div className="panel-head slim">
                      <div>
                        <p className="eyebrow">Agents</p>
                        <h3>Especialistas configuráveis</h3>
                      </div>
                    </div>
                    <div className="provider-grid">
                      {agentProfiles.map((agent) => (
                        <article key={agent.id} className="provider-card">
                          <strong>{agent.label}</strong>
                          <span>{agent.privacy_level} · {agent.enabled ? "ativo" : "inativo"}</span>
                          <p>{agent.description || `${agent.provider_id}/${agent.model_name}`}</p>
                        </article>
                      ))}
                    </div>
                  </div>
                </section>
              </div>
            )}

            {view === "projects" && (
              <section className="panel">
                <div className="panel-head">
                  <div>
                    <p className="eyebrow">Projects</p>
                    <h3>Perfis e defaults operacionais</h3>
                  </div>
                </div>
                <div className="split-form">
                  <label>
                    Slug
                    <input value={projectForm.slug} onChange={(event) => setProjectForm((current) => ({ ...current, slug: event.target.value }))} />
                  </label>
                  <label>
                    Nome
                    <input value={projectForm.name} onChange={(event) => setProjectForm((current) => ({ ...current, name: event.target.value }))} />
                  </label>
                </div>
                <label className="full-label">
                  Descrição
                  <textarea
                    value={projectForm.description}
                    onChange={(event) => setProjectForm((current) => ({ ...current, description: event.target.value }))}
                  />
                </label>
                <div className="split-form">
                  <label>
                    Provider default
                    <input
                      value={projectForm.default_provider_id}
                      onChange={(event) => setProjectForm((current) => ({ ...current, default_provider_id: event.target.value }))}
                    />
                  </label>
                  <label>
                    Modelo default
                    <input
                      value={projectForm.default_model}
                      onChange={(event) => setProjectForm((current) => ({ ...current, default_model: event.target.value }))}
                    />
                  </label>
                </div>
                <div className="composer-actions">
                  <button type="button" className="primary-button" onClick={handleCreateProject}>
                    Criar projeto
                  </button>
                </div>

                <div className="provider-grid">
                  {projects.map((project) => (
                    <article key={project.id} className="provider-card">
                      <strong>{project.name}</strong>
                      <span>{project.slug}</span>
                      <p>{project.description}</p>
                      <small>{project.default_provider_id}/{project.default_model}</small>
                    </article>
                  ))}
                </div>
              </section>
            )}
          </section>

          <aside className="context-rail">
            <section className="context-card">
              <p className="eyebrow">Working Memory</p>
              <h3>{selectedSessionId ? "Resumo ativo" : "Sem sessão ativa"}</h3>
              <p>{sessionSummary?.current_state || "O resumo aparece aqui assim que uma sessão vira contexto operacional."}</p>
              <div className="context-list">
                <span><strong>Arquivos:</strong> {shortList(sessionSummary?.relevant_files ?? [])}</span>
                <span><strong>Próximos passos:</strong> {plannerSnapshot?.next_steps.join(" • ") || sessionSummary?.next_steps || "Sem próximos passos ainda."}</span>
                <span><strong>Compactação:</strong> {sessionCompaction ? `${sessionCompaction.compacted_message_count} consolidadas / v${sessionCompaction.summary_version}` : "não iniciada"}</span>
                <span><strong>Perfil:</strong> {sessionProfile ? `${sessionProfile.preset_label || sessionProfile.preset} · ${sessionProfile.objective || "sem objetivo"}` : "não carregado"}</span>
              </div>
            </section>

            <section className="context-card">
              <p className="eyebrow">Transcript</p>
              <h3>{sessionTranscript?.message_count ?? 0} eventos</h3>
              <pre className="preview-text compact">
                {sessionTranscript?.entries?.slice(-6).map((item) => `${item.role}: ${item.content}`).join("\n\n") || "Sem transcript carregado."}
              </pre>
            </section>

            <section className="context-card">
              <p className="eyebrow">Execução operacional</p>
              <h3>{selectedRun?.label || "Nenhuma execução selecionada"}</h3>
              <div className="context-list">
                <span><strong>Status:</strong> {selectedRun?.status || "idle"}</span>
                <span><strong>Início:</strong> {formatDate(selectedRun?.started_at)}</span>
                <span><strong>Saída:</strong> {selectedRun?.exit_code ?? "-"}</span>
              </div>
              <pre className="preview-text compact terminal">
                {selectedRun?.log_tail || "Os logs das ações operacionais aparecem aqui."}
              </pre>
            </section>

            <section className="context-card">
              <p className="eyebrow">Workflow Run</p>
              <h3>{selectedWorkflow?.workflow_name || "Nenhum workflow selecionado"}</h3>
              <div className="context-list">
                <span><strong>Status:</strong> {selectedWorkflow?.status || "idle"}</span>
                <span><strong>Leitura operacional:</strong> {workflowStatusLabel(selectedWorkflow?.status)}</span>
                <span><strong>Progresso:</strong> {Math.round((selectedWorkflow?.progress ?? 0) * 100)}%</span>
                <span><strong>Passos:</strong> {selectedWorkflow?.steps.length ?? 0}</span>
                <span><strong>Tarefa:</strong> {selectedWorkflow?.task_id ? sessionTaskMap.get(selectedWorkflow.task_id)?.subject || selectedWorkflow.task_id : "sem vínculo"}</span>
                <span><strong>Sessão:</strong> {selectedWorkflow?.session_id || "sem vínculo"}</span>
                <span><strong>Logs:</strong> {selectedWorkflow?.log_path || "-"}</span>
                <span><strong>Artefato:</strong> {selectedWorkflow?.output_path || "-"}</span>
                <span><strong>Restart:</strong> {selectedWorkflow?.metadata?.recovered_after_restart ? "recuperado após restart" : "execução contínua"}</span>
              </div>
              <pre className="preview-text compact terminal">
                {selectedWorkflow?.log_tail || "Os logs dos workflows multi-step aparecem aqui."}
              </pre>
              <pre className="preview-text compact">
                {selectedWorkflow?.output_preview
                  ? JSON.stringify(selectedWorkflow.output_preview, null, 2)
                  : "O preview de saída e artefatos do workflow aparece aqui."}
              </pre>
            </section>

            <section className="context-card">
              <p className="eyebrow">Workspace inspector</p>
              <pre className="preview-text compact">
                {JSON.stringify(
                  {
                    scan: selectedScan ? { root_path: selectedScan.root_path, total_assets: selectedScan.total_assets } : null,
                    asset: selectedAsset ? { path: selectedAsset.relative_path, kind: selectedAsset.asset_kind } : null,
                    installers: opsDashboard?.execution_snapshot.artifacts
                      ? {
                          app: opsDashboard.execution_snapshot.artifacts.app_bundle_exists,
                          dmg: opsDashboard.execution_snapshot.artifacts.dmg_exists,
                          installer: opsDashboard.execution_snapshot.artifacts.installer_exists
                        }
                      : null
                  },
                  null,
                  2
                )}
              </pre>
            </section>
          </aside>
        </div>
      </main>
    </div>
  );
}
