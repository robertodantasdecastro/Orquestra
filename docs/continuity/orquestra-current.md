# Checkpoint e Retomada do Orquestra

Este documento e o espelho humano do handoff canonico salvo em `.codex/memory/orquestra-continuity.md`.

## Fontes minimas para retomar

Quando uma sessao do Codex for interrompida, nao e necessario reler toda a thread. Use apenas:

1. `AGENTS.md`
2. `.codex/memory/orquestra-continuity.md`
3. `git log --oneline -5`
4. `git status --short`

## Estado atual do processo

A branch atual da etapa e:

```text
codex/orquestra-graphical-installer
```

O ultimo commit base antes desta etapa era:

```text
64df030
```

O ciclo atual adiciona:

- instalador grafico `Orquestra Installer.app`
- desinstalador grafico `Orquestra Uninstaller.app`
- DMG completo `Orquestra AI Installer_0.2.0_aarch64.dmg`
- contratos JSON para scripts de instalacao/desinstalacao/check
- `Settings Center`
- `Storage Fabric` local/frio
- `runtime.json`
- Keychain service `ai.orquestra.secrets`
- router interno de modelos/agentes
- logo padrao derivada de `Logo1.png`

## Artefatos principais

```text
orquestra_web/src-tauri/target/release/bundle/macos/Orquestra AI.app
orquestra_web/src-tauri/target/release/bundle/macos/Orquestra Installer.app
orquestra_web/src-tauri/target/release/bundle/macos/Orquestra Uninstaller.app
orquestra_web/src-tauri/target/release/bundle/dmg/Orquestra AI_0.2.0_aarch64.dmg
orquestra_web/src-tauri/target/release/bundle/dmg/Orquestra AI Installer_0.2.0_aarch64.dmg
```

## Validacoes executadas

- `.venv/bin/python -m py_compile ...`
- `bash -n scripts/*.sh`
- `./scripts/install_orquestra_macos_full.sh --check-only --json`
- `./scripts/uninstall_orquestra_macos_full.sh --dry-run --json`
- `.venv/bin/pytest -q`
- `npm --prefix orquestra_web run test -- --run`
- `npm --prefix orquestra_web run build`
- `cargo check`
- `./scripts/build_orquestra_macos_graphical_installer.sh`
- `./scripts/validate_orquestra_macos_package.sh`
- `./scripts/validate_orquestra_macos_graphical_installer.sh`
- `./scripts/validate_orquestra.sh`
- `git diff --check`

## Proxima acao exata

Abrir o DMG completo, testar o `Orquestra Installer.app` e o `Orquestra Uninstaller.app` em ambiente descartavel, validar providers reais no Settings Center e depois decidir entre notarizacao publica ou evolucao de storage remoto real.

Comando util:

```bash
open "orquestra_web/src-tauri/target/release/bundle/dmg/Orquestra AI Installer_0.2.0_aarch64.dmg"
```

## Prompt curto recomendado

```text
Leia AGENTS.md, .codex/memory/orquestra-continuity.md, git log --oneline -5 e git status --short. Continue a implementacao a partir da Proxima acao exata, sem reanalisar todo o projeto.
```
