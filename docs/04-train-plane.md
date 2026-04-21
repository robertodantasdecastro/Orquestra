# Remote Train Plane

## Objetivo

O `Remote Train Plane` e o subsistema do Orquestra para:

- registrar `base models`
- sincronizar `dataset bundles`
- criar `training runs`
- acompanhar `metrics`, `artifacts`, `evaluations` e `comparisons`
- decidir promocao de artefatos

## Estado atual

O fluxo funcional atual e adequado para:

- operacao local/remota validavel
- gerenciamento de runs
- artifacts e comparacoes
- integracao com o `Execution Center`
- teste de baseline e candidate

As integracoes AWS reais planejadas para a proxima etapa ainda nao substituiram o modo atual. Em outras palavras:

- a topologia e os contratos ja existem
- o fluxo operacional ja pode ser exercitado
- `S3 multipart + CloudWatch + SSM` ainda sao a proxima expansao

## Componentes

### Servico remoto dedicado

- `orquestra_trainplane/app.py`
- `orquestra_trainplane/worker.py`
- `orquestra_trainplane/models.py`
- `orquestra_trainplane/services.py`

### Proxy local dentro do Orquestra

- `GET/PUT /api/remote/trainplane/config`
- `POST /api/remote/trainplane/test-connection`
- `POST /api/remote/trainplane/sync/base-model`
- `POST /api/remote/trainplane/sync/dataset-bundle`
- `GET/POST /api/remote/trainplane/runs`
- `GET /api/remote/trainplane/runs/{id}`
- `POST /api/remote/trainplane/runs/{id}/cancel`
- `GET /api/remote/trainplane/runs/{id}/stream`
- `GET /api/remote/trainplane/artifacts`
- `POST /api/remote/trainplane/artifacts/{id}/merge`
- `POST /api/remote/trainplane/artifacts/{id}/promote`
- `GET/POST /api/remote/trainplane/evaluations`
- `GET/POST /api/remote/trainplane/comparisons`

## Fluxo operacional

1. configurar o endpoint remoto e credenciais
2. testar conexao
3. sincronizar `base model`
4. sincronizar `dataset bundle`
5. criar `training run`
6. acompanhar progresso e eventos
7. revisar artifacts
8. executar `evaluation` e `comparison`
9. promover artefato quando aprovado

## O que existe no Execution Center

O painel `Remote Train Plane` expõe:

- `Access & Config`
- `Base Models & Datasets`
- `Training Runs`
- `Live Metrics`
- `Evaluation Lab`
- `Promotion & Registry`

## Base models

O fluxo atual aceita:

- referencia a modelo base
- upload/sync de artefato base
- registro remoto para uso em runs

Use esse bloco para:

- nomear o modelo
- definir a origem
- registrar o formato
- manter metadados de treino

## Dataset bundles

`Dataset bundles` nascem do Orquestra local e podem combinar:

- memoria aprovada
- claims aprovadas
- bundles locais exportados

Recomendacao:

- nao sincronize bundle sem revisar licenca, retencao e `training_allowed`

## Training runs

Um `training run` registra:

- projeto
- modelo base
- bundle de dataset
- perfil de treino
- status
- metrics
- checkpoints
- artefato final

Estados comuns:

- `queued`
- `running`
- `succeeded`
- `failed`
- `cancelled`

## Evaluation e Comparison

O fluxo de avaliacao serve para comparar o candidate com:

- `LM Studio` local
- provider real via `API key`
- baseline registrado no proprio Train Plane

### Evaluation

Use quando quiser:

- scores agregados
- suite fixa
- benchmark por caso

### Comparison

Use quando quiser:

- comparacao lado a lado
- baseline vs candidate
- revisao manual e relatorio de diferencas

## Procedimento recomendado

### Primeiro uso

1. suba o servico remoto com `./scripts/start_orquestra_trainplane.sh`
2. configure o endpoint no `Execution Center`
3. teste a conexao
4. sincronize um `base model`
5. sincronize um `dataset bundle`
6. crie um `training run`
7. acompanhe o stream do run
8. revise artifacts, evaluation e comparison

### Uso com baseline local

1. ligue o `LM Studio`
2. confirme `LMSTUDIO_API_BASE`
3. execute comparacao com baseline local

### Uso com provider real

1. configure a `API key`
2. valide readiness com `./scripts/check_orquestra_providers.sh`
3. rode smoke real quando desejar

## Limites atuais

- as integracoes AWS reais ainda nao foram ligadas como backend efetivo do Train Plane
- o fluxo atual e ideal para validacao, UI, contratos, comparacao e registry
- a parte de infra definitiva continua na proxima etapa do plano global

## Validacao

Validacao principal:

```bash
./scripts/validate_orquestra.sh
```

Validar providers:

```bash
./scripts/check_orquestra_providers.sh
```

Smoke real:

```bash
./scripts/validate_orquestra.sh --real-provider lmstudio
./scripts/validate_orquestra_real_provider_smoke.sh --provider openai
```

## Proxima etapa prevista

As proximas expansoes planejadas para o `Train Plane` sao:

- `S3 multipart`
- `CloudWatch`
- `SSM`
- observabilidade AWS real
- validacao comparativa mais forte em ambiente remoto
