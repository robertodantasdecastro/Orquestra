# Checkpoint e Retomada do Orquestra

Este documento e o espelho humano do handoff canonico salvo em `.codex/memory/orquestra-continuity.md`.

## Fontes minimas para retomar
Quando uma sessao do Codex for interrompida, nao e necessario reler toda a thread. Use apenas:

1. `AGENTS.md`
2. `.codex/memory/orquestra-continuity.md`
3. `git log --oneline -5`
4. `git status --short`

## Protocolo por micro-etapa
Ao concluir uma etapa:

1. atualize `.codex/memory/orquestra-continuity.md`
2. rode a menor validacao significativa da etapa
3. rode `git diff --check`
4. capture `git status --short`
5. crie um commit
6. faca `git push`

## Quando criar checkpoint intermediario extra
Crie um checkpoint mesmo antes de encerrar a etapa quando houver:

- mudanca em backend e frontend ao mesmo tempo
- mudanca de schema/modelos
- mudanca na validacao oficial
- antes de testes longos
- antes de trocar de login ou encerrar a sessao

## Prompt curto recomendado

```text
Leia AGENTS.md, .codex/memory/orquestra-continuity.md, git log --oneline -5 e git status --short. Continue a implementacao a partir da Proxima acao exata, sem reanalisar todo o projeto.
```

## Estado atual esperado
Consulte sempre `.codex/memory/orquestra-continuity.md` para:

- branch atual
- ultimo commit
- etapa concluida
- validacoes executadas
- pendencias abertas
- proxima acao exata
- arquivos principais tocados

## Estado atual do processo
O ciclo atual em `main` agora inclui, alem da paridade alta anterior:

- memoria hibrida
- compactacao de contexto
- planner hibrido
- workflows locais multi-step
- `OSINT Lab` com:
  - busca web nativa
  - conectores administráveis
  - source registry
  - evidencias e claims rastreáveis
  - promocao para memoria com proveniencia preservada
  - uso de evidencias no `Assistant Workspace` e no `rag/query`
- documentacao reestruturada com:
  - guia de documentacao
  - manual operacional reescrito
  - guia dedicado do `OSINT Lab`
  - guia dedicado do `Remote Train Plane`
- desktop macOS com instalador/desinstalador
- README e docs reescritos para a superficie atual do produto
- instalador completo macOS com:
  - diagnostico `check-only`
  - instalacao de dependencias obrigatorias
  - guia de opcionais e chaves
  - desinstalador seletivo com backup de memorias/dados
- `Train Plane` remoto dedicado com:
  - backend `orquestra_trainplane/`
  - proxy local `/api/remote/trainplane/*`
  - painel no `Execution Center`
  - sync de `base model` e `dataset bundle`
  - `training runs`, `artifacts`, `evaluations` e `comparisons`
  - cobertura de testes e validacao oficial

## O que ainda falta para encerrar o processo mais amplo
Os proximos itens, fora do nucleo ja entregue, sao:

1. validar manualmente o `OSINT Lab` com providers reais e, quando necessario, proxy Tor configurado
2. validar manualmente o `Train Plane` com `LM Studio` local como baseline real
3. validar manualmente o `Train Plane` com um provider real por `API key`
4. substituir o modo remoto simulado por integracoes reais `S3 multipart + CloudWatch + SSM`
5. OCR/transcricao opcional mais rica para assets multimodais
6. assinatura/notarizacao para distribuicao publica

## Nova base para o proximo ciclo
Antes de habilitar providers reais, use:

```bash
./scripts/check_orquestra_providers.sh
```

Para travar um provider minimo:

```bash
./scripts/check_orquestra_providers.sh --strict --require lmstudio
./scripts/check_orquestra_providers.sh --strict --require openai
```

Para um smoke fim a fim opcional por provider:

```bash
./scripts/validate_orquestra.sh --real-provider lmstudio
./scripts/validate_orquestra_real_provider_smoke.sh --provider openai
```
