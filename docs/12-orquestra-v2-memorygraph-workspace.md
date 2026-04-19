# Orquestra V2

`Orquestra V2` e a evolucao do control plane do `Orquestra` para um workspace macOS-first com memoria estruturada, leitura multimodal de diretorios e shell desktop.

## Objetivo
Concentrar em uma unica superficie:
- conversa multi-provider;
- memoria de sessao e memoria duravel;
- inventario e leitura multimodal de pastas;
- consulta `RAG`;
- operacao de jobs remotos;
- registry e comparacao de modelos.

## Blocos do V2
### Control Plane
- `orquestra_ai/app.py`
- `orquestra_ai/services.py`
- `orquestra_ai/models.py`

### MemoryGraph
- `orquestra_ai/memory_graph.py`
- transcript bruto
- resumo de sessao
- memoria duravel
- training candidates

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

## MemoryGraph V2
### Camadas
1. `raw_transcript`
2. `session_working_memory`
3. `durable_memory`
4. `training_candidates`

### Contratos principais
- `POST /api/chat/sessions/{id}/resume`
- `GET /api/chat/sessions/{id}/transcript`
- `GET /api/chat/sessions/{id}/summary`
- `GET /api/memory/topics`
- `POST /api/memory/recall`
- `POST /api/memory/promote`
- `GET /api/memory/training-candidates`

### Politica
- transcript nunca e o resumo;
- compactacao protege continuidade e auditoria;
- memoria duravel entra por promocao;
- recall semantico deve degradar para recall lexical quando necessario.

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

## Validacao executada neste ciclo
- `py_compile` do backend `Orquestra`
- `npm run build` do frontend
- `cargo check` do shell `Tauri`
- `tauri build` com bundle `.app` e `.dmg`
- smoke de `chat + summary + resume + transcript`
- smoke de `attach-directory + workspace query + extract + preview + memorize`
- validação de tipagem/integração da nova superfície operacional e dos scripts de instalação macOS

## Proximos passos
1. ligar providers reais via `LiteLLM Proxy`
2. adicionar uma camada de testes automatizados alem do smoke script
3. adicionar OCR e transcricao real opcional
4. amadurecer UX e readiness operacional de `Train Ops` e `Registry` sem depender ainda de execucao remota real
5. decidir se a instalacao macOS evolui para `pkg` assinado ou segue script-first nesta fase
