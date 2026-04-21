# Orquestra V2: MemoryGraph, Workspace e Runtime

## Objetivo

Este documento descreve a camada tecnica que sustenta:

- memoria persistente e memoria operacional
- compactacao de contexto
- planner de sessao
- execucao local multi-step
- leitura multimodal de diretorios
- OSINT associado a memoria e RAG
- runtime local do app

## Blocos tecnicos

### Control plane

- `orquestra_ai/app.py`
- `orquestra_ai/services.py`
- `orquestra_ai/models.py`

### MemoryGraph

- `orquestra_ai/memory_graph.py`
- `orquestra_ai/memory_recall.py`
- `orquestra_ai/rag_memory.py`
- `orquestra_ai/session_profile.py`
- `orquestra_ai/memory_candidates.py`

### Planner e workflow

- `orquestra_ai/planner.py`
- `orquestra_ai/workflow_engine.py`
- `orquestra_ai/operations.py`

### OSINT

- `orquestra_ai/osint.py`

### Workspace

- `orquestra_ai/workspace.py`

### Desktop

- `orquestra_web/src-tauri/`

## MemoryGraph V2

### Camadas persistidas

1. `raw_transcript`
2. `session_summary`
3. `session_compaction_state`
4. `session_profile`
5. `memory_review_candidates`
6. `durable_memory`
7. `rag_memory_index`
8. `planner_snapshot_and_tasks`
9. `workflow_runs`
10. `training_candidates`
11. `osint_investigations_and_evidence`

### Session Profile

Cada sessao guarda em `metadata_json`:

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

### Memory kinds

- `user`
- `feedback`
- `project`
- `reference`
- `persona`
- `dataset`

### Escopos

- `session_memory`
- `episodic_memory`
- `semantic_memory`
- `workspace_memory`
- `persona_memory`
- `source_fact`
- `training_signal`

## Memoria associada ao RAG

### Backends

- SQLite como base estruturada
- `memdir` como projecao em arquivos
- `orquestra_memory_v1` como indice vetorial principal
- `orquestra_osint_evidence_v1` como indice vetorial de evidencias OSINT

### Destinos apos aprovacao

Ao aprovar um candidato, o Orquestra materializa:

1. banco local
2. arquivo projetado
3. indice vetorial

Quando a origem e `OSINT`, a proveniencia tambem fica em:

- `MemoryRecord.metadata_json`
- projecao em arquivo
- metadata do chunk vetorial

Campos importantes preservados:

- `citations`
- `source_url`
- `claim_id`
- `capture_id`
- `evidence_ids`
- `validation_status`
- `license_policy`

### Estrutura do memdir

- `experiments/orquestra/memorygraph/memdir/global`
- `experiments/orquestra/memorygraph/memdir/projects/<slug>`
- `experiments/orquestra/memorygraph/memdir/sessions/<session_id>`

## Recall de memoria

O `MemoryRecallService` opera com duas estrategias:

### `hybrid`

- shortlist lexical
- reforco vetorial
- merge por score
- fallback operacional quando vetor indisponivel

### `lexical`

- usa apenas shortlist lexical
- evita dependencia vetorial

## Compactacao de contexto

### Estado persistido

`SessionCompactionState` guarda:

- `last_compacted_message_id`
- `summary_version`
- `next_steps`
- `preserved_recent_turns`
- `compacted_message_count`
- `compacted_at`

### Conteudo preservado

O snapshot operacional preserva:

- `objective`
- `current_state`
- `task_specification`
- `decisions`
- `open_questions`
- `next_steps`
- `worklog`
- `recent_failures`

### Regra de montagem

O contexto agregado usa:

1. perfil da sessao
2. snapshot compacto
3. planner
4. memoria
5. OSINT evidence
6. workspace/fontes
7. RAG legado
8. mensagem atual

## OSINT nativo na camada de memoria

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

### Garantias operacionais

- conectores seedados no bootstrap
- configuracao persistida em `RuntimeMetadata`
- busca e fetch nativos sem depender apenas do provider do chat
- aprovacao de claim promovendo memoria rastreavel
- export local de dataset apenas para claims aprovadas

### Estrutura em disco

- `experiments/orquestra/osint/investigations/<id>/sources`
- `experiments/orquestra/osint/investigations/<id>/captures`
- `experiments/orquestra/osint/investigations/<id>/evidence`
- `experiments/orquestra/osint/investigations/<id>/claims`
- `experiments/orquestra/osint/investigations/<id>/exports`

### Papel do OSINT no contexto

`OsintEvidence` nao substitui memoria duravel. O papel dela e:

- sustentar a resposta atual
- enriquecer o `rag/query`
- permitir revisao antes de promocao

Memoria duravel entra somente depois de aprovacao.

## Planner hibrido

### Entidades

- `PlannerSnapshot`
- `SessionTask`

### Atributos relevantes de `SessionTask`

- `subject`
- `description`
- `active_form`
- `status`
- `owner`
- `blocked_by`
- `blocks`
- `position`
- `metadata`

### Estados

- `pending`
- `in_progress`
- `blocked`
- `completed`
- `failed`
- `cancelled`

### Regras

- planner e operacional, nao memoria duravel
- tarefas duplicadas devem ser evitadas
- dependencias precisam sobreviver a reload e restart

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
- logs persistidos
- `output_path`
- `output_preview`
- cancelamento
- saida parcial em falha
- recovery apos restart
- vinculo com sessao e tarefa

### Estados finais esperados

- `succeeded`
- `failed`
- `cancelled`
- `interrupted`

## Workspace multimodal

### Fluxo

1. anexar diretorio
2. gerar inventario
3. ranquear ativos
4. extrair sob demanda
5. responder com citacoes operacionais
6. promover ativo para memoria quando necessario

### Tipos de ativo

- `code_text`
- `image`
- `pdf`
- `office`
- `audio`
- `video`
- `binary`

### Politica

- inventario primeiro
- derivado pequeno quando necessario
- extracao pesada apenas sob demanda
- fallback lexical quando vetor nao puder ser usado

## Runtime local

### Caminhos principais

- `experiments/orquestra/memorygraph`
- `experiments/orquestra/workspace`
- `experiments/orquestra/workflows`
- `experiments/orquestra/operations`
- `experiments/orquestra/rag_runtime`
- `experiments/orquestra/osint`

### Runtime instalado

Quando o app e instalado, o runtime operacional passa a viver em:

- `~/Library/Application Support/Orquestra/runtime`

### Bootstrap e shutdown

O FastAPI usa `lifespan` para:

- bootstrap do banco
- seed de conectores e runtime metadata
- preparacao dos servicos locais
- encerramento limpo do app
