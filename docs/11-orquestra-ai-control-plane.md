# Orquestra AI Control Plane

## Objetivo
Este documento descreve o desenho operacional do Orquestra como control plane local-first para:

- chat multi-provider
- memoria persistente e memoria operacional
- RAG contextual
- leitura multimodal de diretorios
- planner de sessao
- workflows locais multi-step
- registro de jobs, modelos e artefatos

## Componentes principais
### Backend
- `orquestra_ai/app.py`
- `orquestra_ai/services.py`
- `orquestra_ai/models.py`

O backend:
- serve a API
- coordena sessao, memoria, planner e workflow
- executa bootstrap de runtime por `lifespan`
- expõe saude, dashboard e endpoints de produto

### Train Plane remoto
- `orquestra_trainplane/app.py`
- `orquestra_trainplane/worker.py`
- `orquestra_trainplane/models.py`
- `orquestra_trainplane/services.py`

O servico remoto:
- expõe auth por bootstrap admin + `TOTP` + `PAT`
- recebe `base models` e `dataset bundles`
- executa `training runs` adapter-first em modo validavel
- publica `artifacts`, `evaluation runs` e `comparison runs`
- serve um console web remoto simplificado para operacao e inspeção

### Gateway de modelos
- `orquestra_ai/gateway.py`

Providers suportados:
- `lmstudio`
- `openai`
- `anthropic`
- `deepseek`
- `ollama`
- `litellm`

### Memoria e contexto
- `orquestra_ai/memory_graph.py`
- `orquestra_ai/memory_recall.py`
- `orquestra_ai/rag_memory.py`
- `orquestra_ai/session_profile.py`
- `orquestra_ai/memory_candidates.py`

### Planner e workflow
- `orquestra_ai/planner.py`
- `orquestra_ai/workflow_engine.py`
- `orquestra_ai/operations.py`

### Workspace
- `orquestra_ai/workspace.py`

### Frontend e desktop
- `orquestra_web/src/App.tsx`
- `orquestra_web/src/api.ts`
- `orquestra_web/src-tauri/`

O frontend agora tambem incorpora o bloco `Remote Train Plane` dentro do `Execution Center`.

## Superficies da interface
As areas de produto usadas hoje pelo shell web/desktop sao:

1. `Operations Dashboard`
2. `Process Center`
3. `Memory Studio`
4. `Execution Center`
5. `Assistant Workspace`
6. `Workspace Browser`
7. `Projects`

## Modelo operacional da sessao
Cada sessao combina:
- `ChatSession`
- `ChatMessage`
- `SessionTranscript`
- `SessionSummary`
- `SessionCompactionState`
- `PlannerSnapshot`
- `SessionTask`

### Perfil da sessao
O perfil fica em `ChatSession.metadata_json` e inclui:
- `objective`
- `preset`
- `memory_policy`
- `rag_policy`
- `persona_config`

### Presets
- `research`
- `osint`
- `persona`
- `assistant`
- `dataset`

## Semantica real das flags publicas
Os contratos publicos de `POST /api/chat/stream` e `POST /api/rag/query` ja tem semantica operacional efetiva:

- `planner_enabled`: controla o uso do planner no contexto e na reconstrução operacional
- `memory_selector_mode`: aceita `hybrid` e `lexical`
- `include_workspace`: controla a secao `Workspace/fontes`
- `include_sources`: controla a secao `RAG legado`
- `compaction_enabled`: liga/desliga snapshot compacto
- `task_context_enabled`: controla uso do contexto de tarefas
- `context_budget`: limita o contexto agregado

### Ordem fixa do contexto
1. perfil da sessao
2. snapshot compacto
3. planner
4. memoria relevante
5. workspace/fontes
6. RAG legado
7. mensagem atual

## Memoria e RAG
### Camadas
- transcript bruto em JSONL
- resumo estruturado
- estado de compactacao
- fila de revisao
- memoria duravel
- indice vetorial `orquestra_memory_v1`
- projecao em arquivos `memdir`

### Tipos de memoria
- `user`
- `feedback`
- `project`
- `reference`
- `persona`
- `dataset`

### Escopos relevantes
- `session_memory`
- `episodic_memory`
- `semantic_memory`
- `workspace_memory`
- `persona_memory`
- `source_fact`
- `training_signal`

### Pipeline de aprovacao
Ao aprovar um `MemoryReviewCandidate`, o sistema cria:
1. `MemoryRecord`
2. projecao em arquivo
3. indexacao em `orquestra_memory_v1`

### Politica de resiliencia
- falha de embedding nao quebra chat
- falha do backend vetorial nao quebra recall
- fallback lexical continua disponivel

## Planner hibrido
### Entidades
- `PlannerSnapshot`
- `SessionTask`

### Recursos
- `next_steps` reais
- estrategia e riscos
- tarefas persistidas
- dependencias por `blocked_by` e `blocks`
- visibilidade na UI lateral do chat

## Executor local multi-step
### Entidades
- `WorkflowRun`
- `WorkflowStepRun`

### Passos suportados
- `ops_action`
- `rag_query`
- `workspace_query`
- `workspace_extract`
- `memory_review_batch`
- `shell_safe`

### Garantias operacionais
- progresso por passo
- cancelamento
- logs persistidos
- `output_path`
- `output_preview`
- saida parcial em falha
- recuperacao apos restart
- vinculo com sessao e tarefa

## Workspace multimodal
### Politica
- inventario primeiro
- extracao pesada depois
- ranking por metadado + conteudo quando aplicavel
- degradacao lexical quando vetor falha

### Tipos de ativo
- `code_text`
- `image`
- `pdf`
- `office`
- `audio`
- `video`
- `binary`

## Runtime e distribuicao
### Enderecos locais
- API: `http://127.0.0.1:8808`
- Web: `http://127.0.0.1:4177`

### Artefatos macOS
- `Orquestra AI.app`
- `Orquestra AI_0.2.0_aarch64.dmg`

### Instalacao
- `scripts/install_orquestra_macos.sh`
- `scripts/uninstall_orquestra_macos.sh`
- LaunchAgent `ai.orquestra.api`
- runtime em `~/Library/Application Support/Orquestra/runtime`

## API publica agrupada por dominio
### Saude e operacao
- `GET /api/health`
- `GET /api/ops/dashboard`
- `GET /api/ops/actions`
- `GET /api/ops/runs`
- `GET /api/ops/runs/{run_id}`
- `POST /api/ops/runs`

### Workflows
- `GET /api/workflows/runs`
- `GET /api/workflows/runs/{run_id}`
- `POST /api/workflows/runs`
- `POST /api/workflows/runs/{run_id}/cancel`

### Train Plane remoto via Orquestra local
- `GET /api/remote/trainplane/config`
- `PUT /api/remote/trainplane/config`
- `POST /api/remote/trainplane/test-connection`
- `GET /api/remote/trainplane/base-models`
- `POST /api/remote/trainplane/sync/base-model`
- `GET /api/remote/trainplane/dataset-bundles`
- `POST /api/remote/trainplane/sync/dataset-bundle`
- `GET /api/remote/trainplane/runs`
- `POST /api/remote/trainplane/runs`
- `GET /api/remote/trainplane/runs/{run_id}`
- `POST /api/remote/trainplane/runs/{run_id}/cancel`
- `GET /api/remote/trainplane/runs/{run_id}/stream`
- `GET /api/remote/trainplane/artifacts`
- `POST /api/remote/trainplane/artifacts/{artifact_id}/merge`
- `POST /api/remote/trainplane/artifacts/{artifact_id}/promote`
- `GET /api/remote/trainplane/evaluations`
- `POST /api/remote/trainplane/evaluations`
- `GET /api/remote/trainplane/comparisons`
- `POST /api/remote/trainplane/comparisons`

### API publica do servico remoto `orquestra_trainplane`
- `POST /api/auth/bootstrap`
- `POST /api/auth/login`
- `POST /api/base-models/upload/init`
- `POST /api/base-models/upload/complete`
- `GET /api/base-models`
- `POST /api/dataset-bundles`
- `GET /api/dataset-bundles`
- `POST /api/training-runs`
- `GET /api/training-runs`
- `GET /api/training-runs/{run_id}`
- `POST /api/training-runs/{run_id}/cancel`
- `GET /api/training-runs/{run_id}/events`
- `GET /api/artifacts`
- `POST /api/artifacts/{artifact_id}/merge`
- `POST /api/artifacts/{artifact_id}/promote`
- `POST /api/evaluation-runs`
- `GET /api/evaluation-runs`
- `GET /api/evaluation-runs/{run_id}`
- `POST /api/comparison-runs`
- `GET /api/comparison-runs`
- `GET /api/comparison-runs/{run_id}`

### Providers, modelos e projetos
- `GET /api/providers`
- `PUT /api/providers`
- `GET /api/models`
- `GET /api/connectors`
- `GET /api/projects`
- `POST /api/projects`
- `POST /api/projects/{project_id}/deployments`

### Chat e sessao
- `POST /api/chat/sessions`
- `GET /api/chat/sessions`
- `GET /api/chat/sessions/{session_id}/profile`
- `PUT /api/chat/sessions/{session_id}/profile`
- `GET /api/chat/sessions/{session_id}/messages`
- `POST /api/chat/sessions/{session_id}/resume`
- `GET /api/chat/sessions/{session_id}/transcript`
- `GET /api/chat/sessions/{session_id}/summary`
- `POST /api/chat/sessions/{session_id}/compact`
- `GET /api/chat/sessions/{session_id}/planner`
- `POST /api/chat/sessions/{session_id}/planner/rebuild`
- `GET /api/chat/sessions/{session_id}/tasks`
- `POST /api/chat/sessions/{session_id}/tasks`
- `PATCH /api/chat/sessions/{session_id}/tasks`
- `GET /api/tasks/{task_id}`
- `POST /api/chat/stream`

### Memoria
- `GET /api/memory`
- `POST /api/memory/upsert`
- `GET /api/memory/topics`
- `POST /api/memory/recall`
- `POST /api/memory/promote`
- `GET /api/memory/candidates`
- `POST /api/memory/candidates/{candidate_id}/approve`
- `POST /api/memory/candidates/{candidate_id}/reject`
- `GET /api/memory/training-candidates`
- `POST /api/memory/training-candidates`

### RAG
- `POST /api/rag/query`

### Workspace
- `GET /api/workspace/scans`
- `POST /api/workspace/attach-directory`
- `GET /api/workspace/scans/{scan_id}`
- `GET /api/workspace/assets`
- `POST /api/workspace/query`
- `POST /api/workspace/assets/{asset_id}/extract`
- `GET /api/workspace/assets/{asset_id}/preview`
- `POST /api/workspace/assets/{asset_id}/open`
- `POST /api/workspace/assets/{asset_id}/memorize`

### Jobs e registry
- `GET /api/training/jobs`
- `POST /api/training/jobs`
- `GET /api/remote/jobs`
- `POST /api/remote/jobs`
- `GET /api/remote/jobs/{job_id}/logs`
- `GET /api/registry/models`
- `POST /api/registry/models`
- `POST /api/registry/compare`

## Checkpoint e retomada
O repositório usa um handoff versionado:
- arquivo canonico: `.codex/memory/orquestra-continuity.md`
- espelho humano: `docs/continuity/orquestra-current.md`

Fluxo por etapa:
1. atualizar handoff
2. validar a etapa
3. rodar `git diff --check`
4. registrar `git status --short`
5. commit
6. push

## Limites atuais
- conectores remotos ainda nao executam treino real
- EC2 continua fora desta fase
- distribuicao publica notarizada ainda nao esta fechada
