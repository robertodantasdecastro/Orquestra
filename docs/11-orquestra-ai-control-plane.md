# Orquestra AI

`Orquestra AI` e o control plane unificado da aplicacao `Orquestra`. A proposta e concentrar `RAG`, memoria, leitura multimodal, jobs remotos e operacao de modelos em um workspace proprio, separado do `Local_RAG`.

> Atualizacao: o estado mais novo da implementacao agora esta consolidado em `docs/12-orquestra-v2-memorygraph-workspace.md`, com `MemoryGraph V2`, `Workspace Multimodal` e shell desktop macOS.

## Objetivo
Criar um ambiente unico para:
- conversar com providers remotos e locais;
- manter memoria personalizada e evolutiva;
- consultar, curar e exportar conhecimento pelo `RAG`;
- preparar e acompanhar jobs remotos;
- registrar artefatos, adapters e deploys por projeto.

## Estrutura
- backend: `orquestra_ai/`
- frontend: `orquestra_web/`
- scripts:
  - `scripts/start_orquestra_api.sh`
  - `scripts/start_orquestra_web.sh`
  - `scripts/build_orquestra_web.sh`
  - `scripts/start_orquestra_stack.sh`

## Providers do v1
- `lmstudio`
- `openai`
- `anthropic`
- `deepseek`
- `ollama`

## Conectores remotos do v1
- `ec2`
- `sagemaker_notebook_job`
- `kaggle_kernel`
- `databricks_job`

No ciclo atual, `EC2` entra como conector mais concreto. Os demais aparecem como stubs operacionais do catalogo, com readiness baseada em variaveis de ambiente.

## Fluxo padrao
1. escolher projeto, provider e modelo no `Workspace UI`
2. conversar pelo `Assistant Workspace`
3. promover fatos e contexto para memoria
4. executar consultas no `RAG Studio`
5. registrar artifacts e benchmarks no `Model Hub`
6. preparar jobs remotos no `Train Ops`

## Operacao local
### API
```bash
cd ~/Desenvolvimento/Orquestra
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-orquestra.txt
./scripts/start_orquestra_api.sh
```

### Frontend
```bash
cd ~/Desenvolvimento/Orquestra
./scripts/start_orquestra_web.sh
```

### Stack em background
```bash
cd ~/Desenvolvimento/Orquestra
./scripts/start_orquestra_stack.sh
```

## Endpoints principais
- `GET /api/health`
- `GET /api/providers`
- `GET /api/models`
- `GET /api/connectors`
- `GET /api/projects`
- `POST /api/projects`
- `GET /api/chat/sessions`
- `GET /api/chat/sessions/{id}/messages`
- `POST /api/chat/stream`
- `GET /api/memory`
- `POST /api/memory/upsert`
- `POST /api/rag/query`
- `GET /api/training/jobs`
- `POST /api/training/jobs`
- `GET /api/remote/jobs`
- `POST /api/remote/jobs`
- `GET /api/registry/models`
- `POST /api/registry/models`

## Notas de projeto
- `claude-code/v1` deve seguir somente como referencia de UX e arquitetura, nao como base de codigo.
- o `rag/llm.py` agora aceita providers do gateway sem quebrar o fluxo RAG antigo.
- o frontend novo e `chat-first`, mas unifica memoria, RAG, modelos, jobs e configuracao no mesmo shell.
