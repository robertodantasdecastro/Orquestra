# Manual Operacional do Orquestra

## Contexto
O `Orquestra` nasceu da evolucao do ambiente `Local_RAG` para uma aplicacao independente, macOS-first e local-first. A meta atual nao e apenas rodar scripts de RAG, mas oferecer uma superficie unica para chat multi-provider, memoria, leitura multimodal de diretorios, RAG, registry, jobs e gestao operacional.

Este manual descreve como a aplicacao funciona, como instalar, como operar no dia a dia e quais limites ainda existem nesta fase.

## Objetivo do Produto
O Orquestra e um control plane local para projetos de IA. Ele coordena modelos, memoria, arquivos, RAG, execucoes e artefatos em um workspace unico.

Objetivos principais:
- operar modelos locais e remotos em uma unica interface;
- manter continuidade entre sessoes por transcript, resumo e memoria duravel;
- analisar diretorios com arquivos heterogeneos sem copiar binarios grandes para o banco;
- consultar conhecimento local via RAG;
- preparar jobs de treino e registrar artefatos de modelo;
- fornecer dashboard com estado de servicos, processos, memoria e execucao;
- empacotar a experiencia em app macOS sem perder o modo web.

## Recursos Detalhados
### 1. Assistant Workspace
O Assistant Workspace e a superficie de conversa.

Ele permite:
- criar sessoes por projeto com objetivo obrigatorio e preset operacional;
- escolher provider e modelo;
- conversar em modo streaming;
- usar resumo da sessao e estado de compactacao como contexto operacional;
- recuperar memoria aprovada de `orquestra_memory_v1` antes de responder;
- recuperar contexto por pipeline `summary + recent tail + recalled memory + fontes`;
- compactar sessoes longas manualmente ou por orcamento de contexto;
- manter `next_steps` reais via planner hibrido;
- sugerir candidatos revisaveis no `Memory Inbox`;
- promover memoria duravel somente apos aprovacao explicita;
- gerar training candidates somente quando o modo dataset estiver habilitado e o candidato for aprovado;
- consultar transcript e resumo separadamente.

Camadas usadas:
- `ChatSession`: sessao ativa;
- `ChatMessage`: mensagens persistidas no banco;
- `SessionTranscript`: arquivo JSONL bruto;
- `SessionSummary`: resumo operacional estruturado;
- `MemoryReviewCandidate`: fila de revisao;
- `MemoryRecord`: memoria duravel ou episodica.

### 2. Memory Studio
O Memory Studio gerencia a memoria do projeto.

Recursos:
- listagem de memorias recentes;
- topicos de memoria duravel;
- memdir projetado em arquivos para sessao, projeto e escopo global;
- filtros por `memory_kind`, `scope`, sessao e projeto;
- recall por consulta;
- promocao manual de contexto para topico;
- revisao de candidatos do `Memory Inbox`;
- visualizacao de training candidates;
- separacao entre memoria de sessao e memoria duravel.

Escopos recomendados:
- `user_profile_memory`: preferencias e padroes do usuario;
- `project_memory`: decisoes e contexto duravel do projeto;
- `episodic_memory`: fatos de uma interacao especifica;
- `semantic_memory`: conhecimento extraido e reaproveitavel;
- `workspace_memory`: ativos relevantes de diretorios anexados.
- `persona_memory`: estilo, tom e restricoes aprovadas;
- `source_fact`: fatos com fonte/citacao;
- `training_signal`: material candidato a dataset, sempre revisado.

Tipos de memoria suportados:
- `user`
- `feedback`
- `project`
- `reference`
- `persona`
- `dataset`

### 3. Workspace Browser
O Workspace Browser anexa diretorios e permite leitura multimodal.

Fluxo:
1. informar uma pasta local;
2. gerar inventario recursivo;
3. classificar arquivos por tipo;
4. ranquear ativos por prompt;
5. extrair conteudo sob demanda;
6. responder citando caminhos;
7. abrir ou memorizar ativos relevantes.

Tipos reconhecidos:
- `code_text`: codigo e texto;
- `image`: imagens;
- `pdf`: documentos PDF;
- `office`: `docx`, `xlsx`, `pptx`;
- `audio`: audio com metadados e transcricao opcional;
- `video`: video com metadados, poster frame e transcricao opcional;
- `binary`: arquivo sem extrator especifico.

Politica de eficiencia:
- o inventario registra metadados, nao duplica binarios;
- derivados pequenos ficam em `experiments/orquestra/workspace`;
- derivados pesados usam TTL;
- indexacao vetorial acontece quando ha texto util;
- se o vetor falhar, o Orquestra degrada para ranking lexical.

### 4. RAG Studio
O RAG Studio consulta o engine local de RAG.

Ele permite:
- enviar pergunta;
- escolher collection;
- usar provider/modelo selecionado;
- rodar em modo mock;
- persistir interacao quando necessario;
- recuperar memoria aprovada pela colecao Chroma `orquestra_memory_v1`;
- promover respostas uteis para memoria.

Uso recomendado:
- perguntas sobre base local;
- recuperacao de contexto tecnico;
- validacao de conteudo antes de promover para memoria;
- preparacao de material que pode virar dataset.

### 5. Execution Center
O Execution Center concentra providers, conectores, jobs, registry e acoes operacionais.

Recursos:
- listagem de providers configurados;
- catalogo de conectores;
- criacao de training jobs e remote jobs como intencao local;
- leitura de logs de jobs quando houver caminho registrado;
- registro de modelos/adapters;
- comparacao de benchmarks;
- execucao local multi-step por `WorkflowRun` e `WorkflowStepRun`;
- acompanhamento de progresso por passo, log tail e cancelamento;
- vinculacao opcional entre workflow, sessao e tarefa do planner;
- disparo de acoes operacionais:
  - bootstrap;
  - validacao;
  - build web;
  - build desktop;
  - instalacao macOS;
  - desinstalacao macOS.

Limite atual:
- conectores remotos ainda nao executam treino real;
- EC2 ficou propositalmente para fase posterior;
- o estado `queued_waiting_compute` indica que o job esta preparado, mas aguardando compute real.

### 6. Operations Dashboard
O dashboard mostra a saude do sistema.

Ele monitora:
- API local;
- web dashboard;
- bundle web;
- app desktop;
- DMG;
- SQLite runtime;
- MemoryGraph Store;
- Workspace Runtime;
- Chroma Memory RAG;
- Qdrant local como backend futuro/adaptavel;
- Redis opcional;
- LM Studio;
- Ollama;
- LiteLLM Proxy;
- instalador e desinstalador.

Tambem exibe:
- metricas de servicos prontos;
- sessoes recentes;
- memorias;
- execucoes;
- listeners;
- processos encontrados;
- caminhos de runtime;
- artefatos de distribuicao.

## Arquitetura Operacional
### Backend
O backend e uma API FastAPI em `orquestra_ai/app.py`.

Responsabilidades:
- servir endpoints;
- orquestrar chat;
- chamar gateway de modelos;
- registrar memoria;
- coordenar workspace multimodal;
- registrar jobs e modelos;
- expor snapshot operacional.

### Gateway de Modelos
O gateway fica em `orquestra_ai/gateway.py`.

Ele suporta:
- provider OpenAI-compatible;
- LiteLLM;
- modo mock;
- listagem de modelos quando o provider expoe `/models`;
- fallback local-safe quando solicitado.

### Banco Local
O banco padrao e SQLite, configurado pelo `.env`.

Dados principais:
- projetos;
- providers;
- sessoes e mensagens;
- transcript e resumo;
- estado de compactacao;
- memoria;
- topicos;
- candidates;
- tarefas e snapshot de planner;
- runs e steps de workflow;
- jobs;
- registry;
- scans e ativos de workspace.

### Artefatos
Os artefatos vivem em `experiments/orquestra/` por padrao.

Subpastas importantes:
- `memorygraph/transcripts`;
- `memorygraph/session_summaries`;
- `memorygraph/memdir`;
- `memorygraph/topics`;
- `memorygraph/manifests`;
- `memorygraph/training_candidates`;
- `rag_runtime`;
- `workspace/inventories`;
- `workspace/derivatives`;
- `workspace/insights`;
- `qdrant`;
- `operations`.

### Frontend e Desktop
O frontend e React/Vite em `orquestra_web/`.

O desktop e Tauri em `orquestra_web/src-tauri/`.

O shell desktop e fino:
- ele renderiza a UI;
- a API segue local em `127.0.0.1:8808`;
- web e desktop consomem os mesmos endpoints.
- o instalador cria um LaunchAgent para manter a API local disponivel;
- o build gera `.app` e `.dmg` em `orquestra_web/src-tauri/target/release/bundle/`.

## Instalacao no macOS
### Pre-requisitos
Instale ou confirme:
- `python3.12` ou `python3`;
- `node` e `npm`;
- `rustup` e `cargo`;
- opcionalmente `LM Studio`, `ffmpeg`, `ffprobe` e `whisper`.

### Bootstrap
```bash
cd /caminho/para/Orquestra
./scripts/bootstrap_orquestra.sh
```

O bootstrap:
- cria `.venv`;
- instala dependencias Python;
- instala dependencias web;
- cria `.env` se estiver ausente.

### Instalador completo
```bash
./scripts/install_orquestra_macos.sh
```

O instalador:
- valida que esta em macOS;
- prepara dependencias;
- builda o app desktop;
- valida o pacote `.app` e o DMG;
- instala `Orquestra AI.app` em `~/Applications`;
- cria `~/Library/Application Support/Orquestra`;
- sincroniza o runtime em `~/Library/Application Support/Orquestra/runtime`;
- gera backup do banco local antes do upgrade quando existir estado anterior;
- grava manifesto do runtime em `experiments/orquestra/install/install_manifest.json`;
- cria `~/Library/Logs/Orquestra`;
- registra LaunchAgent `ai.orquestra.api`;
- aguarda a API responder em `/api/health`.

Opcoes:
```bash
./scripts/install_orquestra_macos.sh --skip-build
./scripts/install_orquestra_macos.sh --no-launch-agent
./scripts/install_orquestra_macos.sh --no-runtime-sync
./scripts/install_orquestra_macos.sh --open
./scripts/install_orquestra_macos.sh --no-wait-api
./scripts/install_orquestra_macos.sh --skip-package-verify
./scripts/install_orquestra_macos.sh --install-dir "$HOME/Applications/Orquestra AI.app"
```

Use `--skip-build` quando o bundle Tauri ja existir.
Use `--no-launch-agent` quando quiser iniciar a API manualmente.
Use `--no-runtime-sync` apenas em desenvolvimento, quando quiser que o LaunchAgent use o runtime ja existente.
Use `--open` para abrir o app instalado ao final.
Use `--skip-package-verify` apenas se estiver depurando uma build parcial.
Use `ORQUESTRA_INSTALL_API_WAIT_SECONDS=120` se o primeiro boot da API demorar por carregamento de dependencias locais.
Use `ORQUESTRA_INSTALL_BACKUP_LIMIT=8` para manter mais backups do banco durante upgrades.

### Validar pacote macOS
```bash
./scripts/validate_orquestra_macos_package.sh
```

Essa verificacao confirma:
- bundle `.app`;
- DMG;
- `Info.plist`;
- executavel `orquestra-desktop`;
- sintaxe do instalador/desinstalador;
- estado da assinatura local.

A assinatura atual e `ad-hoc`, suficiente para uso local. Para distribuicao publica, ainda sera necessario configurar Developer ID, hardened runtime e notarizacao.

### Desinstalador
```bash
./scripts/uninstall_orquestra_macos.sh
```

Por padrao remove:
- LaunchAgent;
- app em `~/Applications/Orquestra AI.app`.

Preserva:
- `~/Library/Application Support/Orquestra`;
- `~/Library/Logs/Orquestra`.

Remocao completa:
```bash
./scripts/uninstall_orquestra_macos.sh --purge-data
```

Opcoes:
```bash
./scripts/uninstall_orquestra_macos.sh --install-dir "$HOME/Applications/Orquestra AI.app"
./scripts/uninstall_orquestra_macos.sh --purge-data
./scripts/uninstall_orquestra_macos.sh --no-launch-agent
```

## Operacao Diaria
### Modo 1: Desenvolvimento local
Abra dois terminais:

Terminal 1:
```bash
./scripts/start_orquestra_api.sh
```

Terminal 2:
```bash
./scripts/start_orquestra_web.sh
```

Acesse:
- `http://127.0.0.1:4177`

### Modo 2: Desktop local
```bash
./scripts/start_orquestra_desktop.sh
```

Esse modo e ideal para uso diario no Mac sem abrir manualmente o browser.

### Modo 2B: Build, abrir e verificar desktop
```bash
./script/build_and_run.sh --verify
```

Esse modo builda o Tauri, valida o pacote, sobe a API se necessario, abre o `.app` e confirma processo + `/api/health`.

### Modo 3: Stack em background
```bash
./scripts/start_orquestra_stack.sh
```

Esse script usa `tmux` para deixar API e web rodando em sessoes separadas.

### Modo 4: App instalado
Depois do instalador:
- abra `~/Applications/Orquestra AI.app`;
- a API deve ser mantida pelo LaunchAgent;
- consulte logs em `~/Library/Logs/Orquestra`.

## Configuracao de Providers
### LM Studio
1. Abra o LM Studio.
2. Carregue um modelo.
3. Ative o servidor local.
4. Confirme `.env`:
```bash
LMSTUDIO_API_BASE=http://localhost:1234/v1
```

### OpenAI, Anthropic e DeepSeek
Configure no `.env` local:
```bash
OPENAI_API_KEY=...
ANTHROPIC_API_KEY=...
DEEPSEEK_API_KEY=...
```

Nao versionar esse arquivo.

### LiteLLM Proxy
Quando quiser centralizar providers remotos:
```bash
ORQUESTRA_LITELLM_PROXY_URL=http://127.0.0.1:4000
```

## Fluxos de Uso
### Criar uma sessao de chat
1. Abra `Assistant Workspace`.
2. Escolha projeto, provider e modelo.
3. Clique em `Nova sessao`.
4. Defina o objetivo obrigatorio da sessao.
5. Escolha o preset: `Pesquisa`, `OSINT`, `Persona`, `Assistente` ou `Dataset`.
6. Ajuste as opcoes rapidas: usar RAG, usar Workspace, capturar memorias e modo dataset.
7. Clique em `Iniciar chat`.
8. Use o painel lateral `Memoria & RAG` para ajustar objetivo, preset, memoria, RAG e workspace durante a conversa.
9. Digite o prompt e use modo mock se quiser validar sem provider real.
10. Consulte `Resumo`, `Transcript` e `Memory Inbox` para continuidade.

O Orquestra gera candidatos revisaveis apos as respostas. Esses candidatos nao viram memoria duravel nem dataset automaticamente.

### Revisar Memory Inbox
1. Abra `Assistant Workspace`.
2. Selecione uma sessao.
3. Abra o painel `Memoria & RAG`.
4. Leia cada candidato pendente com escopo, `memory_kind`, confianca e conteudo resumido.
5. Use `Aprovar` para criar `MemoryRecord` e indexar em `orquestra_memory_v1`.
6. Use `Rejeitar` para descartar a sugestao.
7. Ative `dataset apos aprovacao` somente quando quiser gerar `TrainingCandidate` a partir da aprovacao.

### Compactar uma sessao
1. Abra `Assistant Workspace`.
2. Selecione a sessao longa que deseja estabilizar.
3. No painel lateral, use `Compactar contexto`.
4. Confirme que o bloco de compactacao mostra quantidade de mensagens consolidadas e `next_steps`.
5. Continue o chat normalmente; o prompt passa a priorizar `summary + recent tail + recalled memory`.

### Trabalhar com planner
1. Abra `Assistant Workspace`.
2. Selecione a sessao.
3. No painel lateral, revise `Planner` e `next_steps`.
4. Use `Validar planner` para reconstruir o snapshot a partir do resumo atual.
5. Adicione uma nova tarefa a partir do prompt atual ou atualize o status de uma tarefa existente.
6. Use tarefas da sessao para guiar execucao, sem transformar isso automaticamente em memoria duravel.

### Promover memoria
1. Abra `Memory Studio`.
2. Escreva um conteudo relevante.
3. Defina titulo e escopo.
4. Use `Promover`.
5. Teste recall com uma pergunta relacionada.

### Anexar uma pasta
1. Abra `Workspace Browser`.
2. Informe o caminho da pasta.
3. Defina um prompt hint.
4. Execute o scan.
5. Selecione ativos para preview/extracao.
6. Consulte o workspace com uma pergunta.
7. Memorize os ativos que devem virar contexto duravel.

### Consultar RAG
1. Abra `RAG Studio`.
2. Informe a pergunta.
3. Escolha modo mock ou provider real.
4. Se houver sessao selecionada, a consulta tambem pode recuperar memoria aprovada de `orquestra_memory_v1`.
5. Analise resposta, citacoes, uso e memoria recuperada.
6. Promova o que for importante para memoria ou aprove candidatos no `Memory Inbox`.

### Preparar um job
1. Abra `Execution Center`.
2. Escolha conector.
3. Crie `training job` ou `remote job`.
4. Acompanhe estado na lista.
5. Se houver logs registrados, abra o console do job.

Nesta fase, isso registra intencao e metadados. Execucao remota real sera ligada depois.

### Executar um workflow local
1. Abra `Execution Center`.
2. Revise a lista `Local workflows`.
3. Dispare o workflow de validacao ou crie um novo run pela API.
4. Acompanhe status, progresso por passo, `log tail`, `output_path` e preview do artefato.
5. Use `Cancelar` quando precisar interromper a execucao.
6. Diferencie o estado final do run:
   - `succeeded`: concluido com artefato final;
   - `failed`: falhou com saida parcial persistida;
   - `cancelled`: cancelado pelo usuario com estado final salvo;
   - `interrupted`: recuperado apos restart.
7. Depois do restart da app, reabra o Execution Center para confirmar a recuperacao do run persistido.

### Registrar modelo
1. Abra `Execution Center`.
2. Registre artefato no registry.
3. Informe formato, modelo base e benchmark.
4. Compare baseline e candidate.
5. Registre deploy local quando apropriado.

## Validacao
Execute:
```bash
./scripts/validate_orquestra.sh
```

Essa validacao cobre:
- compilacao Python;
- `pytest` do backend/API;
- sintaxe dos scripts shell;
- `vitest`, `tsc -b` e build web;
- `cargo check` do Tauri;
- smoke da API;
- chat com perfil de sessao, resumo, resume e transcript;
- compactacao de sessao e persistencia de `next_steps`;
- `auto compact` sob contexto longo com `context_budget`;
- planner, tarefas e consistencia de resumo;
- dependencias de planner (`blocked_by` e `blocks`);
- Memory Inbox, aprovacao e recall RAG associado;
- workflow local multi-step, incluindo cancelamento, falha parcial e recovery apos restart;
- scan de workspace;
- preview e memoria.

## Checkpoint e retomada
Quando houver risco de interrupcao por limite do Codex, troca de login ou reinicio do computador, use este protocolo:

1. atualize `.codex/memory/orquestra-continuity.md`
2. rode a menor validacao significativa da etapa
3. rode `git diff --check`
4. confira `git status --short`
5. crie um commit
6. faca `git push`

Fontes minimas para retomar sem reler toda a thread:
- `AGENTS.md`
- `.codex/memory/orquestra-continuity.md`
- `git log --oneline -5`
- `git status --short`

Prompt curto recomendado:

```text
Leia AGENTS.md, .codex/memory/orquestra-continuity.md, git log --oneline -5 e git status --short. Continue a implementacao a partir da Proxima acao exata, sem reanalisar todo o projeto.
```

## Troubleshooting
### API nao responde
Verifique:
```bash
curl -fsS http://127.0.0.1:8808/api/health
```

Se instalado:
```bash
launchctl print gui/$UID/ai.orquestra.api
tail -n 100 ~/Library/Logs/Orquestra/api.stderr.log
```

### Web nao abre
Verifique:
```bash
./scripts/start_orquestra_web.sh
```

Depois acesse `http://127.0.0.1:4177`.

### Provider local offline
Confirme se o LM Studio esta aberto e com servidor ativo.

Teste:
```bash
curl -fsS http://localhost:1234/v1/models
```

### Audio/video sem transcricao
Instale e exponha `whisper`, `ffmpeg` e `ffprobe`.

Sem essas ferramentas, o Orquestra continua operando em modo `metadata_only`.

### Build desktop falha
Confirme:
```bash
node --version
npm --version
cargo --version
```

Depois:
```bash
cd orquestra_web
npm install
npm run desktop:build
```

Valide o pacote:
```bash
./scripts/validate_orquestra_macos_package.sh
```

## Politica de Dados
- `.env` real nao deve entrar no Git.
- Chaves SSH e API keys ficam fora do repositorio.
- Binarios originais anexados no Workspace nao sao duplicados por padrao.
- Derivados ficam em `experiments/orquestra/workspace`.
- Logs instalados ficam em `~/Library/Logs/Orquestra`.
- Dados de suporte instalados ficam em `~/Library/Application Support/Orquestra`.
- Runtime da API instalada fica em `~/Library/Application Support/Orquestra/runtime`.
- Manifesto do runtime fica em `~/Library/Application Support/Orquestra/runtime/experiments/orquestra/install/install_manifest.json`.
- Backups de upgrade ficam em `~/Library/Application Support/Orquestra/runtime/experiments/orquestra/install/backups`.

## Logo e Identidade
A marca do Orquestra representa um nucleo local-first com orbitas de servicos conectados.

Arquivos:
- `assets/brand/orquestra-logo.svg`
- `assets/brand/orquestra-wordmark.svg`
- `orquestra_web/src/assets/orquestra-logo.svg`

Uso recomendado:
- logo quadrada para app, sidebar e icones;
- wordmark para README, apresentacoes e documentacao;
- paleta principal: azul ciano, verde menta, fundo azul-petroleo.

## Estado Atual e Limites
Pronto hoje:
- backend FastAPI;
- frontend web;
- app Tauri;
- `.app` e DMG gerados localmente;
- dashboard operacional;
- MemoryGraph V2;
- compactacao completa de contexto;
- planner hibrido com `SessionTask` e `PlannerSnapshot`;
- executor local multi-step com `WorkflowRun` e `WorkflowStepRun`;
- Workspace Multimodal;
- RAG local integrado;
- memoria associada ao RAG com `Memory Inbox`;
- instalador/desinstalador macOS;
- registry e jobs como catalogo operacional.

Ainda posterior:
- execucao real EC2;
- assinatura/notarizacao macOS;
- OCR completo;
- transcricao real validada em todos os formatos;
- conectores remotos com compute real;
- Keychain para credenciais.

## Checklist de Fechamento
Antes de considerar uma fase concluida:
1. Atualizar README ou docs afetados.
2. Rodar `./scripts/validate_orquestra.sh`.
3. Rodar `git diff --check`.
4. Conferir `git status --short`.
5. Fazer commit e push quando a fase estiver pronta.
