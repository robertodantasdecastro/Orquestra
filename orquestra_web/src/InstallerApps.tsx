import { useEffect, useMemo, useState } from "react";
import orquestraLogo from "./assets/orquestra-logo.png";

declare global {
  interface Window {
    __TAURI__?: {
      core?: {
        invoke: (command: string, args?: Record<string, unknown>) => Promise<string>;
      };
    };
  }
}

type CommandResult = {
  success?: boolean;
  code?: number;
  stdout?: string;
  stderr?: string;
  message?: string;
};

type InstallPlan = {
  kind: "InstallPlan";
  generated_at: string;
  version: string;
  platform: Record<string, string>;
  paths: Record<string, string>;
  dependencies: Array<{ command: string; installed: boolean; path: string; required: boolean }>;
  optional_features: Array<{ id: string; label: string; configured: boolean; required: boolean }>;
  providers: Array<{ env: string; configured: boolean; secret_output: boolean }>;
  runtime_storage: Record<string, unknown>;
  steps: Array<{ id: string; label: string }>;
};

type UninstallPlan = {
  kind: "UninstallPlan";
  generated_at: string;
  mode: string;
  items: Array<{
    id: string;
    label: string;
    path: string;
    exists: boolean;
    selected: boolean;
    sensitive: boolean;
    backup_recommended: boolean;
  }>;
  dependencies: Array<{ id: string; label: string; selected: boolean }>;
  strong_confirmation_required: boolean;
};

const mockInstallPlan: InstallPlan = {
  kind: "InstallPlan",
  generated_at: new Date().toISOString(),
  version: "0.2.0",
  platform: { system: "Darwin", machine: "arm64", release: "local-preview" },
  paths: {
    installed_app: "~/Applications/Orquestra AI.app",
    runtime: "~/Library/Application Support/Orquestra/runtime",
    runtime_config: "~/Library/Application Support/Orquestra/runtime/config/runtime.json"
  },
  dependencies: ["xcode-select", "brew", "python3.12", "node", "npm", "cargo", "rustc", "uv", "git"].map((command) => ({
    command,
    installed: false,
    path: "",
    required: true
  })),
  optional_features: [
    { id: "lmstudio", label: "LM Studio", configured: false, required: false },
    { id: "tor", label: "Tor proxy", configured: false, required: false },
    { id: "ffmpeg", label: "ffmpeg", configured: false, required: false }
  ],
  providers: ["OPENAI_API_KEY", "DEEPSEEK_API_KEY", "BRAVE_SEARCH_API_KEY"].map((env) => ({
    env,
    configured: false,
    secret_output: false
  })),
  runtime_storage: {},
  steps: [
    { id: "preflight", label: "Diagnosticar macOS e dependências" },
    { id: "runtime", label: "Criar runtime.json e storage local-first" },
    { id: "app", label: "Instalar app, LaunchAgent e validar API" }
  ]
};

async function invokeJson<T>(command: string, args?: Record<string, unknown>, fallback?: T): Promise<T> {
  const invoke = window.__TAURI__?.core?.invoke;
  if (!invoke) {
    if (fallback !== undefined) return fallback;
    throw new Error("Comandos Tauri indisponíveis neste ambiente.");
  }
  const raw = await invoke(command, args);
  const result = JSON.parse(raw) as CommandResult;
  if (result.success === false) {
    throw new Error(result.stderr || result.message || `Comando falhou: ${command}`);
  }
  if (!result.stdout) return result as T;
  return JSON.parse(result.stdout) as T;
}

function statusClass(ok: boolean) {
  return ok ? "ready" : "missing";
}

function WizardShell({
  title,
  subtitle,
  children,
  status
}: {
  title: string;
  subtitle: string;
  children: React.ReactNode;
  status: string;
}) {
  return (
    <div className="installer-shell">
      <aside className="installer-rail">
        <div className="rail-brand">
          <div className="brand-chip">
            <img src={orquestraLogo} alt="Orquestra AI" />
          </div>
          <div>
            <strong>{title}</strong>
            <span>{subtitle}</span>
          </div>
        </div>
        <div className="rail-status">
          <div className="pulse" />
          <p>{status}</p>
        </div>
      </aside>
      <main className="installer-main">{children}</main>
    </div>
  );
}

export function InstallerApp() {
  const [plan, setPlan] = useState<InstallPlan | null>(null);
  const [status, setStatus] = useState("Aguardando diagnóstico inicial.");
  const [requiredOnly, setRequiredOnly] = useState(false);
  const [selectedOptional, setSelectedOptional] = useState<Set<string>>(new Set(["tor", "ffmpeg"]));
  const missingRequired = useMemo(() => plan?.dependencies.filter((item) => !item.installed) ?? [], [plan]);

  async function refresh() {
    setStatus("Executando preflight gráfico...");
    try {
      const payload = await invokeJson<InstallPlan>("installer_preflight", undefined, mockInstallPlan);
      setPlan(payload);
      setStatus("Plano de instalação carregado.");
    } catch (error) {
      setStatus(`Falha no preflight: ${String(error)}`);
    }
  }

  async function runInstall() {
    setStatus("Instalação iniciada. O log final aparecerá aqui quando o script terminar.");
    try {
      const optionalCsv = Array.from(selectedOptional).join(",");
      const result = await invokeJson<CommandResult>("installer_run_plan", {
        requiredOnly,
        optionalCsv,
        configureEnv: false
      });
      setStatus(result.stdout || result.message || "Instalação finalizada.");
      await refresh();
    } catch (error) {
      setStatus(`Falha na instalação: ${String(error)}`);
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  return (
    <WizardShell title="Orquestra Installer" subtitle="Instalação gráfica local-first" status={status}>
      <section className="wizard-hero">
        <p className="eyebrow">macOS graphical installer</p>
        <h1>Instale o Orquestra com runtime, storage, providers e OSINT sob controle.</h1>
        <p>
          Este wizard usa os scripts oficiais como motor, salva segredos no Keychain e prepara o `runtime.json`
          para que memória, RAG, OSINT e workflows tenham caminhos rastreáveis.
        </p>
        <div className="composer-actions">
          <button className="primary-button" type="button" onClick={runInstall}>Instalar agora</button>
          <button className="ghost-button" type="button" onClick={refresh}>Revalidar</button>
        </div>
      </section>

      <section className="stage-grid">
        <article className="panel">
          <div className="panel-head"><div><p className="eyebrow">Preflight</p><h3>Dependências obrigatórias</h3></div></div>
          <div className="service-grid">
            {(plan?.dependencies ?? []).map((item) => (
              <div className={`service-card ${statusClass(item.installed)}`} key={item.command}>
                <strong>{item.command}</strong>
                <span className={`state-pill ${statusClass(item.installed)}`}>{item.installed ? "ok" : "ausente"}</span>
                <small>{item.path || "será orientado/instalado quando autorizado"}</small>
              </div>
            ))}
          </div>
          <p className="subtitle">{missingRequired.length ? `${missingRequired.length} itens precisam de ação.` : "Base obrigatória pronta."}</p>
        </article>

        <article className="panel">
          <div className="panel-head"><div><p className="eyebrow">Recursos</p><h3>Opcionais e providers</h3></div></div>
          <label className="toggle-row">
            <input type="checkbox" checked={requiredOnly} onChange={(event) => setRequiredOnly(event.target.checked)} />
            Instalar somente o núcleo obrigatório
          </label>
          <div className="provider-grid">
            {(plan?.optional_features ?? []).map((item) => (
              <label className="provider-card" key={item.id}>
                <input
                  type="checkbox"
                  checked={selectedOptional.has(item.id)}
                  onChange={(event) =>
                    setSelectedOptional((current) => {
                      const next = new Set(current);
                      if (event.target.checked) next.add(item.id);
                      else next.delete(item.id);
                      return next;
                    })
                  }
                />
                <strong>{item.label}</strong>
                <span>{item.configured ? "detectado" : "opcional"}</span>
              </label>
            ))}
          </div>
        </article>

        <article className="panel two-column-panel">
          <div>
            <p className="eyebrow">Runtime & Storage</p>
            <h3>Caminhos que serão configurados</h3>
            <div className="context-list">
              <span><strong>Runtime:</strong> {plan?.paths.runtime}</span>
              <span><strong>runtime.json:</strong> {plan?.paths.runtime_config}</span>
              <span><strong>App:</strong> {plan?.paths.installed_app}</span>
            </div>
          </div>
          <div>
            <p className="eyebrow">Chaves</p>
            <h3>Providers sem expor segredo</h3>
            <div className="token-list">
              {(plan?.providers ?? []).map((item) => (
                <span key={item.env}>{item.env}: {item.configured ? "configurado" : "pendente"}</span>
              ))}
            </div>
          </div>
        </article>
      </section>
    </WizardShell>
  );
}

export function UninstallerApp() {
  const [mode, setMode] = useState("safe");
  const [plan, setPlan] = useState<UninstallPlan | null>(null);
  const [status, setStatus] = useState("Aguardando varredura.");
  const [backupData, setBackupData] = useState(true);
  const [confirmAll, setConfirmAll] = useState("");

  async function refresh(nextMode = mode) {
    setStatus("Detectando instalação atual...");
    try {
      const payload = await invokeJson<UninstallPlan>("uninstaller_build_plan", { mode: nextMode }, {
        kind: "UninstallPlan",
        generated_at: new Date().toISOString(),
        mode: nextMode,
        items: [],
        dependencies: [],
        strong_confirmation_required: nextMode === "all"
      });
      setPlan(payload);
      setStatus("Plano de remoção carregado.");
    } catch (error) {
      setStatus(`Falha na varredura: ${String(error)}`);
    }
  }

  async function runUninstall() {
    if (mode === "all" && confirmAll !== "REMOVER ORQUESTRA") {
      setStatus("Digite REMOVER ORQUESTRA para confirmar o modo destrutivo.");
      return;
    }
    try {
      const result = await invokeJson<CommandResult>("uninstaller_run_plan", {
        mode,
        backupData,
        confirmRemoveAll: mode === "all"
      });
      setStatus(result.stdout || result.message || "Desinstalação finalizada.");
      await refresh(mode);
    } catch (error) {
      setStatus(`Falha na desinstalação: ${String(error)}`);
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  return (
    <WizardShell title="Orquestra Uninstaller" subtitle="Remoção seletiva com backup" status={status}>
      <section className="wizard-hero danger-zone">
        <p className="eyebrow">macOS graphical uninstaller</p>
        <h1>Remova o Orquestra sem perder memória, RAG ou evidências por acidente.</h1>
        <p>Escolha o modo, revise itens sensíveis e gere backup antes de apagar dados locais.</p>
        <div className="composer-actions">
          <select value={mode} onChange={(event) => { setMode(event.target.value); refresh(event.target.value); }}>
            <option value="safe">Seguro seletivo</option>
            <option value="preserve-deps">Preservar dependências</option>
            <option value="all">Remover tudo</option>
          </select>
          <button className="primary-button" type="button" onClick={runUninstall}>Executar remoção</button>
          <button className="ghost-button" type="button" onClick={() => refresh(mode)}>Revalidar</button>
        </div>
      </section>

      <section className="stage-grid">
        <article className="panel">
          <div className="panel-head"><div><p className="eyebrow">Itens detectados</p><h3>Dados e componentes</h3></div></div>
          <label className="toggle-row">
            <input type="checkbox" checked={backupData} onChange={(event) => setBackupData(event.target.checked)} />
            Criar backup antes de remover dados sensíveis
          </label>
          <div className="service-grid">
            {(plan?.items ?? []).map((item) => (
              <div className={`service-card ${item.selected ? "warning" : "ready"}`} key={item.id}>
                <strong>{item.label}</strong>
                <span className={`state-pill ${item.exists ? "ready" : "missing"}`}>{item.exists ? "existe" : "ausente"}</span>
                <p>{item.path}</p>
                <small>{item.sensitive ? "sensível, backup recomendado" : item.selected ? "selecionado" : "preservado"}</small>
              </div>
            ))}
          </div>
        </article>

        {mode === "all" && (
          <article className="panel">
            <div className="panel-head"><div><p className="eyebrow">Confirmação forte</p><h3>Remover tudo</h3></div></div>
            <p>Para liberar o modo destrutivo, digite exatamente:</p>
            <pre className="preview-text compact">REMOVER ORQUESTRA</pre>
            <input value={confirmAll} onChange={(event) => setConfirmAll(event.target.value)} />
          </article>
        )}
      </section>
    </WizardShell>
  );
}
