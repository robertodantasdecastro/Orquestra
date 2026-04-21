# OSINT Lab

## Objetivo

O `OSINT Lab` transforma busca web, fetch, evidencia e memoria rastreavel em um fluxo nativo do Orquestra. Ele existe para que investigacoes nao dependam apenas de:

- transcript de chat
- provider externo do modelo
- RAG legado ja indexado

## O que o modulo entrega hoje

- `OsintInvestigation`
- `OsintRun`
- `OsintSource`
- `OsintCapture`
- `OsintEvidence`
- `OsintClaim`
- `OsintEntity`
- conectores administraveis
- source registry editavel
- export local de dataset aprovado

## Modelo operacional

O `OSINT Lab` separa quatro camadas:

1. `source`
2. `capture`
3. `evidence`
4. `claim`

Somente depois de revisao explicita uma `claim` pode virar:

- `MemoryRecord`
- `TrainingCandidate`
- `Dataset bundle`

## Conectores administraveis

Cada conector pode ser:

- ligado ou desligado globalmente
- ligado ou desligado por investigacao
- classificado por `credential_status`
- classificado por `health_status`
- limitado por `retention_policy`

### Conectores seedados

Busca e APIs com execucao implementada no runtime atual:

- `brave`
- `tavily`
- `exa`
- `github`
- `wikidata`
- `sec`
- `internet_archive`
- `cisa_kev`
- `nvd`
- `youtube`
- `shodan`

Conectores administraveis ja seedados para evolucao/control plane:

- `censys`
- `reddit`
- `onion_manual`

### Estado padrao

- `brave`: ligado por padrao, exige `BRAVE_SEARCH_API_KEY`
- `tavily`: desligado ate haver `TAVILY_API_KEY`
- `exa`: desligado ate haver `EXA_API_KEY`
- `github`: ligado por padrao, funciona sem token e melhora com `GITHUB_TOKEN`
- `wikidata`: ligado por padrao
- `sec`: ligado por padrao
- `internet_archive`: ligado por padrao
- `cisa_kev`: ligado por padrao
- `nvd`: ligado por padrao, aceita `NVD_API_KEY`
- `youtube`: desligado ate haver `YOUTUBE_API_KEY`
- `shodan`: desligado ate haver `SHODAN_API_KEY`
- `censys`: desligado ate haver `CENSYS_API_ID` e `CENSYS_API_SECRET`
- `reddit`: desligado por padrao e condicionado a politica explicita
- `onion_manual`: desligado por padrao e usado como seed manual

Para preparar chaves e dependencias opcionais, use:

```bash
./scripts/install_orquestra_macos_full.sh --with-optional brave,tor --configure-env
./scripts/check_orquestra_macos_installation.sh --check-only
```

Guia completo de logins/chaves:

- [docs/05-instalador-completo-macos.md](./05-instalador-completo-macos.md)

## Source Registry

O `Source Registry` serve para:

- registrar seeds manuais
- cadastrar fontes curadas
- manter politica de retencao
- marcar se a fonte pode ou nao entrar em treino
- armazenar `base_url`, categoria, criticidade e confiabilidade

Use o registry quando:

- precisar de fallback sem search provider
- quiser manter uma lista curada por projeto
- quiser seeds `.onion` ou listas especificas

## Fluxo recomendado de investigacao

1. crie a investigacao com `objective`, entidade, idioma e jurisdicao
2. selecione os conectores ativos
3. gere ou ajuste as queries planejadas
4. execute a busca
5. revise as fontes retornadas
6. faca fetch das fontes mais relevantes
7. revise as evidencias extraidas
8. aprove claims duraveis
9. promova memoria ou exporte bundle

## Como usar na pratica

### 1. Criar a investigacao

Campos recomendados:

- `title`
- `objective`
- `target_entity`
- `language`
- `jurisdiction`

Boas praticas:

- deixe o objetivo direto
- use a mesma lingua dominante da busca
- use jurisdicao quando a fonte depender de pais ou regulacao

### 2. Administrar conectores

No painel de conectores:

- ligue apenas o necessario
- confira `credential_status`
- confira `health_status`
- desative conectores pagos ou sensiveis quando nao estiver usando

### 3. Planejar queries

Use queries que combinem:

- entidade principal
- aliases
- `site:`
- recorte temporal
- recorte geografico
- tipo de documento

Exemplos:

```text
nome da entidade site:sec.gov
nome da entidade breach report
nome da entidade jurisdiction language
```

### 4. Rodar a busca

O `Search Orchestrator` usa:

1. conectores efetivamente habilitados e prontos
2. fallback por ordem de prioridade
3. `Source Registry` quando nao houver resultado suficiente

### 5. Fazer fetch

O fetch:

- valida URL
- normaliza `HTML`, `PDF`, `JSON` e texto
- gera hash
- cria `capture`
- preserva metadados de origem

### 6. Revisar evidencias

Evidencia deve representar trecho ou fato observavel. Use aprovacao para:

- trechos confiaveis
- dados que sustentam uma inferencia
- material que mereca reuso no chat e no RAG

Evite aprovar como evidencia:

- snippets pobres
- duplicatas
- conteudo sem valor duravel

### 7. Aprovar claims

A `claim` e o nivel sintetizado da investigacao. Ao aprovar uma claim, o sistema pode:

- criar `MemoryRecord`
- projetar o conteudo no `memdir`
- indexar no `orquestra_memory_v1`

Proveniencia preservada:

- `citations`
- `source_url`
- `claim_id`
- `capture_id`
- `evidence_ids`
- `validation_status`

### 8. Exportar bundle

Use export somente quando:

- as claims foram revisadas
- a politica de retencao permite
- `training_allowed=true` fizer sentido

Por padrao, o sistema tende a ser conservador:

- `store_result_metadata = true`
- `store_full_provider_snippet = false`
- `training_allowed = false`

## Integracao com chat e RAG

O `OSINT Lab` nao fica isolado da conversa. Quando o preset e `osint`, ou quando a investigacao esta associada ao fluxo, o backend inclui `OSINT evidence` na montagem de contexto.

Ordem de contexto:

1. perfil da sessao
2. snapshot compacto
3. planner
4. memoria relevante
5. OSINT evidence
6. workspace/fontes
7. RAG legado
8. mensagem atual

Isso permite:

- usar evidencias no `Assistant Workspace`
- usar evidencias no `rag/query`
- transformar claim aprovada em memoria duravel rastreavel

## Uso com Tor

O suporte Tor e `local-first` e isolado ao fetcher OSINT.

### O que isso significa

- a aplicacao inteira nao e roteada por Tor
- apenas fetch/crawl OSINT pode usar proxy `SOCKS5`
- a URL padrao esperada e `socks5h://127.0.0.1:9050`

### Quando usar

- seeds `.onion`
- fetch sensivel que exija proxy local controlado

### Cuidados

- confirme que o proxy local realmente esta ativo
- habilite apenas conectores e seeds que permitem `via_tor`
- nao assuma que todo conector suporta esse modo

## APIs principais

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

## Procedimento minimo recomendado

1. configure as chaves dos conectores que realmente vai usar
2. habilite o minimo necessario
3. crie a investigacao
4. rode busca
5. faca fetch de 1 a 3 fontes fortes
6. aprove somente evidencias e claims claras
7. promova memoria apenas do que precisa sobreviver

## Limites atuais

- parte do catalogo de conectores ja esta seedada para evolucao, mas nem todos os conectores seedados tem executor completo de busca no runtime atual
- providers reais dependem de credenciais e disponibilidade externa
- o fluxo `.onion` depende de proxy local configurado pelo operador

## Troubleshooting rapido

### Busca nao retorna resultados

Verifique:

- `enabled`
- `ready`
- credencial no ambiente
- conectores selecionados na investigacao
- seeds no `Source Registry`

### Claim aprovada nao apareceu no chat

Verifique:

- se a memoria foi criada
- se a sessao atual usa o projeto correto
- se `include_osint_evidence` ou o preset `osint` estao ativos
- se o recall esta em modo `hybrid` ou `lexical` funcional

### Fetch falhou

Verifique:

- URL
- timeout
- content-type
- se o proxy Tor foi exigido sem estar disponivel
