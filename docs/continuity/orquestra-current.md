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
