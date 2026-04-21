# Orquestra

![Orquestra AI](assets/brand/orquestra-wordmark.svg)

`Orquestra` e um control plane `macOS-first` e `local-first` para operacao de IA. A aplicacao combina chat multi-provider, memoria persistente, RAG contextual, investigacao OSINT, leitura multimodal de diretorios, planner de sessao, workflows locais multi-step e um painel remoto de treino/comparacao de modelos.

## Estado atual do produto
Hoje o Orquestra entrega:

- `Assistant Workspace` com setup de sessao por objetivo, preset e politicas de memoria/RAG.
- `Memory Studio` com memoria hibrida, inbox de revisao, recall lexical + vetorial e projecao em arquivos.
- `OSINT Lab` com busca web nativa, conectores administraveis, source registry, evidencias, claims e promocao rastreavel para memoria.
- `Workspace Browser` com leitura `inventory-first` e extracao multimodal sob demanda.
- `Execution Center` com workflows, registry, consulta RAG, conectores e o painel `Remote Train Plane`.
- `Operations Dashboard` e `Process Center` para saude da stack, artefatos, runtime e observabilidade local.
- app desktop macOS com instalador, desinstalador, runtime espelhado e LaunchAgent local.
- servico remoto dedicado `orquestra_trainplane` para treino `adapter-first`, artifacts, avaliacoes e comparacoes.

## Principios operacionais

- `local-first`: a operacao principal continua funcional sem servicos remotos obrigatorios.
- `macOS-first`: o fluxo oficial de desktop, instalacao e runtime foi pensado primeiro para macOS.
- `review-before-promote`: memoria duravel e dataset exigem aprovacao explicita.
- `inventory-first`: o workspace indexa antes e extrai conteudo pesado apenas quando necessario.
- `graceful degradation`: falha de embeddings, vetor ou provider nao deve quebrar o fluxo principal.
- `single control plane`: chat, memoria, RAG, OSINT, workflow e treino compartilham o mesmo contexto operacional.

## Mapa da documentacao

- [docs/00-guia-da-documentacao.md](docs/00-guia-da-documentacao.md): indice da documentacao e trilhas de leitura.
- [docs/01-instalacao-validacao-macos.md](docs/01-instalacao-validacao-macos.md): bootstrap, execucao, instalacao, validacao e troubleshooting no macOS.
- [docs/02-manual-operacional.md](docs/02-manual-operacional.md): manual de uso completo da aplicacao.
- [docs/03-osint-lab.md](docs/03-osint-lab.md): operacao detalhada do `OSINT Lab`.
- [docs/04-train-plane.md](docs/04-train-plane.md): uso do `Remote Train Plane` e fluxo de treino/comparacao.
- [docs/11-orquestra-ai-control-plane.md](docs/11-orquestra-ai-control-plane.md): arquitetura do control plane, dominios e APIs.
- [docs/12-orquestra-v2-memorygraph-workspace.md](docs/12-orquestra-v2-memorygraph-workspace.md): memoria, contexto, workspace, runtime e OSINT tecnico.
- [docs/continuity/orquestra-current.md](docs/continuity/orquestra-current.md): protocolo de checkpoint e retomada com baixo uso de contexto.

## Superficie atual da UI

As areas oficiais do produto sao:

1. `Operations Dashboard`
2. `Process Center`
3. `Memory Studio`
4. `Execution Center`
5. `Assistant Workspace`
6. `OSINT Lab`
7. `Workspace Browser`
8. `Projects`

## Inicio rapido

Bootstrap do repositório:

```bash
cd /caminho/para/Orquestra
./scripts/bootstrap_orquestra.sh
```

Validacao oficial:

```bash
./scripts/validate_orquestra.sh
```

Subir a API:

```bash
./scripts/start_orquestra_api.sh
```

Subir a interface web:

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

Subir o Train Plane local/simulado:

```bash
./scripts/start_orquestra_trainplane.sh
```

## Fluxo operacional recomendado

1. Crie ou selecione um projeto em `Projects`.
2. Abra `Assistant Workspace` e inicie uma sessao com `objective` e `preset`.
3. Converse usando memoria, planner e RAG de forma seletiva.
4. Revise o `Memory Inbox` antes de promover memoria duravel.
5. Use `Workspace Browser` para anexar diretorios e extrair contexto local.
6. Use `OSINT Lab` para investigacoes web com evidencias e claims.
7. Use `Execution Center` para workflows, RAG operacional, registry e Train Plane.
8. Compacte sessoes longas e reconstrua o planner quando a estrategia mudar.

## Recursos principais

### Assistant Workspace

- setup de sessao com `objective`, `preset`, `memory_policy`, `rag_policy` e `persona_config`
- transcript bruto separado do snapshot operacional
- compactacao persistente com `SessionCompactionState`
- `Memory Inbox`
- planner hibrido com `next_steps` reais
- uso de `summary + recent tail + recalled memory + OSINT evidence + workspace/fontes`

Presets suportados:

- `research`
- `osint`
- `persona`
- `assistant`
- `dataset`

### Memory Studio

- `MemoryReviewCandidate`, `MemoryRecord`, `MemoryTopic`
- tipos de memoria: `user`, `feedback`, `project`, `reference`, `persona`, `dataset`
- escopos: `session_memory`, `episodic_memory`, `semantic_memory`, `workspace_memory`, `persona_memory`, `source_fact`, `training_signal`
- recall com `memory_selector_mode=hybrid` ou `memory_selector_mode=lexical`
- projecao em `experiments/orquestra/memorygraph/memdir`

### OSINT Lab

- investigacoes com objetivo, entidade-alvo, idioma e jurisdicao
- conectores administraveis com ligar/desligar global e por investigacao
- `Source Registry` com seeds e politicas
- evidencias e claims aprovaveis
- promocao rastreavel de claim para memoria
- export de dataset apenas para conteudo aprovado

### Workspace Browser

- attach de diretorios locais
- inventario recursivo
- ranking de ativos
- extracao sob demanda de `code_text`, `image`, `pdf`, `office`, `audio`, `video` e `binary`
- promocao de ativos para memoria

### Execution Center

- providers e modelos
- acoes operacionais
- `WorkflowRun` e `WorkflowStepRun`
- logs, `output_path`, `output_preview` e estados finais claros
- consulta RAG operacional
- resumo do `OSINT Connector Hub`
- `Remote Train Plane` com configuracao, sync, runs, artifacts, comparacoes e avaliacoes

## Ordem real de montagem de contexto

O backend usa a seguinte ordem:

1. perfil da sessao
2. snapshot compacto
3. planner
4. memoria relevante
5. OSINT evidence
6. workspace/fontes
7. RAG legado
8. mensagem atual

Flags que ja tem semantica operacional real:

- `planner_enabled`
- `memory_selector_mode`
- `include_workspace`
- `include_sources`
- `include_osint_evidence`
- `compaction_enabled`
- `task_context_enabled`
- `context_budget`

## Instalacao no macOS

Instalar:

```bash
./scripts/install_orquestra_macos.sh
```

Desinstalar:

```bash
./scripts/uninstall_orquestra_macos.sh
```

Guia completo:

- [docs/01-instalacao-validacao-macos.md](docs/01-instalacao-validacao-macos.md)

## Providers reais e smoke opcional

Checklist rapido:

```bash
./scripts/check_orquestra_providers.sh
```

Smoke real opcional:

```bash
./scripts/validate_orquestra.sh --real-provider lmstudio
./scripts/validate_orquestra_real_provider_smoke.sh --provider openai
```

Variaveis comuns:

- `OPENAI_API_KEY`
- `ANTHROPIC_API_KEY`
- `DEEPSEEK_API_KEY`
- `BRAVE_SEARCH_API_KEY`
- `TAVILY_API_KEY`
- `EXA_API_KEY`
- `LMSTUDIO_API_BASE=http://localhost:1234/v1`
- `ORQUESTRA_OSINT_TOR_PROXY_URL=socks5h://127.0.0.1:9050`

## Estrutura principal do repositorio

- `orquestra_ai/`: API FastAPI, memoria, planner, workflow, RAG e OSINT
- `orquestra_trainplane/`: servico remoto de treino/comparacao
- `orquestra_web/`: frontend React/Vite e shell desktop Tauri
- `rag/`: engine RAG local integrado
- `scripts/`: bootstrap, start, validacao, instalacao e empacotamento
- `assets/brand/`: logo, wordmark e identidade visual
- `docs/`: documentacao de operacao, arquitetura e continuidade

## Status atual e proximas etapas

Nucleo entregue:

- memoria hibrida
- compactacao de contexto
- planner hibrido
- workflows locais multi-step
- `OSINT Lab`
- `Remote Train Plane`
- desktop macOS com instalador/desinstalador

Pendencias fora do nucleo atual:

- validacao manual do `OSINT Lab` com providers reais e Tor quando aplicavel
- validacao manual do `Train Plane` com `LM Studio` local e provider real por `API key`
- integracoes AWS reais do Train Plane (`S3 multipart + CloudWatch + SSM`)
- OCR/transcricao multimodal mais rica
- assinatura/notarizacao para distribuicao publica do app macOS
