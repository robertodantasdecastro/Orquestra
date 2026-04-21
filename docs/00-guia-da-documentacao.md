# Guia da Documentacao

## Objetivo

Este arquivo organiza a documentacao oficial do Orquestra e indica qual documento ler em cada situacao.

Identidade visual do projeto:

```text
Logo1.png -> wordmark com texto
Logo2.png -> icon-only
assets/brand/orquestra-logo.png -> wordmark canonico
assets/brand/orquestra-icon.png -> icone canonico
```

## Leitura recomendada por perfil

### Primeiro acesso

1. [README.md](../README.md)
2. [docs/01-instalacao-validacao-macos.md](./01-instalacao-validacao-macos.md)
3. [docs/05-instalador-completo-macos.md](./05-instalador-completo-macos.md)
4. [docs/07-instalador-grafico-macos.md](./07-instalador-grafico-macos.md), se quiser o wizard grafico
5. [docs/02-manual-operacional.md](./02-manual-operacional.md)

### Operacao diaria

1. [docs/02-manual-operacional.md](./02-manual-operacional.md)
2. [docs/06-settings-center-storage-fabric-router.md](./06-settings-center-storage-fabric-router.md), se houver ajuste de storage, chaves, modelos ou agentes
3. [docs/03-osint-lab.md](./03-osint-lab.md), se houver investigacao web
4. [docs/04-train-plane.md](./04-train-plane.md), se houver treino/comparacao

### Arquitetura e implementacao

1. [docs/11-orquestra-ai-control-plane.md](./11-orquestra-ai-control-plane.md)
2. [docs/12-orquestra-v2-memorygraph-workspace.md](./12-orquestra-v2-memorygraph-workspace.md)
3. [docs/06-settings-center-storage-fabric-router.md](./06-settings-center-storage-fabric-router.md)

### Retomada apos interrupcao

1. [docs/continuity/orquestra-current.md](./continuity/orquestra-current.md)
2. [.codex/memory/orquestra-continuity.md](../.codex/memory/orquestra-continuity.md)

## Mapa dos documentos

- [README.md](../README.md)
  - visao geral do produto, recursos, inicio rapido e mapa da doc

- [docs/01-instalacao-validacao-macos.md](./01-instalacao-validacao-macos.md)
  - bootstrap
  - stack local
  - instalacao e desinstalacao no macOS
  - validacao oficial e smoke real

- [docs/02-manual-operacional.md](./02-manual-operacional.md)
  - uso completo da UI
  - fluxo recomendado de trabalho
  - procedimentos comuns

- [docs/03-osint-lab.md](./03-osint-lab.md)
  - conectores administraveis
  - source registry
  - evidencias, claims, memoria e export

- [docs/04-train-plane.md](./04-train-plane.md)
  - configuracao remota
  - sync de base model e dataset
  - runs, artifacts, evaluations e comparisons

- [docs/05-instalador-completo-macos.md](./05-instalador-completo-macos.md)
  - instalacao do zero
  - dependencias obrigatorias e opcionais
  - logins, API keys e `.env`
  - desinstalacao seletiva e backup de memorias

- [docs/06-settings-center-storage-fabric-router.md](./06-settings-center-storage-fabric-router.md)
  - runtime.json
  - storage multilocal e quotas
  - Keychain e fallback `.env`
  - providers, catalogo de modelos, router e agentes

- [docs/07-instalador-grafico-macos.md](./07-instalador-grafico-macos.md)
  - `Orquestra Installer.app`
  - `Orquestra Uninstaller.app`
  - DMG completo do wizard
  - contratos JSON usados pela UI grafica

- [docs/11-orquestra-ai-control-plane.md](./11-orquestra-ai-control-plane.md)
  - dominios do sistema
  - APIs publicas
  - arquitetura operacional

- [docs/12-orquestra-v2-memorygraph-workspace.md](./12-orquestra-v2-memorygraph-workspace.md)
  - memoria
  - compactacao
  - planner
  - workflow
  - workspace
  - runtime

- [docs/continuity/orquestra-current.md](./continuity/orquestra-current.md)
  - protocolo de checkpoint e retomada

## Fonte canonica de continuidade

Para retomada com baixo uso de contexto, a fonte canonica e:

- `.codex/memory/orquestra-continuity.md`

O documento em `docs/continuity/` e o espelho humano resumido.

## Regra de manutencao

Toda mudanca relevante em:

- superficie da UI
- fluxo operacional
- scripts de bootstrap, install ou validate
- Settings Center, storage, providers, router, memoria, RAG, workflow, OSINT ou Train Plane

deve atualizar pelo menos:

- `README.md`
- o documento operacional ou tecnico afetado
- o handoff de continuidade quando a mudanca altera o estado do projeto
