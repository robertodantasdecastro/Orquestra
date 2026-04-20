# Manual Operacional do Orquestra

## Visao geral
O Orquestra e um control plane local-first para projetos de IA. Ele organiza conversa, memoria, arquivos, RAG, planejamento e execucao em uma interface unica, com backend FastAPI local e UI compartilhada entre web e app desktop.

Este manual descreve:
- como o produto esta organizado
- como operar cada area
- qual e o fluxo recomendado no dia a dia
- quais limites ainda existem nesta fase

## Superficies oficiais da interface
As areas oficiais do Orquestra hoje sao:

1. `Operations Dashboard`
2. `Process Center`
3. `Memory Studio`
4. `Execution Center`
5. `Assistant Workspace`
6. `Workspace Browser`
7. `Projects`

## Fluxo recomendado de uso
1. escolha ou crie um projeto em `Projects`
2. abra `Assistant Workspace`
3. crie uma sessao nova com objetivo e preset
4. converse usando memoria e RAG apenas quando fizer sentido operacional
5. revise candidatos no `Memory Inbox`
6. compacte a sessao quando o contexto crescer
7. reconstrua o planner quando a abordagem mudar
8. use `Execution Center` para workflows, jobs e consulta RAG
9. use `Memory Studio` para recall, promocao e revisao global
10. use `Workspace Browser` para anexar diretorios e promover ativos relevantes

## Assistant Workspace
O `Assistant Workspace` e o centro da operacao de chat.

### O que existe ali
- criacao de sessao com:
  - `objective`
  - `preset`
  - `memory_policy`
  - `rag_policy`
  - `persona_config`
- transcript bruto separado do resumo operacional
- compactacao persistente da sessao
- painel lateral `Memoria & RAG`
- `Memory Inbox`
- bloco de planner
- resumo da sessao e transcript recente

### Presets atuais
- `research`
- `osint`
- `persona`
- `assistant`
- `dataset`

### Como a sessao funciona
Cada sessao usa:
- `ChatSession` para os metadados e perfil
- `ChatMessage` para as mensagens persistidas
- `SessionTranscript` para o arquivo bruto
- `SessionSummary` para o estado operacional
- `SessionCompactionState` para continuidade em conversas longas

### Ordem de contexto usada no backend
Quando o chat monta contexto, a ordem operacional e:
1. perfil da sessao
2. snapshot compacto
3. planner
4. memoria relevante
5. workspace/fontes
6. RAG legado
7. mensagem atual

### Flags com efeito real
As flags abaixo ja tem efeito real em `chat/stream` e `rag/query`:
- `planner_enabled`
- `memory_selector_mode`
- `include_workspace`
- `include_sources`
- `compaction_enabled`
- `context_budget`

## Memory Studio
O `Memory Studio` centraliza a memoria do sistema.

### O que pode ser feito
- listar memorias recentes
- listar topicos consolidados
- revisar candidatos pendentes
- executar recall por consulta
- promover memoria manualmente
- inspecionar `training candidates`

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

### Regras importantes
- memoria duravel so entra com aprovacao explicita
- dataset nao nasce automaticamente do chat
- fallback lexical protege o fluxo quando vetor/embeddings falham

## Workspace Browser
O `Workspace Browser` conecta diretorios locais ao contexto do Orquestra.

### Fluxo
1. informar o caminho local
2. anexar o diretorio
3. gerar inventario recursivo
4. ranquear ativos por prompt
5. extrair somente o que for necessario
6. abrir, revisar ou memorizar o ativo

### Tipos de ativo
- `code_text`
- `image`
- `pdf`
- `office`
- `audio`
- `video`
- `binary`

### Politica de eficiencia
- o inventario registra metadados
- binarios nao sao copiados para o banco por padrao
- derivados pequenos ficam em runtime local
- extracao pesada acontece sob demanda

## Memory Inbox
O `Memory Inbox` aparece no fluxo do chat e tambem pode ser acompanhado pela memoria global.

Ele serve para:
- revisar candidatos sugeridos automaticamente
- aprovar ou rejeitar memoria duravel
- manter a memoria do projeto auditavel
- separar conhecimento operacional de ruido de conversa

Ao aprovar um candidato, o sistema materializa:
1. `MemoryRecord` no banco
2. projecao em arquivo no `memdir`
3. indexacao na colecao `orquestra_memory_v1`

## Compactacao de contexto
O Orquestra nao depende de transcript integral para chats longos.

### O que a compactacao preserva
- `objective`
- `current_state`
- `task_specification`
- `decisions`
- `open_questions`
- `next_steps`
- `worklog`
- `recent_failures`

### Quando usar
- quando a sessao estiver longa
- antes de mudar de abordagem
- antes de iniciar um workflow ligado a uma sessao grande

### Como operar
- use `Compactar contexto` no `Assistant Workspace`
- ou deixe o backend aplicar por `context_budget`

## Planner hibrido
O planner organiza o trabalho da sessao.

### Componentes
- `PlannerSnapshot`
- `SessionTask`

### O que ele controla
- objetivo atual
- estrategia
- riscos
- `next_steps`
- tarefas reais da sessao
- dependencias `blocked_by` e `blocks`

### Estados de tarefa
- `pending`
- `in_progress`
- `blocked`
- `completed`
- `failed`
- `cancelled`

### Uso recomendado
- promova itens operacionais claros para tarefa
- registre dependencias quando uma tarefa trava outra
- reconstrua o planner quando a estrategia mudar

## Execution Center
O `Execution Center` concentra execucao, conectores, registry e consulta RAG.

### Blocos da tela
- providers e modelos
- acoes operacionais
- runs operacionais
- workflows locais multi-step
- conectores e jobs
- registry e comparacao
- consulta RAG operacional

### Workflows locais
Entidades principais:
- `WorkflowRun`
- `WorkflowStepRun`

Passos suportados:
- `ops_action`
- `rag_query`
- `workspace_query`
- `workspace_extract`
- `memory_review_batch`
- `shell_safe`

Estados finais relevantes:
- `succeeded`
- `failed`
- `cancelled`
- `interrupted`

### O que observar em um run
- progresso
- status por passo
- `log_path`
- `output_path`
- `output_preview`
- vinculo com tarefa
- vinculo com sessao
- recuperacao apos restart

### Remote Train Plane
Dentro do `Execution Center`, o bloco `Remote Train Plane` organiza o treino remoto e a validacao comparativa.

#### Blocos principais
- `Access & Config`
- `Base Models & Datasets`
- `Training Runs`
- `Live Metrics`
- `Evaluation Lab`
- `Promotion & Registry`

#### Fluxo recomendado
1. salvar `base_url`, token, regiao, `instance_id` e `bucket`
2. testar a conexao
3. sincronizar um `base model`
4. exportar um `dataset bundle` a partir de `training candidates` aprovados
5. criar um `training run`
6. acompanhar `loss`, `eval_loss`, GPU, CPU, checkpoints e artifact
7. executar `evaluation` e `comparison`
8. promover o artifact para o registry local se ele passar na revisao

#### Baselines suportados no lab comparativo
- `lmstudio_local`
- `provider_api`
- `trainplane_artifact`

#### O que o operador deve observar
- se o token esta configurado
- se o endpoint remoto responde no teste de conexao
- se o run gera checkpoints e artifact
- se a comparacao melhora `correctness` e `faithfulness`
- se o artifact promovido realmente deve entrar no registry local

## Operations Dashboard
O `Operations Dashboard` e a visao executiva da stack.

Ele mostra:
- servicos principais
- estado do runtime
- artefatos de distribuicao
- listeners e processos
- sessoes e scans recentes
- memoria recente
- workflows recentes

## Projects
`Projects` concentra:
- cadastro de projetos
- default provider
- default model
- organizacao de sessoes por projeto

## Validacao operacional
O comando oficial continua sendo:

```bash
./scripts/validate_orquestra.sh
```

Quando quiser incluir provider real na validacao:

```bash
./scripts/validate_orquestra.sh --real-provider lmstudio
ORQUESTRA_VALIDATE_REAL_PROVIDERS=openai ./scripts/validate_orquestra.sh
```

Ele cobre:
- backend
- frontend
- shell scripts
- build web
- `cargo check`
- pacote macOS, quando disponivel
- smoke de sessao, memoria, compactacao, planner, workflow, workspace e RAG
- smoke real opcional por provider quando solicitado

Para readiness de providers reais sem sair do fluxo local-safe:

```bash
./scripts/check_orquestra_providers.sh
```

Use modo estrito quando quiser travar um provider minimo antes de operar:

```bash
./scripts/check_orquestra_providers.sh --strict --require lmstudio
./scripts/check_orquestra_providers.sh --strict --require litellm_proxy
```

Para um smoke fim a fim com chamada real de provider:

```bash
./scripts/validate_orquestra_real_provider_smoke.sh --provider lmstudio
./scripts/validate_orquestra_real_provider_smoke.sh --provider openai
```

## Checkpoint e retomada
Quando houver risco de interrupcao por limite do Codex, reinicio da maquina ou troca de login, use sempre este protocolo:

1. atualizar `.codex/memory/orquestra-continuity.md`
2. rodar a menor validacao significativa da etapa
3. rodar `git diff --check`
4. verificar `git status --short`
5. criar commit
6. fazer `git push`

Fontes minimas para retomar:
- `AGENTS.md`
- `.codex/memory/orquestra-continuity.md`
- `git log --oneline -5`
- `git status --short`

Prompt curto recomendado:

```text
Leia AGENTS.md, .codex/memory/orquestra-continuity.md, git log --oneline -5 e git status --short. Continue a implementacao a partir da Proxima acao exata, sem reanalisar todo o projeto.
```

## Limites atuais
- conectores remotos ainda funcionam como catalogo e registro de intencao
- EC2 continua fora desta fase
- OCR e transcricao real opcional ainda podem evoluir
- smokes reais por provider sao opcionais e exigem ativacao explicita
- distribuicao publica com assinatura/notarizacao final ainda nao foi fechada
