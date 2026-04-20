# Orquestra AI

`Orquestra AI` e o control plane unificado da aplicacao `Orquestra`. A proposta e concentrar `RAG`, memoria, leitura multimodal, jobs remotos e operacao de modelos em um workspace proprio, separado do `Local_RAG`.

> Atualizacao: o estado mais novo da implementacao agora esta consolidado em `docs/12-orquestra-v2-memorygraph-workspace.md`, com `MemoryGraph V2`, memoria associada ao RAG, `Workspace Multimodal` e shell desktop macOS.
> Manual operacional completo: `docs/02-manual-operacional.md`.

## Objetivo
Criar um ambiente unico para:
- conversar com providers remotos e locais;
- manter memoria personalizada e evolutiva;
- consultar, curar e exportar conhecimento pelo `RAG`;
- preparar e acompanhar jobs remotos;
- registrar artefatos, adapters e deploys por projeto.

O control plane deve permanecer `local-first`: o Mac coordena a operacao, a API local responde em `127.0.0.1:8808`, a UI web/desktop consome os mesmos endpoints e os conectores remotos podem ficar indisponiveis sem travar chat, memoria, RAG ou workspace.

## Estrutura
- backend: `orquestra_ai/`
- frontend: `orquestra_web/`
- marca: `assets/brand/`
- scripts:
  - `scripts/start_orquestra_api.sh`
  - `scripts/start_orquestra_web.sh`
  - `scripts/build_orquestra_web.sh`
  - `scripts/start_orquestra_stack.sh`
  - `scripts/install_orquestra_macos.sh`
  - `scripts/uninstall_orquestra_macos.sh`
  - `scripts/validate_orquestra_macos_package.sh`
  - `script/build_and_run.sh`

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

No ciclo atual, o catalogo de conectores ja existe, mas a execucao remota real segue adiada. `SageMaker`, `Kaggle` e `Databricks` aparecem como stubs operacionais do catalogo, com readiness baseada em variaveis de ambiente, e a integracao de `EC2` fica explicitamente para uma fase posterior.

## Fluxo padrao
1. escolher projeto, provider e modelo no `Workspace UI`
2. criar sessao com objetivo, preset e politica de memoria/RAG
3. conversar pelo `Assistant Workspace`
4. revisar `Memory Inbox` antes de promover memoria ou dataset
5. executar consultas no `RAG Studio` com memoria aprovada quando houver
6. registrar artifacts e benchmarks no `Model Hub`
7. preparar jobs remotos no `Train Ops`

## Recursos principais
- `Assistant Workspace`: conversa multi-provider com resumo, transcript, `Session Profile`, recall e painel `Memoria & RAG`.
- `Memory Studio`: memoria duravel, topicos, promocao, `Memory Inbox` e training candidates.
- `Workspace Browser`: anexar diretorios, inventariar, extrair, abrir e memorizar ativos.
- `RAG Studio`: consulta local ao engine RAG integrado ao gateway e a colecao Chroma `orquestra_memory_v1`.
- `Execution Center`: providers, conectores, jobs, registry, comparacao e acoes operacionais.
- `Operations Dashboard`: status de servicos, processos, memoria, execucao e artefatos macOS.

## Operacao local
### API
```bash
cd /caminho/para/Orquestra
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-orquestra.txt
./scripts/start_orquestra_api.sh
```

### Frontend
```bash
cd /caminho/para/Orquestra
./scripts/start_orquestra_web.sh
```

### Stack em background
```bash
cd /caminho/para/Orquestra
./scripts/start_orquestra_stack.sh
```

### Desktop macOS
```bash
cd /caminho/para/Orquestra
./script/build_and_run.sh --verify
```

Instalacao local:
```bash
./scripts/install_orquestra_macos.sh
```

O instalador copia o `.app` para `~/Applications`, espelha o runtime em `~/Library/Application Support/Orquestra/runtime` e registra o LaunchAgent `ai.orquestra.api` apontando para esse runtime local.
Cada upgrade com sync de runtime cria backup do banco local e atualiza o manifesto de instalação em `experiments/orquestra/install/install_manifest.json`.

Validacao de pacote:
```bash
./scripts/validate_orquestra_macos_package.sh
```

## Endpoints principais
- `GET /api/health` retorna `app_version`, `schema_version`, `schema_target_version`, `migration_required` e `runtime`
- `GET /api/providers`
- `GET /api/models`
- `GET /api/connectors`
- `GET /api/projects`
- `POST /api/projects`
- `GET /api/chat/sessions`
- `POST /api/chat/sessions`
- `GET /api/chat/sessions/{id}/profile`
- `PUT /api/chat/sessions/{id}/profile`
- `GET /api/chat/sessions/{id}/messages`
- `POST /api/chat/stream`
- `GET /api/memory`
- `GET /api/memory/candidates`
- `POST /api/memory/candidates/{id}/approve`
- `POST /api/memory/candidates/{id}/reject`
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
- `training jobs` e `remote jobs` hoje registram intencao e metadados na aplicacao, mas ainda nao despacham execucao remota real.
