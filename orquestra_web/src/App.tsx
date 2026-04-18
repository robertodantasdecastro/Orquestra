import { useEffect, useState } from "react";
import {
  ChatMessage,
  ChatSession,
  ConnectorDescriptor,
  HealthState,
  JobRecord,
  MemoryRecord,
  MemoryTopic,
  ModelArtifact,
  Project,
  ProviderProfile,
  RagResult,
  RegistryCompareResult,
  SessionSummary,
  SessionTranscript,
  TrainingCandidate,
  WorkspaceAsset,
  WorkspacePreview,
  WorkspaceQueryResult,
  WorkspaceScan,
  attachDirectory,
  compareRegistryModels,
  createDeployment,
  createJob,
  createMemory,
  createProject,
  createSession,
  extractWorkspaceAsset,
  getHealth,
  getRemoteJobLogs,
  getSummary,
  getTranscript,
  getWorkspaceScan,
  listConnectors,
  listMemory,
  listMemoryTopics,
  listMessages,
  listModels,
  listProjects,
  listProviders,
  listRegistryModels,
  listRemoteJobs,
  listSessions,
  listTrainingCandidates,
  listTrainingJobs,
  listWorkspaceAssets,
  listWorkspaceScans,
  memorizeWorkspaceAsset,
  openWorkspaceAsset,
  previewWorkspaceAsset,
  promoteMemory,
  queryRag,
  queryWorkspace,
  rawPreviewUrl,
  recallMemory,
  resumeSession,
  streamChat
} from "./api";

type ViewId = "assistant" | "workspace" | "memory" | "rag" | "models" | "jobs" | "projects" | "settings";

const views: Array<{ id: ViewId; title: string; helper: string }> = [
  { id: "assistant", title: "Assistant Workspace", helper: "Conversa, resumo de sessão e transcript." },
  { id: "workspace", title: "Workspace Browser", helper: "Anexe diretórios e explore ativos multimodais." },
  { id: "memory", title: "Memory Studio", helper: "Tópicos, recall, promoção e candidatos de treino." },
  { id: "rag", title: "RAG Studio", helper: "Consulta com fontes, scoring e memória integrada." },
  { id: "models", title: "Model Hub", helper: "Providers, registry, comparação e deploy." },
  { id: "jobs", title: "Train Ops", helper: "Conectores, jobs remotos e bundles." },
  { id: "projects", title: "Projects", helper: "Projetos, perfis e defaults operacionais." },
  { id: "settings", title: "Settings", helper: "Infra local-first, runtime e políticas." }
];

function formatDate(value?: string | null) {
  if (!value) return "agora";
  return new Date(value).toLocaleString("pt-BR");
}

function formatBytes(value?: number) {
  const size = value ?? 0;
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
  if (size < 1024 * 1024 * 1024) return `${(size / (1024 * 1024)).toFixed(1)} MB`;
  return `${(size / (1024 * 1024 * 1024)).toFixed(2)} GB`;
}

function shortList(items: string[], empty = "Sem dados ainda.") {
  return items.length ? items.join(" • ") : empty;
}

export default function App() {
  const [view, setView] = useState<ViewId>("assistant");
  const [health, setHealth] = useState<HealthState | null>(null);
  const [providers, setProviders] = useState<ProviderProfile[]>([]);
  const [projects, setProjects] = useState<Project[]>([]);
  const [connectors, setConnectors] = useState<ConnectorDescriptor[]>([]);
  const [trainingJobs, setTrainingJobs] = useState<JobRecord[]>([]);
  const [remoteJobs, setRemoteJobs] = useState<JobRecord[]>([]);
  const [registryModels, setRegistryModels] = useState<ModelArtifact[]>([]);

  const [selectedProjectId, setSelectedProjectId] = useState("");
  const [selectedProviderId, setSelectedProviderId] = useState("lmstudio");
  const [selectedModel, setSelectedModel] = useState("");
  const [models, setModels] = useState<string[]>([]);

  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [selectedSessionId, setSelectedSessionId] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [sessionSummary, setSessionSummary] = useState<SessionSummary | null>(null);
  const [sessionTranscript, setSessionTranscript] = useState<SessionTranscript | null>(null);
  const [chatPrompt, setChatPrompt] = useState("");
  const [chatStreaming, setChatStreaming] = useState(false);
  const [chatMockMode, setChatMockMode] = useState(false);
  const [resumePayload, setResumePayload] = useState<Record<string, unknown> | null>(null);

  const [workspaceRootPath, setWorkspaceRootPath] = useState("");
  const [workspacePromptHint, setWorkspacePromptHint] = useState("Analisar pasta de forma inventory-first e lazy.");
  const [workspacePrompt, setWorkspacePrompt] = useState("Quais arquivos são mais relevantes e como devo abri-los?");
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
  const [promoteTitle, setPromoteTitle] = useState("Arquitetura Orquestra V2");
  const [promoteContent, setPromoteContent] = useState("MemoryGraph, Workspace Multimodal e control plane macOS-first definidos.");

  const [ragPrompt, setRagPrompt] = useState("Quais fontes devo priorizar para threat intelligence ativa?");
  const [ragResult, setRagResult] = useState<RagResult | null>(null);
  const [ragLoading, setRagLoading] = useState(false);

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
  const [statusLine, setStatusLine] = useState("Orquestra V2 pronto para operar em modo local-first.");

  const selectedProject = projects.find((project) => project.id === selectedProjectId) ?? null;
  const selectedAsset = workspaceAssets.find((asset) => asset.id === selectedAssetId) ?? null;
  const currentView = views.find((item) => item.id === view)!;

  async function refreshGlobal(preferredProjectId?: string) {
    const [
      healthPayload,
      providersPayload,
      projectsPayload,
      connectorsPayload,
      trainingPayload,
      remotePayload,
      registryPayload
    ] = await Promise.all([
      getHealth(),
      listProviders(),
      listProjects(),
      listConnectors(),
      listTrainingJobs(),
      listRemoteJobs(),
      listRegistryModels()
    ]);

    setHealth(healthPayload);
    setProviders(providersPayload);
    setProjects(projectsPayload);
    setConnectors(connectorsPayload);
    setTrainingJobs(trainingPayload);
    setRemoteJobs(remotePayload);
    setRegistryModels(registryPayload);

    const nextProjectId = preferredProjectId ?? selectedProjectId ?? projectsPayload[0]?.id ?? "";
    setSelectedProjectId(nextProjectId);

    const nextProject = projectsPayload.find((item) => item.id === nextProjectId) ?? projectsPayload[0] ?? null;
    const nextProviderId = nextProject?.default_provider_id ?? providersPayload[0]?.provider_id ?? "lmstudio";
    setSelectedProviderId(nextProviderId);
  }

  async function refreshProjectScoped(projectId: string) {
    if (!projectId) return;
    const [sessionPayload, memoryPayload, topicsPayload, candidatesPayload, scanPayload] = await Promise.all([
      listSessions(projectId),
      listMemory(projectId),
      listMemoryTopics(projectId),
      listTrainingCandidates(projectId),
      listWorkspaceScans(projectId)
    ]);
    setSessions(sessionPayload);
    setMemoryRecords(memoryPayload);
    setMemoryTopics(topicsPayload);
    setTrainingCandidates(candidatesPayload);
    setWorkspaceScans(scanPayload);

    const nextSessionId = sessionPayload.find((item) => item.id === selectedSessionId)?.id ?? sessionPayload[0]?.id ?? "";
    setSelectedSessionId(nextSessionId);
    const nextScanId = scanPayload.find((item) => item.id === selectedScanId)?.id ?? scanPayload[0]?.id ?? "";
    setSelectedScanId(nextScanId);
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
      setResumePayload(null);
      return;
    }
    const [messagesPayload, summaryPayload, transcriptPayload] = await Promise.all([
      listMessages(sessionId),
      getSummary(sessionId),
      getTranscript(sessionId)
    ]);
    setMessages(messagesPayload);
    setSessionSummary(summaryPayload);
    setSessionTranscript(transcriptPayload);
  }

  async function refreshWorkspace(scanId: string) {
    if (!scanId) {
      setSelectedScan(null);
      setWorkspaceAssets([]);
      setSelectedAssetId("");
      setAssetPreview(null);
      return;
    }
    const [scanPayload, assetsPayload] = await Promise.all([
      getWorkspaceScan(scanId),
      listWorkspaceAssets(scanId)
    ]);
    setSelectedScan(scanPayload);
    setWorkspaceAssets(assetsPayload);
    const nextAssetId = assetsPayload.find((item) => item.id === selectedAssetId)?.id ?? assetsPayload[0]?.id ?? "";
    setSelectedAssetId(nextAssetId);
  }

  useEffect(() => {
    refreshGlobal()
      .then(() => setStatusLine("Bootstrap do Orquestra concluído."))
      .catch((error) => setStatusLine(`Falha no bootstrap: ${String(error)}`));
  }, []);

  useEffect(() => {
    if (!selectedProjectId) return;
    refreshProjectScoped(selectedProjectId).catch((error) => setStatusLine(`Falha ao carregar dados do projeto: ${String(error)}`));
  }, [selectedProjectId]);

  useEffect(() => {
    if (!selectedProviderId) return;
    const projectPreferredModel = projects.find((item) => item.id === selectedProjectId)?.default_model;
    refreshProviderModels(selectedProviderId, projectPreferredModel).catch((error) =>
      setStatusLine(`Falha ao listar modelos: ${String(error)}`)
    );
  }, [selectedProviderId, selectedProjectId]);

  useEffect(() => {
    if (!selectedSessionId) return;
    refreshSession(selectedSessionId).catch((error) => setStatusLine(`Falha ao carregar sessão: ${String(error)}`));
  }, [selectedSessionId]);

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

  async function handleSendChat() {
    if (!chatPrompt.trim() || chatStreaming) return;
    const prompt = chatPrompt.trim();
    setChatPrompt("");
    setChatStreaming(true);
    setStatusLine("Streaming do Assistant Workspace em andamento.");

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
          mock_response: chatMockMode
        },
        {
          onSession: ({ session_id }) => {
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
                ? { ...current, current_state: payload.current_state, updated_at: payload.updated_at }
                : {
                    session_id: selectedSessionId,
                    current_state: payload.current_state,
                    next_steps: "",
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
          onDone: ({ provider_id, model_name, usage, latency_seconds }) => {
            setMessages((current) =>
              current.map((message, index) =>
                index === current.length - 1 && message.role === "assistant"
                  ? { ...message, provider_id, model_name, usage, latency_seconds }
                  : message
              )
            );
            setStatusLine(`Resposta concluída via ${provider_id}/${model_name} em ${latency_seconds.toFixed(2)}s.`);
          }
        }
      );
      await refreshProjectScoped(selectedProjectId);
      if (selectedSessionId) {
        await refreshSession(selectedSessionId);
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
      setStatusLine("Payload de retomada da sessão atualizado.");
      await refreshSession(selectedSessionId);
    } catch (error) {
      setStatusLine(`Falha ao retomar sessão: ${String(error)}`);
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
      setStatusLine(`Diretório anexado com sucesso: ${scan.root_path}`);
      await refreshProjectScoped(selectedProjectId);
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
    } catch (error) {
      setStatusLine(`Falha ao extrair asset: ${String(error)}`);
    }
  }

  async function handleOpenAsset() {
    if (!selectedAssetId) return;
    try {
      const payload = await openWorkspaceAsset(selectedAssetId);
      setStatusLine(`Abrir asset via ${payload.strategy}: ${payload.absolute_path}`);
      window.open(rawPreviewUrl(selectedAssetId), "_blank", "noopener,noreferrer");
    } catch (error) {
      setStatusLine(`Falha ao abrir asset: ${String(error)}`);
    }
  }

  async function handleMemorizeAsset() {
    if (!selectedAssetId) return;
    try {
      await memorizeWorkspaceAsset(selectedAssetId, { project_id: selectedProjectId || undefined });
      setStatusLine("Asset promovido para memória de workspace.");
      await refreshProjectScoped(selectedProjectId);
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
        source: "workspace_ui"
      });
      setStatusLine("Memória promovida para tópico durável.");
      await refreshProjectScoped(selectedProjectId);
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
        source: "workspace_ui",
        content: promoteContent,
        confidence: 0.82,
        approved_for_training: false
      });
      setStatusLine("Memória manual registrada.");
      await refreshProjectScoped(selectedProjectId);
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
        task_type: "orquestra_analysis",
        remember: true,
        mock_llm: chatMockMode
      });
      setRagResult(result);
      setStatusLine("Consulta do RAG concluída.");
      await refreshProjectScoped(selectedProjectId);
    } catch (error) {
      setStatusLine(`Falha no RAG Studio: ${String(error)}`);
    } finally {
      setRagLoading(false);
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
          model_name: selectedModel,
          provider_id: selectedProviderId,
          source: "orquestra_v2_ui",
          project_id: selectedProjectId
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
        notes: "Deploy registrado pela UI Orquestra V2."
      });
      setStatusLine("Deploy registrado no projeto.");
    } catch (error) {
      setStatusLine(`Falha ao registrar deploy: ${String(error)}`);
    }
  }

  return (
    <div className="orquestra-shell">
      <aside className="rail">
        <div className="rail-brand">
          <div className="brand-chip">OA</div>
          <div>
            <strong>Orquestra AI</strong>
            <span>MemoryGraph + Workspace Multimodal</span>
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
            <button type="button" className="ghost-button" onClick={() => refreshGlobal(selectedProjectId).then(() => refreshProjectScoped(selectedProjectId))}>
              Atualizar
            </button>
          </div>
        </header>

        <section className="hero-strip">
          <div className="hero-copy">
            <h2>Um workspace único para conversar, lembrar, varrer pastas, consultar o RAG e operar jobs.</h2>
            <p>
              O Orquestra V2 prioriza inventário leve, memória estruturada e execução local-first. Quando nuvem e compute
              remoto estiverem disponíveis, os mesmos objetos e rotas continuam válidos.
            </p>
          </div>
          <div className="hero-metrics">
            <article>
              <span>Backend</span>
              <strong>{health?.ok ? "healthy" : "offline"}</strong>
            </article>
            <article>
              <span>Providers</span>
              <strong>{health?.providers ?? 0}</strong>
            </article>
            <article>
              <span>Tópicos</span>
              <strong>{health?.memory_topics ?? 0}</strong>
            </article>
            <article>
              <span>Scans</span>
              <strong>{health?.workspace_scans ?? 0}</strong>
            </article>
          </div>
        </section>

        <div className="workspace-grid">
          <section className="primary-stage">
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
                      onClick={async () => {
                        const session = await createSession({
                          project_id: selectedProjectId || undefined,
                          title: "Nova sessão Orquestra",
                          provider_id: selectedProviderId,
                          model_name: selectedModel
                        });
                        setSelectedSessionId(session.id);
                        await refreshProjectScoped(selectedProjectId);
                      }}
                    >
                      Nova sessão
                    </button>
                  </div>
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

            {view === "memory" && (
              <div className="memory-layout">
                <section className="panel">
                  <div className="panel-head">
                    <div>
                      <p className="eyebrow">Recall</p>
                      <h3>Seleção leve + semântica</h3>
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

                  <div className="memory-grid">
                    <div className="memory-column">
                      <h4>Tópicos duráveis</h4>
                      {memoryTopics.map((topic) => (
                        <article key={topic.id} className="memory-card">
                          <strong>{topic.title}</strong>
                          <span>{topic.scope}</span>
                          <p>{topic.description || topic.slug}</p>
                        </article>
                      ))}
                    </div>
                    <div className="memory-column">
                      <h4>Recall</h4>
                      {(memoryRecallResults?.items ?? []).map((item, index) => (
                        <article key={`${item.title}-${index}`} className="memory-card">
                          <strong>{item.title}</strong>
                          <span>{item.scope || "memory"}</span>
                          <p>{item.content}</p>
                        </article>
                      ))}
                    </div>
                  </div>
                </section>

                <section className="panel">
                  <div className="panel-head">
                    <div>
                      <p className="eyebrow">Promotion</p>
                      <h3>Promover resumo útil para memória durável</h3>
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
                    </div>
                  </div>
                </section>
              </div>
            )}

            {view === "rag" && (
              <section className="panel">
                <div className="panel-head">
                  <div>
                    <p className="eyebrow">RAG Studio</p>
                    <h3>Consulta com fontes e memória compartilhada</h3>
                  </div>
                </div>
                <div className="form-stack">
                  <textarea value={ragPrompt} onChange={(event) => setRagPrompt(event.target.value)} />
                  <div className="composer-actions">
                    <button type="button" className="primary-button" onClick={handleRagQuery} disabled={ragLoading}>
                      {ragLoading ? "Consultando..." : "Executar consulta"}
                    </button>
                  </div>
                </div>

                {ragResult && (
                  <div className="result-layout">
                    <article className="result-panel">
                      <header>
                        <strong>{ragResult.provider_id || selectedProviderId}/{ragResult.model_name || selectedModel}</strong>
                        <span>{ragResult.latency_seconds?.toFixed(2) ?? "0.00"}s</span>
                      </header>
                      <p>{ragResult.answer}</p>
                    </article>
                    <article className="result-panel">
                      <h4>Citações</h4>
                      {(ragResult.citations ?? []).map((citation, index) => (
                        <div key={`${citation.source}-${index}`} className="result-asset">
                          <strong>{citation.title || citation.source || "Fonte"}</strong>
                          <span>{citation.channel || "contexto"}</span>
                        </div>
                      ))}
                    </article>
                  </div>
                )}
              </section>
            )}

            {view === "models" && (
              <div className="models-layout">
                <section className="panel">
                  <div className="panel-head">
                    <div>
                      <p className="eyebrow">Mesh Gateway</p>
                      <h3>Providers e capacidades</h3>
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
                </section>

                <section className="panel">
                  <div className="panel-head">
                    <div>
                      <p className="eyebrow">Registry</p>
                      <h3>Comparação e deploy</h3>
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
                </section>
              </div>
            )}

            {view === "jobs" && (
              <div className="jobs-layout">
                <section className="panel">
                  <div className="panel-head">
                    <div>
                      <p className="eyebrow">Connectors</p>
                      <h3>Forge / Remote Ops</h3>
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
                </section>

                <section className="panel">
                  <div className="panel-head">
                    <div>
                      <p className="eyebrow">Jobs</p>
                      <h3>Fila, status e logs</h3>
                    </div>
                  </div>
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

            {view === "settings" && (
              <section className="panel">
                <div className="panel-head">
                  <div>
                    <p className="eyebrow">Settings</p>
                    <h3>Runtime local-first</h3>
                  </div>
                </div>
                <div className="settings-grid">
                  <article className="provider-card">
                    <strong>Workspace root</strong>
                    <p>{health?.workspace_root || "-"}</p>
                  </article>
                  <article className="provider-card">
                    <strong>Database</strong>
                    <p>{health?.database_url || "-"}</p>
                  </article>
                  <article className="provider-card">
                    <strong>Redis</strong>
                    <p>{health?.redis_url || "-"}</p>
                  </article>
                  <article className="provider-card">
                    <strong>Qdrant</strong>
                    <p>{health?.qdrant_url || health?.qdrant_path || "-"}</p>
                  </article>
                </div>
                <pre className="preview-text">
                  {JSON.stringify(
                    {
                      selectedProject: selectedProject?.name,
                      selectedProviderId,
                      selectedModel,
                      webEnabled: health?.web_enabled,
                      connectorsReady: connectors.filter((item) => item.ready).map((item) => item.connector_id)
                    },
                    null,
                    2
                  )}
                </pre>
              </section>
            )}
          </section>

          <aside className="context-rail">
            <section className="context-card">
              <p className="eyebrow">Session Working Memory</p>
              <h3>{selectedSessionId ? "Resumo ativo" : "Sem sessão ativa"}</h3>
              <p>{sessionSummary?.current_state || "O resumo da sessão aparece aqui após interações ou retomada."}</p>
              <div className="context-list">
                <span><strong>Arquivos:</strong> {shortList(sessionSummary?.relevant_files ?? [])}</span>
                <span><strong>Próximos passos:</strong> {sessionSummary?.next_steps || "Sem próximos passos ainda."}</span>
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
              <p className="eyebrow">Resume Payload</p>
              <pre className="preview-text compact">{JSON.stringify(resumePayload, null, 2)}</pre>
            </section>

            <section className="context-card">
              <p className="eyebrow">Workspace Inspector</p>
              <pre className="preview-text compact">
                {JSON.stringify(
                  {
                    scan: selectedScan ? { root_path: selectedScan.root_path, total_assets: selectedScan.total_assets } : null,
                    asset: selectedAsset ? { path: selectedAsset.relative_path, kind: selectedAsset.asset_kind } : null,
                    registryModels: registryModels.length
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
