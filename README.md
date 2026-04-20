# Orquestra

![Orquestra AI](assets/brand/orquestra-wordmark.svg)

`Orquestra` e um control plane macOS-first e local-first para operacao de IA. A aplicacao unifica chat multi-provider, memoria persistente, RAG contextual, leitura multimodal de diretorios, planner de sessao, workflows locais multi-step, dashboard operacional e empacotamento desktop/web em uma unica superficie.

## O que o Orquestra entrega hoje
- `Assistant Workspace` com setup de sessao por objetivo, preset e politicas de memoria/RAG.
- `Memory Studio` com memoria hibrida, `Memory Inbox`, recall lexical + vetorial e projecao em arquivos.
- `Workspace Browser` com leitura `inventory-first` e extracao sob demanda.
- `Execution Center` com providers, jobs, workflows locais, registry e consulta RAG operacional.
- `Operations Dashboard` e `Process Center` para saude da stack, listeners, processos e artefatos.
- app desktop macOS com instalador, desinstalador, runtime espelhado e LaunchAgent local.

## Visao geral do produto
O Orquestra transforma o Mac em uma estacao de coordenacao de projetos de IA. Em vez de depender de um transcript bruto gigante ou de scripts soltos, ele organiza:

- sessao de trabalho com objetivo explicito;
- memoria duravel aprovada e memoria curta operacional;
- compactacao persistente para chats longos;
- tarefas reais da sessao com proximos passos;
- workflows locais observaveis com logs e artefatos;
- consulta a fontes locais, workspace e RAG legado sem quebrar o fluxo local.

Principios do projeto:
- `local-first`: banco, memoria, artefatos, runtime e validacao rodam localmente por padrao.
- `macOS-first`: a distribuicao oficial atual e app Tauri + scripts de instalacao/desinstalacao.
- `web + desktop`: a mesma UI React/Vite funciona no navegador e no app.
- `provider-agnostic`: o gateway suporta LM Studio, OpenAI, Anthropic, DeepSeek, Ollama e LiteLLM.
- `review-before-promote`: nada vira memoria duravel ou dataset sem aprovacao explicita.
- `inventory-first`: o workspace inventaria antes; extracao pesada so acontece quando faz sentido.

## Superficie atual da UI
As areas oficiais do produto sao:

1. `Operations Dashboard`
2. `Process Center`
3. `Memory Studio`
4. `Execution Center`
5. `Assistant Workspace`
6. `Workspace Browser`
7. `Projects`

Dentro dessas areas, o Orquestra expõe os blocos abaixo.

### Assistant Workspace
- cria sessoes com `objective`, `preset`, `memory_policy`, `rag_policy` e `persona_config`
- separa transcript bruto, resumo operacional e estado de compactacao
- usa `summary + recent tail + recalled memory + workspace/fontes` em vez de transcript integral
- mostra `Memory Inbox`, resumo, transcript, planner e contexto operacional na mesma tela
- atualiza `next_steps` reais a partir do planner

Presets suportados:
- `research`
- `osint`
- `persona`
- `assistant`
- `dataset`

### Memory Studio
- `MemoryRecord`, `MemoryTopic` e `MemoryReviewCandidate`
- tipos de memoria: `user`, `feedback`, `project`, `reference`, `persona`, `dataset`
- escopos operacionais: `session_memory`, `episodic_memory`, `semantic_memory`, `workspace_memory`, `persona_memory`, `source_fact`, `training_signal`
- recall com `memory_selector_mode=hybrid` ou `memory_selector_mode=lexical`
- projecao em arquivos sob `experiments/orquestra/memorygraph/memdir`

### Workspace Browser
- anexo de diretorios
- inventario recursivo com classificacao por ativo
- extracao sob demanda para `code_text`, `image`, `pdf`, `office`, `audio`, `video` e `binary`
- preview, abertura no app padrao e promocao de ativos para memoria

### Execution Center
- providers e modelos disponiveis
- catalogo de conectores e jobs
- `WorkflowRun` e `WorkflowStepRun`
- progresso por passo
- `log_path`, `output_path` e `output_preview`
- estados finais claros: `succeeded`, `failed`, `cancelled`, `interrupted`
- recuperacao visual apos restart quando um run interrompido e reclassificado
- comparacao de registry e consulta RAG operacional

### Operations Dashboard e Process Center
- saude da API, web, desktop, bundle e artefatos
- listeners locais
- processos de background
- sessoes recentes
- scans de workspace
- memoria recente e pendencias do inbox
- caminhos de runtime e estado de instalacao

## Memoria, RAG, planner e workflow
Os recursos de maior impacto operacional do Orquestra hoje sao:

### Memoria hibrida
- banco local SQLite como base canônica
- projecao em arquivos Markdown/metadata no `memdir`
- colecao `orquestra_memory_v1` para memoria aprovada associada ao RAG
- fallback heuristico quando vetor/embeddings nao estao disponiveis

### Compactacao de contexto
- `SessionCompactionState` persistido por sessao
- separacao entre transcript bruto e snapshot compacto
- preservacao de `next_steps`, decisoes, worklog e falhas recentes
- acionamento manual e automatico por `context_budget`

### Planner hibrido
- `PlannerSnapshot` persistido por sessao
- `SessionTask` com dependencias `blocked_by` e `blocks`
- tarefas visiveis e editaveis na UI
- sincronizacao com objetivo e resumo da sessao

### Executor local multi-step
- passos suportados: `ops_action`, `rag_query`, `workspace_query`, `workspace_extract`, `memory_review_batch`, `shell_safe`
- cancelamento real
- saida parcial em falha
- retomada visual apos restart
- vinculo opcional entre workflow, sessao e tarefa

## Contratos publicos importantes
Algumas flags de contexto agora tem comportamento real no backend:

- `planner_enabled`
- `memory_selector_mode`
- `include_workspace`
- `include_sources`
- `compaction_enabled`
- `context_budget`

Ordem fixa de montagem de contexto:
1. perfil da sessao
2. snapshot compacto
3. planner
4. memoria relevante
5. workspace/fontes
6. RAG legado
7. mensagem atual

## Estrutura do repositório
- `orquestra_ai/`: API FastAPI, gateway, memoria, planner, workflows, jobs e runtime
- `orquestra_web/`: frontend React/Vite e shell desktop Tauri
- `rag/`: engine RAG integrado ao backend
- `training/local/`: utilitarios locais de treino/avaliacao
- `scripts/`: bootstrap, run, validacao, empacotamento, instalacao e desinstalacao
- `assets/brand/`: logo e wordmark
- `docs/`: instalacao, manual, arquitetura, memoria/workspace e continuidade

## Inicio rapido
```bash
cd /caminho/para/Orquestra
./scripts/bootstrap_orquestra.sh
./scripts/validate_orquestra.sh
```

Subir a API:
```bash
./scripts/start_orquestra_api.sh
```

Subir a UI web:
```bash
./scripts/start_orquestra_web.sh
```

Subir a stack local:
```bash
./scripts/start_orquestra_stack.sh
```

Abrir o desktop:
```bash
./scripts/start_orquestra_desktop.sh
```

Build + verificacao do desktop:
```bash
./script/build_and_run.sh --verify
```

## Instalacao no macOS
Instalar:
```bash
./scripts/install_orquestra_macos.sh
```

Desinstalar:
```bash
./scripts/uninstall_orquestra_macos.sh
```

O instalador atual:
- instala `Orquestra AI.app` em `~/Applications`
- espelha o runtime em `~/Library/Application Support/Orquestra/runtime`
- registra o LaunchAgent `ai.orquestra.api`
- cria manifesto e backups de upgrade do banco

## Validacao oficial
O comando oficial de validacao e:

```bash
./scripts/validate_orquestra.sh
```

Ele executa:
- `py_compile`
- `pytest -q`
- `bash -n` nos scripts
- `vitest`
- `tsc -b`
- `vite build`
- `cargo check`
- validacao do pacote macOS quando `.app` e `.dmg` existem
- smoke da API cobrindo sessao, memoria, compactacao, planner, workflow, workspace e RAG

## Checkpoint e retomada
O protocolo de continuidade do repositório foi reduzido para quatro fontes curtas:

- `AGENTS.md`
- `.codex/memory/orquestra-continuity.md`
- `git log --oneline -5`
- `git status --short`

Prompt curto recomendado para retomar sem reler toda a thread:

```text
Leia AGENTS.md, .codex/memory/orquestra-continuity.md, git log --oneline -5 e git status --short. Continue a implementacao a partir da Proxima acao exata, sem reanalisar todo o projeto.
```

## Estado atual da entrega
- backend, frontend web e desktop estao integros no fluxo local
- memoria hibrida, compactacao, planner e workflows locais ja estao implementados
- a documentacao operacional ja cobre instalacao, uso, arquitetura e continuidade
- a validacao principal esta verde no branch de trabalho

Limites atuais:
- conectores remotos ainda operam como catalogo/intencao, sem execucao remota real
- EC2 continua adiado para o proximo ciclo
- distribuicao publica ainda nao usa assinatura/notarizacao final

## Documentacao
- [Instalacao e validacao macOS](docs/01-instalacao-validacao-macos.md)
- [Manual operacional](docs/02-manual-operacional.md)
- [Control plane e APIs](docs/11-orquestra-ai-control-plane.md)
- [MemoryGraph, Workspace e runtime](docs/12-orquestra-v2-memorygraph-workspace.md)
- [Checkpoint e retomada](docs/continuity/orquestra-current.md)

## Seguranca
- nunca versione segredos, chaves privadas ou credenciais reais
- prefira `.env` local e providers mock/local-safe para validacao
- nao promova dataset sem aprovacao explicita
- mantenha o fluxo local-first como padrao operacional
