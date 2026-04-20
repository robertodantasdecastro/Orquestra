# Orquestra V2

`Orquestra V2` e a evolucao do control plane do `Orquestra` para um workspace macOS-first com memoria estruturada, leitura multimodal de diretorios e shell desktop.

Manual de uso completo:
- `docs/02-manual-operacional.md`

## Objetivo
Concentrar em uma unica superficie:
- conversa multi-provider;
- memoria de sessao e memoria duravel;
- inventario e leitura multimodal de pastas;
- consulta `RAG`;
- operacao de jobs remotos;
- registry e comparacao de modelos.
- instalacao e desinstalacao macOS por scripts versionados.

## Blocos do V2
### Control Plane
- `orquestra_ai/app.py`
- `orquestra_ai/services.py`
- `orquestra_ai/models.py`

### MemoryGraph
- `orquestra_ai/memory_graph.py`
- `orquestra_ai/memory_recall.py`
- `orquestra_ai/session_profile.py`
- `orquestra_ai/memory_candidates.py`
- `orquestra_ai/rag_memory.py`
- transcript bruto
- resumo de sessao
- estado de compactacao
- perfil operacional de sessao
- candidatos revisaveis
- memoria duravel
- training candidates
- projecao em arquivos `memdir`

### Planner / Workflows
- `orquestra_ai/planner.py`
- `orquestra_ai/workflow_engine.py`
- `PlannerSnapshot`
- `SessionTask`
- `WorkflowRun`
- `WorkflowStepRun`

### Workspace Multimodal
- `orquestra_ai/workspace.py`
- scanner recursivo `inventory-first`
- handlers para:
  - `code_text`
  - `image`
  - `pdf`
  - `office`
  - `audio`
  - `video`

### Mesh Gateway
- `orquestra_ai/gateway.py`
- providers:
  - `lmstudio`
  - `openai`
  - `anthropic`
  - `deepseek`
  - `ollama`

### Registry / Forge
- `orquestra_ai/connectors.py`
- `training jobs`
- `remote jobs`
- `registry compare`
- deploy por projeto

Neste ciclo, `Train Ops` e `Registry` ja funcionam como superficie de catalogo, registro e comparacao. A execucao remota real dos conectores fica para uma fase posterior.

### Frontend / Desktop
- `orquestra_web/src/App.tsx`
- `orquestra_web/src/api.ts`
- `orquestra_web/src/styles.css`
- `orquestra_web/src-tauri/`

O shell de UI agora organiza a operação em quatro superfícies principais:
- `Operations Dashboard`
- `Process Center`
- `Memory Studio`
- `Execution Center`

Tambem existem superficies de trabalho para:
- `Assistant Workspace`
- `Workspace Browser`
- `Projects`
- `RAG Studio`, integrado ao contexto operacional.

## MemoryGraph V2
### Camadas
1. `raw_transcript`
2. `session_compaction_state`
3. `session_profile`
4. `memory_review_candidates`
5. `durable_memory`
6. `rag_memory_index`
7. `planner_snapshot_and_tasks`
8. `workflow_runs`
9. `training_candidates`

### Memoria associada ao RAG
Cada `ChatSession` possui um `Session Profile` em `metadata_json` com:
- `objective`: objetivo textual da sessao;
- `preset`: `research`, `osint`, `persona`, `assistant` ou `dataset`;
- `memory_policy`: captura automatica revisavel, escopos ativos, retencao e uso no prompt;
- `rag_policy`: colecoes habilitadas, uso de memoria, workspace e fontes locais;
- `persona_config`: tom, estilo, restricoes e referencias de assimilacao.

A colecao vetorial padrao para memoria aprovada e `orquestra_memory_v1` no Chroma. O `MemoryGraph` continua como camada estruturada em SQLite, JSONL e Markdown. Qdrant permanece disponivel como backend futuro/adaptavel, mas nao e requisito para a V1 local.

Os registros aprovados sao materializados em tres destinos:
1. banco local;
2. projecao de arquivos em `artifacts_root/memorygraph/memdir`;
3. indice vetorial `orquestra_memory_v1`.

Estrutura de projecao:
- `memorygraph/memdir/global`
- `memorygraph/memdir/projects/<slug>`
- `memorygraph/memdir/sessions/<session_id>`

Tipos de memoria aceitos:
- `user`
- `feedback`
- `project`
- `reference`
- `persona`
- `dataset`

O runtime do RAG respeita `RAG_RUNTIME_ROOT`/`LOCAL_TRAIN_RUNTIME_ROOT` quando estiver gravavel. Se o volume configurado estiver ausente ou sem permissao, o Orquestra cai automaticamente para `experiments/orquestra/rag_runtime`, evitando quebra em Macs sem SSD externo montado.

Fluxo de chat:
1. o usuario cria uma sessao definindo objetivo e preset;
2. o chat carrega perfil, snapshot compacto, memorias aprovadas relevantes, planner e fontes locais;
3. a resposta usa um contexto pequeno `summary + recent tail + recalled memory + workspace/fontes` quando disponiveis;
4. o transcript bruto e o resumo operacional sao atualizados;
5. o Orquestra atualiza `SessionCompactionState` quando necessario e preserva `next_steps`;
6. o Orquestra gera `MemoryReviewCandidate` pendente;
7. somente apos aprovacao o candidato vira `MemoryRecord` e e indexado em `orquestra_memory_v1`;
8. `TrainingCandidate` so nasce quando a aprovacao marca explicitamente uso para dataset.

Escopos suportados:
- `session_memory`
- `episodic_memory`
- `semantic_memory`
- `workspace_memory`
- `persona_memory`
- `source_fact`
- `training_signal`

### Contratos principais
- `POST /api/chat/sessions` com `objective`, `preset`, `memory_policy` e `rag_policy`
- `GET /api/chat/sessions/{id}/profile`
- `PUT /api/chat/sessions/{id}/profile`
- `POST /api/chat/sessions/{id}/resume`
- `GET /api/chat/sessions/{id}/transcript`
- `GET /api/chat/sessions/{id}/summary`
- `POST /api/chat/sessions/{id}/compact`
- `GET /api/chat/sessions/{id}/planner`
- `POST /api/chat/sessions/{id}/planner/rebuild`
- `GET /api/chat/sessions/{id}/tasks`
- `POST /api/chat/sessions/{id}/tasks`
- `PATCH /api/chat/sessions/{id}/tasks`
- `GET /api/memory/candidates`
- `POST /api/memory/candidates/{id}/approve`
- `POST /api/memory/candidates/{id}/reject`
- `GET /api/memory/topics`
- `POST /api/memory/recall`
- `POST /api/memory/promote`
- `GET /api/memory/training-candidates`
- `GET /api/workflows/runs`
- `POST /api/workflows/runs`
- `GET /api/workflows/runs/{id}`
- `POST /api/workflows/runs/{id}/cancel`

### Politica
- transcript nunca e o resumo;
- compactacao protege continuidade e auditoria;
- memoria duravel entra por promocao manual ou aprovacao explicita do `Memory Inbox`;
- conversa nao vira dataset sem aprovacao explicita;
- recall semantico deve degradar para recall lexical quando necessario.
- falha de embedding, Chroma ou seletor vetorial nao pode quebrar o chat.

## Planner Hibrido
Cada sessao pode manter um `PlannerSnapshot` persistido com:
- `objective`
- `strategy`
- `next_steps`
- `risks`

As tarefas reais da sessao vivem em `SessionTask` com estados:
- `pending`
- `in_progress`
- `blocked`
- `completed`
- `failed`
- `cancelled`

O planner e operacional, nao memoria duravel. Ele guia a sessao atual, sobrevive a reload/restart e pode ser reconstruido a partir do resumo quando a abordagem mudar.

## Executor Local Multi-step
`WorkflowEngine` persiste `WorkflowRun` e `WorkflowStepRun` e reaproveita `OrquestraOperations` como backend para `ops_action`.

Passos locais suportados na V1:
- `ops_action`
- `rag_query`
- `workspace_query`
- `workspace_extract`
- `memory_review_batch`
- `shell_safe`

Garantias:
- progresso por passo;
- cancelamento;
- log tail persistido em arquivo;
- retomada/reclassificacao apos restart;
- vinculo opcional com sessao e tarefa do planner.

## Workspace Multimodal
### Fluxo
1. anexar diretorio
2. gerar inventario recursivo
3. rankear ativos pelo prompt
4. extrair sob demanda
5. responder citando caminhos e acoes
6. promover ativo relevante para memoria quando necessario

### Politica de eficiencia
- nao duplicar binarios no banco;
- armazenar metadados e derivados pequenos;
- usar TTL para derivados pesados;
- indexacao pesada so sob demanda;
- fallback para operacao lexical quando o backend vetorial nao puder ser aberto.

## Shell desktop macOS
### Estrutura
- `orquestra_web/src-tauri/Cargo.toml`
- `orquestra_web/src-tauri/tauri.conf.json`
- `orquestra_web/src-tauri/src/main.rs`

### Runtime
- o shell desktop e fino;
- a API segue local em `127.0.0.1:8808`;
- a UI aponta para a API por `VITE_ORQUESTRA_API_BASE`.
- web e desktop consomem o mesmo snapshot operacional e as mesmas ações gerenciadas.
- a marca vetorial fica em `assets/brand/orquestra-logo.svg` e `orquestra_web/src/assets/orquestra-logo.svg`.
- a build macOS gera `Orquestra AI.app` e `Orquestra AI_0.2.0_aarch64.dmg`.
- `scripts/validate_orquestra_macos_package.sh` valida `.app`, DMG, `Info.plist`, executavel e scripts de instalacao.
- `scripts/install_orquestra_macos.sh` instala o `.app`, sincroniza runtime em `~/Library/Application Support/Orquestra/runtime` e registra o LaunchAgent `ai.orquestra.api`.
- `script/build_and_run.sh --verify` builda, valida, sobe a API local, abre o app e confere processo + `/api/health`.

### Comandos
```bash
cd /caminho/para/Orquestra
./scripts/start_orquestra_api.sh
./scripts/start_orquestra_web.sh
```

ou:

```bash
cd /caminho/para/Orquestra
./scripts/start_orquestra_desktop.sh
```

Build/validacao desktop:
```bash
cd /caminho/para/Orquestra
./script/build_and_run.sh --verify
./scripts/validate_orquestra_macos_package.sh
```

## Validacao executada neste ciclo
- `py_compile` do backend `Orquestra`
- `pytest -q`
- `vitest`
- `npm run build` do frontend
- `cargo check` do shell `Tauri`
- `tauri build` com bundle `.app` e `.dmg`
- smoke de `chat + summary + compact + planner + resume + transcript`
- smoke de `attach-directory + workspace query + extract + preview + memorize`
- smoke de `workflow local multi-step`
- validação de tipagem/integração da nova superfície operacional e dos scripts de instalação macOS

## Proximos passos
1. ligar providers reais via `LiteLLM Proxy`
2. ampliar cobertura de UI/desktop com mais cenarios de workflow e planner
3. adicionar OCR e transcricao real opcional
4. amadurecer UX e readiness operacional de `Train Ops` e `Registry` sem depender ainda de execucao remota real
5. decidir se a instalacao macOS evolui para `pkg` assinado ou segue script-first nesta fase
6. avaliar assinatura e notarizacao quando houver distribuicao fora do ambiente local do usuario
