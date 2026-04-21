# Orquestra AI Control Plane

## Objetivo

Este documento descreve a arquitetura operacional do Orquestra como control plane local-first para:

- chat multi-provider
- memoria persistente e memoria operacional
- RAG contextual
- investigacao OSINT
- leitura multimodal de diretorios
- planner de sessao
- workflows locais multi-step
- registro de modelos, jobs, artifacts e comparacoes

## Dominios principais

### Backend local

Arquivos centrais:

- `orquestra_ai/app.py`
- `orquestra_ai/services.py`
- `orquestra_ai/models.py`

Responsabilidades:

- servir a API
- coordenar chat, memoria, planner, workflow, workspace e OSINT
- expor dashboard, saude e contratos publicos
- atuar como proxy para o `Remote Train Plane`

### Gateway de modelos

Arquivo:

- `orquestra_ai/gateway.py`

Providers suportados:

- `lmstudio`
- `openai`
- `anthropic`
- `deepseek`
- `ollama`
- `litellm`

### Memoria e contexto

Arquivos:

- `orquestra_ai/memory_graph.py`
- `orquestra_ai/memory_recall.py`
- `orquestra_ai/rag_memory.py`
- `orquestra_ai/session_profile.py`
- `orquestra_ai/memory_candidates.py`

### Planner e workflow

Arquivos:

- `orquestra_ai/planner.py`
- `orquestra_ai/workflow_engine.py`
- `orquestra_ai/operations.py`

### OSINT

Arquivo:

- `orquestra_ai/osint.py`

### Workspace

Arquivo:

- `orquestra_ai/workspace.py`

### Frontend e desktop

Arquivos:

- `orquestra_web/src/App.tsx`
- `orquestra_web/src/api.ts`
- `orquestra_web/src-tauri/`

### Train Plane remoto

Arquivos:

- `orquestra_trainplane/app.py`
- `orquestra_trainplane/worker.py`
- `orquestra_trainplane/models.py`
- `orquestra_trainplane/services.py`

## Superficies oficiais de produto

1. `Operations Dashboard`
2. `Process Center`
3. `Memory Studio`
4. `Execution Center`
5. `Assistant Workspace`
6. `OSINT Lab`
7. `Workspace Browser`
8. `Projects`

## Modelo operacional de sessao

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

Os contratos de `POST /api/chat/stream` e `POST /api/rag/query` ja tem semantica operacional real:

- `planner_enabled`
- `memory_selector_mode`
- `include_workspace`
- `include_sources`
- `include_osint_evidence`
- `compaction_enabled`
- `task_context_enabled`
- `context_budget`

No `chat/stream`, tambem existem:

- `osint_mode`
- `fresh_web_enabled`
- `evidence_enabled`
- `source_registry_ids`
- `enabled_connector_ids`
- `via_tor`

## Ordem fixa de contexto

1. perfil da sessao
2. snapshot compacto
3. planner
4. memoria relevante
5. OSINT evidence
6. workspace/fontes
7. RAG legado
8. mensagem atual

## Memoria e RAG

### Camadas

- transcript bruto
- resumo estruturado
- estado de compactacao
- fila de revisao
- memoria duravel
- indice vetorial `orquestra_memory_v1`
- projecao em arquivos `memdir`
- indice vetorial `orquestra_osint_evidence_v1`

### Pipeline de aprovacao

Ao aprovar um `MemoryReviewCandidate`, o sistema cria:

1. `MemoryRecord`
2. projecao em arquivo
3. indexacao em `orquestra_memory_v1`

Quando a origem vem do `OSINT Lab`, a memoria tambem preserva:

- `citations`
- `source_url`
- `claim_id`
- `capture_id`
- `evidence_ids`
- `validation_status`

## OSINT Lab

### Entidades

- `OsintConnectorConfig`
- `OsintSourceRegistryEntry`
- `OsintInvestigation`
- `OsintRun`
- `OsintSource`
- `OsintCapture`
- `OsintEvidence`
- `OsintClaim`
- `OsintEntity`

### Fluxo

1. criar investigacao
2. selecionar conectores
3. planejar queries
4. buscar fontes
5. fazer fetch
6. aprovar evidencias
7. aprovar claims
8. promover memoria ou exportar bundle

### Conectores administraveis

O control plane permite:

- ligar/desligar globalmente
- ligar/desligar por investigacao
- acompanhar `credential_status`
- acompanhar `health_status`
- aplicar `retention_policy`

## Planner hibrido

### Entidades

- `PlannerSnapshot`
- `SessionTask`

### Recursos

- `next_steps` reais
- estrategia e riscos
- tarefas persistidas
- dependencias `blocked_by` e `blocks`
- visibilidade lateral no chat

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

### Garantias

- progresso por passo
- cancelamento
- logs persistidos
- `output_path`
- `output_preview`
- saida parcial em falha
- recovery apos restart
- vinculo com sessao e tarefa

## Workspace multimodal

### Politica

- inventario primeiro
- extracao depois
- ranking por metadado e conteudo
- degradacao lexical quando vetor falha

### Tipos de ativo

- `code_text`
- `image`
- `pdf`
- `office`
- `audio`
- `video`
- `binary`

## Remote Train Plane

O Orquestra local atua como cliente completo do servico remoto.

### Fluxo suportado

1. configurar endpoint e credenciais
2. testar conexao
3. sincronizar `base models`
4. sincronizar `dataset bundles`
5. criar `training runs`
6. acompanhar eventos e metrics
7. revisar `artifacts`, `evaluations` e `comparisons`
8. promover artefatos

### Status atual

- a superficie operacional e os contratos ja existem
- o modo atual ainda e de validacao/operacao local-remota controlada
- a fase AWS real continua para a proxima etapa

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

### Sessoes, planner e tarefas

- `POST /api/chat/sessions`
- `GET /api/chat/sessions`
- `GET /api/chat/sessions/{id}/profile`
- `PUT /api/chat/sessions/{id}/profile`
- `GET /api/chat/sessions/{id}/summary`
- `POST /api/chat/sessions/{id}/compact`
- `GET /api/chat/sessions/{id}/planner`
- `POST /api/chat/sessions/{id}/planner/rebuild`
- `GET/POST /api/chat/sessions/{id}/tasks`
- `PATCH /api/chat/sessions/{id}/tasks`
- `GET /api/tasks/{task_id}`
- `POST /api/chat/stream`

### Memoria

- `GET /api/memory`
- `POST /api/memory/upsert`
- `GET /api/memory/topics`
- `POST /api/memory/recall`
- `POST /api/memory/promote`
- `GET /api/memory/candidates`
- `POST /api/memory/candidates/{id}/approve`
- `POST /api/memory/candidates/{id}/reject`
- `GET /api/memory/training-candidates`
- `POST /api/memory/training-candidates`

### RAG

- `POST /api/rag/query`

### OSINT

- `GET/PUT /api/osint/config`
- `GET /api/osint/providers`
- `GET /api/osint/connectors`
- `PATCH /api/osint/connectors/{id}`
- `POST /api/osint/connectors/{id}/enable`
- `POST /api/osint/connectors/{id}/disable`
- `GET /api/osint/source-registry`
- `POST /api/osint/source-registry`
- `PATCH /api/osint/source-registry/{id}`
- `GET/POST /api/osint/investigations`
- `PATCH /api/osint/investigations/{id}`
- `POST /api/osint/investigations/{id}/plan`
- `POST /api/osint/investigations/{id}/search`
- `POST /api/osint/investigations/{id}/fetch`
- `POST /api/osint/investigations/{id}/crawl`
- `GET /api/osint/investigations/{id}/runs`
- `GET /api/osint/evidence`
- `POST /api/osint/evidence/{id}/approve`
- `GET /api/osint/claims`
- `POST /api/osint/claims/{id}/approve`
- `POST /api/osint/export/dataset-bundle`

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

### Remote Train Plane via proxy local

- `GET/PUT /api/remote/trainplane/config`
- `POST /api/remote/trainplane/test-connection`
- `GET /api/remote/trainplane/base-models`
- `POST /api/remote/trainplane/sync/base-model`
- `GET /api/remote/trainplane/dataset-bundles`
- `POST /api/remote/trainplane/sync/dataset-bundle`
- `GET/POST /api/remote/trainplane/runs`
- `GET /api/remote/trainplane/runs/{id}`
- `POST /api/remote/trainplane/runs/{id}/cancel`
- `GET /api/remote/trainplane/runs/{id}/stream`
- `GET /api/remote/trainplane/artifacts`
- `POST /api/remote/trainplane/artifacts/{id}/merge`
- `POST /api/remote/trainplane/artifacts/{id}/promote`
- `GET/POST /api/remote/trainplane/evaluations`
- `GET/POST /api/remote/trainplane/comparisons`

## Runtime e distribuicao

### Enderecos locais

- API: `http://127.0.0.1:8808`
- Web: `http://127.0.0.1:4177`

### Instalacao

- `scripts/install_orquestra_macos.sh`
- `scripts/uninstall_orquestra_macos.sh`
- LaunchAgent `ai.orquestra.api`
- runtime em `~/Library/Application Support/Orquestra/runtime`
