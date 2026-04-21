# Manual Operacional do Orquestra

## Objetivo

Este manual descreve como operar o Orquestra no dia a dia, cobrindo:

- criacao de projetos e sessoes
- uso do chat com memoria, RAG e OSINT
- planner, workflows e workspace
- aprovacao de memoria e claims
- uso do Train Plane e do registry

## Modelo mental do produto

O Orquestra e um control plane unico para trabalho com IA. Em vez de usar um chat isolado, o produto organiza:

- objetivo da sessao
- memoria duravel aprovada
- memoria curta operacional
- contexto local do workspace
- evidencias OSINT
- tarefas e proximos passos
- workflows executaveis
- comparacao e promocao de modelos

## Areas oficiais da interface

1. `Operations Dashboard`
2. `Process Center`
3. `Memory Studio`
4. `Execution Center`
5. `Assistant Workspace`
6. `OSINT Lab`
7. `Workspace Browser`
8. `Projects`

## Fluxo recomendado de trabalho

1. crie ou selecione um projeto em `Projects`
2. abra `Assistant Workspace`
3. crie uma sessao com objetivo claro e preset adequado
4. converse e mantenha o `Memory Inbox` sob revisao
5. compacte a sessao quando o contexto crescer
6. use o planner para organizar proximos passos
7. use `Workspace Browser` quando precisar associar arquivos locais
8. use `OSINT Lab` quando precisar coleta web nativa e evidencias
9. execute workflows e consultas operacionais no `Execution Center`
10. use o `Remote Train Plane` quando for sincronizar bundles, treinos ou comparacoes

## Projects

`Projects` e o ponto de organizacao por iniciativa.

Use `Projects` para:

- criar um projeto de trabalho
- separar memoria e sessoes por contexto
- manter artefatos, workflows e runs associados ao mesmo dominio

Boas praticas:

- use um projeto por iniciativa real
- nao misture investigacao OSINT, dataset e assistente pessoal no mesmo projeto sem necessidade

## Assistant Workspace

O `Assistant Workspace` e o centro do uso diario.

### O que existe na tela

- criacao de sessao
- resumo operacional
- transcript
- `Memory Inbox`
- planner
- painel lateral de contexto

### Como criar uma sessao

1. clique em `Nova sessao`
2. preencha `objective`
3. escolha um `preset`
4. ajuste `memory_policy` e `rag_policy` se necessario
5. inicie o chat

### Presets atuais

- `research`: pesquisa geral com continuidade e citacoes
- `osint`: investigacao web com evidencias e claims
- `persona`: assimilacao de estilo, restricoes e exemplos
- `assistant`: preferencias operacionais e rotina do usuario
- `dataset`: estruturacao de pares aprovados para treino futuro

### Ordem real de contexto

Ao responder, o backend monta o contexto assim:

1. perfil da sessao
2. snapshot compacto
3. planner
4. memoria relevante
5. OSINT evidence
6. workspace/fontes
7. RAG legado
8. mensagem atual

### Flags que ja tem efeito real

- `planner_enabled`
- `memory_selector_mode`
- `include_workspace`
- `include_sources`
- `include_osint_evidence`
- `compaction_enabled`
- `task_context_enabled`
- `context_budget`

## Memory Inbox e Memory Studio

### Para que servem

O `Memory Inbox` serve para revisar candidatos sugeridos no contexto do chat. O `Memory Studio` permite governar a memoria do sistema de forma mais ampla.

### O que pode ser aprovado

- memoria do usuario
- feedback operacional
- memoria de projeto
- referencia aprovada
- persona
- dataset

### Regra central

Nada vira memoria duravel sem aprovacao explicita.

### O que acontece ao aprovar memoria

O sistema materializa:

1. `MemoryRecord` no banco local
2. projecao em arquivo no `memdir`
3. indexacao em `orquestra_memory_v1`

Se a origem veio do `OSINT Lab`, a memoria mantem:

- `citations`
- `source_url`
- `claim_id`
- `capture_id`
- `evidence_ids`
- `validation_status`

### Quando usar recall lexical ou hibrido

Use `lexical` quando:

- embeddings estiverem indisponiveis
- voce quiser previsibilidade maxima

Use `hybrid` quando:

- quiser recall mais rico
- o backend vetorial estiver saudavel

## Compactacao de contexto

O Orquestra nao depende do transcript inteiro para sessoes longas.

### O que e preservado

- `objective`
- `current_state`
- `task_specification`
- `decisions`
- `open_questions`
- `next_steps`
- `worklog`
- `recent_failures`

### Quando compactar

- quando a sessao estiver longa
- antes de mudar de abordagem
- antes de iniciar um workflow importante
- antes de retomar uma conversa antiga

### Como operar

- acione a compactacao manual no `Assistant Workspace`
- ou deixe o backend aplicar automaticamente por `context_budget`

## Planner hibrido

### Componentes

- `PlannerSnapshot`
- `SessionTask`

### O que o planner controla

- estrategia atual
- riscos
- `next_steps`
- tarefas persistidas
- dependencias `blocked_by` e `blocks`

### Estados de tarefa

- `pending`
- `in_progress`
- `blocked`
- `completed`
- `failed`
- `cancelled`

### Procedimento recomendado

1. transforme proximos passos operacionais em tarefas
2. marque dependencias quando uma tarefa bloquear outra
3. reconstrua o planner quando a estrategia mudar
4. mantenha `next_steps` coerente com o estado real da sessao

## Execution Center

O `Execution Center` concentra execucao, conectores, comparacoes e operacao remota.

### Blocos principais

- providers e modelos
- acoes operacionais
- workflows locais
- runs e logs
- consulta RAG operacional
- resumo do `OSINT Connector Hub`
- `Remote Train Plane`
- registry e comparacao

### Workflows locais multi-step

Passos suportados hoje:

- `ops_action`
- `rag_query`
- `workspace_query`
- `workspace_extract`
- `memory_review_batch`
- `shell_safe`

### O que observar num run

- `status`
- `log_path`
- `output_path`
- `output_preview`
- passos executados
- vinculo com tarefa ou sessao

Estados finais esperados:

- `succeeded`
- `failed`
- `cancelled`
- `interrupted`

## Workspace Browser

O `Workspace Browser` conecta diretorios locais ao contexto do Orquestra.

### Fluxo recomendado

1. anexe um diretorio
2. gere o inventario
3. ranqueie ativos
4. extraia apenas o necessario
5. use o preview
6. memorize ou cite o ativo quando fizer sentido

### Tipos de ativo

- `code_text`
- `image`
- `pdf`
- `office`
- `audio`
- `video`
- `binary`

### Politica operacional

- inventario primeiro
- extracao pesada depois
- derivados pequenos no runtime local
- binarios nao entram integralmente no banco por padrao

## OSINT Lab

O `OSINT Lab` e a trilha nativa de investigacao web do Orquestra.

### O que ele entrega

- investigacoes com objetivo e contexto proprio
- conectores administraveis
- busca web nativa
- fetch normalizado
- evidencias e claims
- promocao rastreavel para memoria
- export controlado para dataset

### Fluxo recomendado

1. crie a investigacao
2. habilite os conectores relevantes
3. planeje as queries
4. rode a busca
5. faca fetch das fontes mais relevantes
6. revise evidencias
7. aprove claims
8. promova memoria ou exporte bundle

Guia detalhado:

- [docs/03-osint-lab.md](./03-osint-lab.md)

## Remote Train Plane

O `Remote Train Plane` fica no `Execution Center` e permite:

- configurar endpoint e credenciais
- sincronizar `base models`
- sincronizar `dataset bundles`
- criar `training runs`
- acompanhar `metrics`, `artifacts`, `evaluations` e `comparisons`
- promover artefatos aprovados

Estado atual:

- a trilha operacional ja existe
- o backend remoto atual e validavel e funcional para fluxo, comparacao e artifacts
- as integracoes AWS reais ainda sao uma etapa posterior

Guia detalhado:

- [docs/04-train-plane.md](./04-train-plane.md)

## Procedimentos comuns

### Criar uma sessao de pesquisa

1. crie um projeto
2. abra `Assistant Workspace`
3. escolha `preset=research`
4. ligue memoria e RAG se fizer sentido
5. anexe workspace local se houver material

### Criar uma sessao OSINT

1. crie a investigacao no `OSINT Lab`
2. ative os conectores necessarios
3. rode busca e fetch
4. aprove evidencias e claims
5. volte ao `Assistant Workspace` com `preset=osint`

### Promover conteudo para memoria

1. abra o `Memory Inbox`
2. revise o candidato
3. aprove apenas o que for duravel
4. rejeite ruido ou contexto temporario

### Executar um workflow local

1. abra `Execution Center`
2. crie o run
3. acompanhe `status`, `logs` e `output`
4. cancele se a execucao nao fizer mais sentido

### Exportar um bundle para treino

1. aprove memoria ou claims relevantes
2. revise se `training_allowed` esta coerente
3. exporte o bundle
4. sincronize com o `Remote Train Plane`

## Boas praticas operacionais

- mantenha o objetivo da sessao curto e concreto
- use memoria duravel apenas para conhecimento que realmente precisa sobreviver
- use `OSINT Lab` para evidencias; nao use memoria como deposito de fonte bruta
- compacte sessoes longas antes de perder continuidade
- use o planner para trabalho de sessao, nao para memoria duravel
- confirme politica de licenca e retencao antes de montar dataset

## Logs, runtime e continuidade

Caminhos importantes:

- runtime instalado: `~/Library/Application Support/Orquestra/runtime`
- logs: `~/Library/Logs/Orquestra`
- handoff: `.codex/memory/orquestra-continuity.md`

Retomada com baixo contexto:

1. leia `AGENTS.md`
2. leia `.codex/memory/orquestra-continuity.md`
3. rode `git log --oneline -5`
4. rode `git status --short`
