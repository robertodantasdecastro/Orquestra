# Settings Center, Storage Fabric, Cofre de Chaves e Router Interno

## Objetivo

Este guia descreve a nova base de configuracao do Orquestra para operacao web e desktop macOS. Ela prepara o produto para instalar, validar e operar com:

- runtime instalado por usuario
- armazenamento multilocal gerenciavel
- cofre de chaves no macOS Keychain
- catalogo de modelos
- router interno de IA
- agentes especializados

O foco da V1 e manter o Orquestra `local-first`, com um hub local de processamento e storage remoto apenas para dados frios.

## Runtime padrao

O runtime padrao instalado fica em:

```text
~/Library/Application Support/Orquestra/runtime/
```

O bootstrap do runtime fica em:

```text
~/Library/Application Support/Orquestra/runtime/config/runtime.json
```

Esse arquivo existe para localizar o banco, o data root, o Qdrant e as politicas basicas antes de o SQLite estar disponivel.

Exemplo conceitual:

```json
{
  "runtime_dir": "/Users/usuario/Library/Application Support/Orquestra/runtime",
  "data_root": "/Users/usuario/Library/Application Support/Orquestra/runtime/experiments/orquestra",
  "database_url": "sqlite:////Users/usuario/Library/Application Support/Orquestra/runtime/experiments/orquestra/orquestra_v2.db",
  "storage_policy": "local_processing_hub"
}
```

Em desenvolvimento, se `runtime.json` nao existir ou nao estiver explicitamente habilitado, o Orquestra preserva o comportamento do repositorio local.

## Diretorios principais

Dentro do runtime instalado, os defaults sao:

- `experiments/orquestra/orquestra_v2.db`: banco SQLite ativo
- `experiments/orquestra/memorygraph`: memoria duravel e memdir
- `experiments/orquestra/rag_runtime`: runtime RAG/Chroma
- `experiments/orquestra/qdrant`: indice Qdrant local quando usado
- `experiments/orquestra/osint`: investigacoes, capturas, evidencias e claims
- `experiments/orquestra/workspace`: scans e extracoes de workspace
- `experiments/orquestra/workflows`: runs, logs e artefatos de workflows
- `experiments/orquestra/trainplane`: metadados locais do Train Plane
- `experiments/orquestra/install/backups`: backups de instalacao e migracao

## Settings Center

A area `Settings` aparece na navegacao principal do app web/desktop. Ela tem quatro blocos operacionais.

### Runtime & Storage

Mostra:

- caminho real do runtime
- caminho real do `data_root`
- politica de storage
- storage locations cadastrados
- assignments por dominio
- quotas e health basico

Permite cadastrar destinos:

- `local_path`
- `external_drive`
- `cloud_mounted`
- `s3_compatible`
- `sftp`
- `readonly_archive`

### Secrets & Providers

Permite cadastrar segredos por provider sem exibir o valor depois. No macOS, o destino padrao e o Keychain:

```text
service: ai.orquestra.secrets
```

O SQLite guarda apenas:

- `secret_ref`
- provider
- label
- status
- metadados nao sensiveis

O `.env` continua aceito como fallback/importacao e modo de desenvolvimento, mas nao e o cofre principal quando a chave e cadastrada pela UI.

### Models & Router

Mostra politicas e permite:

- atualizar catalogo de modelos por provider
- simular decisao de roteamento
- definir preferencia por provider/modelo
- registrar decisoes para auditoria operacional

### Agents

Mostra agentes especializados com:

- tarefa
- provider/modelo preferido
- nivel de privacidade
- tags de roteamento
- estado habilitado/desabilitado

## Storage Fabric

O Storage Fabric separa processamento quente de armazenamento frio.

### Storage quente

Usado para dados ativos e leitura/escrita frequente:

- SSD interno
- SSD externo
- volume montado confiavel
- pasta cloud mounted apenas com alerta e uso controlado

Dominios quentes:

- `sqlite_active`
- `rag_vector_active`
- `memory_hot`
- `workspace_hot`
- `workflow_hot`

### Storage frio

Usado para backup, export, dataset, evidencia fria e snapshots:

- S3 compativel
- SFTP
- archive somente leitura

Dominios frios:

- `backup_cold`
- `export_cold`
- `dataset_cold`
- `osint_evidence_cold`
- `model_artifact_cold`

Regra fixa:

- SQLite ativo nao roda diretamente em S3/SFTP.
- Chroma/Qdrant ativo nao roda diretamente em S3/SFTP.
- RAG so usa fonte fria depois de hidratacao local.

## APIs principais

Runtime:

```text
GET /api/settings/runtime
PUT /api/settings/runtime
```

Storage:

```text
GET /api/settings/storage/locations
POST /api/settings/storage/locations
PATCH /api/settings/storage/locations/{location_id}
DELETE /api/settings/storage/locations/{location_id}
POST /api/settings/storage/test
POST /api/settings/storage/locations/{location_id}/test
GET /api/settings/storage/assignments
PUT /api/settings/storage/assignments/{domain}
POST /api/settings/storage/migrations/plan
POST /api/settings/storage/migrations
GET /api/settings/storage/migrations/{migration_id}
```

Segredos:

```text
GET /api/settings/secrets
POST /api/settings/secrets
POST /api/settings/secrets/{secret_id}/test
DELETE /api/settings/secrets/{secret_id}
```

Modelos, router e agentes:

```text
POST /api/settings/models/refresh
GET /api/settings/models
GET /api/settings/model-router/policies
POST /api/settings/model-router/policies
PATCH /api/settings/model-router/policies/{policy_id}
DELETE /api/settings/model-router/policies/{policy_id}
POST /api/settings/model-router/simulate
GET /api/settings/agents
POST /api/settings/agents
PATCH /api/settings/agents/{agent_id}
DELETE /api/settings/agents/{agent_id}
```

## Router interno

O `OrquestraModelRouter` fica acima do gateway de providers. Ele escolhe provider/modelo considerando:

- preset da sessao
- tipo de tarefa
- politica `local_only`
- provider solicitado
- modelo solicitado
- disponibilidade do provider
- politicas persistidas
- catalogo de modelos

Modos previstos:

- `single_best`
- `fallback_chain`
- `specialist_handoff`
- `parallel_compare`

A V1 registra a decisao em `ModelRouteDecision` e devolve a justificativa no chat/RAG quando aplicavel.

## Impacto em desempenho e confiabilidade

O desempenho melhora quando dados quentes ficam proximos do processamento local. O modelo multilocal nao deve degradar as respostas corretas se a regra de hidratacao for respeitada:

- memoria e RAG ativos continuam locais
- remoto frio nao entra direto no prompt
- fontes frias precisam ser validadas/hidratadas antes de uso
- decisoes do router ficam auditaveis
- segredos nao circulam por logs nem banco

O risco principal e apontar dados ativos para storage instavel. Por isso o backend bloqueia SQLite/RAG ativo em S3/SFTP e a UI deve mostrar alertas para cloud mounted.

## Validacao

Validacoes recomendadas:

```bash
.venv/bin/pytest -q tests/test_settings_installer.py
npm --prefix orquestra_web run test -- --run
npm --prefix orquestra_web run build
```

Contratos de instalacao:

```bash
./scripts/install_orquestra_macos_full.sh --check-only --json
./scripts/uninstall_orquestra_macos_full.sh --dry-run --json
./scripts/check_orquestra_macos_installation.sh --check-only --json
```
