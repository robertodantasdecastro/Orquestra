# Instalacao e Validacao no macOS

## Objetivo

Este guia cobre o fluxo oficial para:

- preparar o ambiente local
- subir API, web, desktop e Train Plane
- instalar o Orquestra como app macOS
- gerar e validar o instalador/desinstalador grafico
- validar backend, frontend, desktop e smoke operacional
- habilitar providers reais quando desejado

Para operacao do produto no dia a dia, consulte [docs/02-manual-operacional.md](./02-manual-operacional.md).

## Pre-requisitos

Obrigatorios:

- macOS
- `python3.12` preferencialmente
- `node` + `npm`
- `rustup` + `cargo`

Opcionais, conforme o caso:

- `LM Studio`
- `ffmpeg`
- `ffprobe`
- `whisper`
- proxy Tor local para fetch `via_tor`

## Bootstrap do repositorio

Para um Mac novo ou sem dependencias, prefira primeiro o instalador completo:

```bash
./scripts/install_orquestra_macos_full.sh --check-only
./scripts/install_orquestra_macos_full.sh
```

Guia detalhado:

- [docs/05-instalador-completo-macos.md](./05-instalador-completo-macos.md)
- [docs/07-instalador-grafico-macos.md](./07-instalador-grafico-macos.md)

Se o ambiente ja tem Python, Node, Rust e dependencias basicas, use o bootstrap direto:

```bash
cd /caminho/para/Orquestra
./scripts/bootstrap_orquestra.sh
```

O bootstrap:

- cria `.venv` quando necessario
- instala dependencias Python
- instala dependencias do frontend
- inicializa `.env` a partir de `.env.example` quando ainda nao existir

## Modos de execucao

### API local

```bash
./scripts/start_orquestra_api.sh
```

Endereco padrao:

```text
http://127.0.0.1:8808
```

### Web

```bash
./scripts/start_orquestra_web.sh
```

Endereco padrao:

```text
http://127.0.0.1:4177
```

### Stack local completa

```bash
./scripts/start_orquestra_stack.sh
```

### Desktop

```bash
./scripts/start_orquestra_desktop.sh
```

### Train Plane local/simulado

```bash
./scripts/start_orquestra_trainplane.sh
```

## Validacao oficial do repositório

```bash
./scripts/validate_orquestra.sh
```

Essa e a porta oficial de validacao. Ela cobre:

- `python -m py_compile`
- `pytest -q`
- `bash -n` nos scripts shell
- `vitest`
- `tsc -b`
- `vite build`
- `cargo check`
- `validate_orquestra_macos_package.sh` quando `.app` e `.dmg` estao disponiveis
- smoke da API para sessao, memoria, planner, workflow, workspace, RAG, OSINT e Train Plane local

Observacoes:

- por padrao, a validacao nao gasta credito em providers reais
- o smoke principal continua funcional em modo local/mock

## Smoke real opcional de providers

Checklist rapido:

```bash
./scripts/check_orquestra_providers.sh
```

Validacao estrita de um provider:

```bash
./scripts/check_orquestra_providers.sh --strict --require lmstudio
./scripts/check_orquestra_providers.sh --strict --require openai
```

Smoke real fim a fim:

```bash
./scripts/validate_orquestra.sh --real-provider lmstudio
ORQUESTRA_VALIDATE_REAL_PROVIDERS=openai ./scripts/validate_orquestra.sh
./scripts/validate_orquestra_real_provider_smoke.sh --provider openai
```

Variaveis comuns:

- `OPENAI_API_KEY`
- `ANTHROPIC_API_KEY`
- `DEEPSEEK_API_KEY`
- `ORQUESTRA_LITELLM_PROXY_URL`
- `LMSTUDIO_API_BASE=http://localhost:1234/v1`
- `BRAVE_SEARCH_API_KEY`
- `TAVILY_API_KEY`
- `EXA_API_KEY`
- `SHODAN_API_KEY`
- `YOUTUBE_API_KEY`
- `ORQUESTRA_OSINT_TOR_PROXY_URL=socks5h://127.0.0.1:9050`

## Build e verificacao do desktop

Build:

```bash
cd orquestra_web
npm run desktop:build
```

Verificacao com helper:

```bash
./script/build_and_run.sh --verify
```

Modos uteis:

```bash
./script/build_and_run.sh
./script/build_and_run.sh --skip-build
./script/build_and_run.sh --verify
./script/build_and_run.sh --logs
./script/build_and_run.sh --telemetry
./script/build_and_run.sh --debug
```

Artefatos esperados:

- `orquestra_web/src-tauri/target/release/bundle/macos/Orquestra AI.app`
- `orquestra_web/src-tauri/target/release/bundle/dmg/Orquestra AI_0.2.0_aarch64.dmg`

Validacao do pacote:

```bash
./scripts/validate_orquestra_macos_package.sh
```

## Build do instalador grafico completo

O DMG simples gerado pelo Tauri e apenas o pacote do app. O wizard completo usa apps dedicados para instalacao e desinstalacao:

```bash
./scripts/build_orquestra_macos_graphical_installer.sh
```

Artefatos esperados:

- `orquestra_web/src-tauri/target/release/bundle/macos/Orquestra AI.app`
- `orquestra_web/src-tauri/target/release/bundle/macos/Orquestra Installer.app`
- `orquestra_web/src-tauri/target/release/bundle/macos/Orquestra Uninstaller.app`
- `orquestra_web/src-tauri/target/release/bundle/dmg/Orquestra AI Installer_0.2.0_aarch64.dmg`

Validacao:

```bash
./scripts/validate_orquestra_macos_graphical_installer.sh
open "orquestra_web/src-tauri/target/release/bundle/dmg/Orquestra AI Installer_0.2.0_aarch64.dmg"
```

O instalador grafico chama os scripts oficiais por baixo em modo machine-readable e mostra:

- diagnostico do Mac
- dependencias obrigatorias
- opcionais como LM Studio, Ollama, Tor, Brave e ffmpeg
- runtime e storage
- providers e chaves
- resultado da instalacao

O desinstalador grafico mostra:

- instalacao detectada
- itens removiveis
- backup antes de apagar dados sensiveis
- modos `Seguro seletivo`, `Preservar dependencias` e `Remover tudo`

## Instalacao do app no macOS

Instalacao completa do zero:

```bash
./scripts/install_orquestra_macos_full.sh
```

Diagnostico sem alterar o sistema:

```bash
./scripts/install_orquestra_macos_full.sh --check-only
```

Instalacao padrao para ambiente ja preparado:

```bash
./scripts/install_orquestra_macos.sh
```

O instalador:

- valida o ambiente
- gera o bundle quando necessario
- copia `Orquestra AI.app` para `~/Applications`
- cria o launcher `~/Applications/Orquestra.app`
- publica `~/Applications/Orquestra Uninstaller.app`
- sincroniza runtime para `~/Library/Application Support/Orquestra/runtime`
- cria `~/Library/Application Support/Orquestra/runtime/config/runtime.json`
- cria backup do banco antes do upgrade quando aplicavel
- grava manifesto de instalacao
- registra o LaunchAgent `ai.orquestra.api`

Opcoes uteis:

```bash
./scripts/install_orquestra_macos.sh --skip-build
./scripts/install_orquestra_macos.sh --no-launch-agent
./scripts/install_orquestra_macos.sh --no-runtime-sync
./scripts/install_orquestra_macos.sh --open
./scripts/install_orquestra_macos.sh --no-wait-api
./scripts/install_orquestra_macos.sh --skip-package-verify
./scripts/install_orquestra_macos.sh --install-dir "$HOME/Applications/Orquestra AI.app"
```

Variaveis de apoio:

```bash
ORQUESTRA_INSTALL_API_WAIT_SECONDS=120 ./scripts/install_orquestra_macos.sh --skip-build
ORQUESTRA_INSTALL_BACKUP_LIMIT=8 ./scripts/install_orquestra_macos.sh --skip-build
```

## Desinstalacao

Desinstalacao seletiva completa:

```bash
./scripts/uninstall_orquestra_macos_full.sh --dry-run
./scripts/uninstall_orquestra_macos_full.sh --mode safe
```

Preservar dependencias globais:

```bash
./scripts/uninstall_orquestra_macos_full.sh --mode preserve-deps
```

Remover itens especificos com backup:

```bash
./scripts/uninstall_orquestra_macos_full.sh --select memory,osint,workspace,db --backup-data
```

Desinstalador base:

```bash
./scripts/uninstall_orquestra_macos.sh
```

Opcoes:

```bash
./scripts/uninstall_orquestra_macos.sh --purge-data
./scripts/uninstall_orquestra_macos.sh --no-launch-agent
```

Por padrao o desinstalador:

- remove o app
- remove o LaunchAgent, salvo se `--no-launch-agent` for usado
- preserva dados e logs do usuario

## Caminhos e artefatos locais

- API: `http://127.0.0.1:8808`
- Web: `http://127.0.0.1:4177`
- App instalado: `~/Applications/Orquestra AI.app`
- Launcher rapido: `~/Applications/Orquestra.app`
- Desinstalador grafico: `~/Applications/Orquestra Uninstaller.app`
- Runtime instalado: `~/Library/Application Support/Orquestra/runtime`
- Runtime bootstrap: `~/Library/Application Support/Orquestra/runtime/config/runtime.json`
- Logs: `~/Library/Logs/Orquestra`
- Manifesto: `~/Library/Application Support/Orquestra/runtime/experiments/orquestra/install/install_manifest.json`
- Backups: `~/Library/Application Support/Orquestra/runtime/experiments/orquestra/install/backups`

## Settings Center apos a instalacao

Depois da primeira abertura, use `Settings` para conferir e ajustar:

- `Runtime & Storage`: caminhos reais, quotas, destinos locais/externos e storage frio
- `Secrets & Providers`: chaves no Keychain e providers habilitados
- `Models & Router`: catalogo de modelos, defaults e simulacao de roteamento
- `Agents`: especialistas por tarefa e politica de privacidade

SQLite e indices ativos de RAG/memoria nao devem ser apontados diretamente para S3/SFTP. Esses backends sao suportados como storage frio para backup, export, dataset, evidencias e snapshots.

## Procedimento recomendado para primeira subida

1. Rode `./scripts/bootstrap_orquestra.sh`.
2. Rode `./scripts/validate_orquestra.sh`.
3. Suba `./scripts/start_orquestra_stack.sh`.
4. Abra `http://127.0.0.1:4177` ou o desktop.
5. Crie um projeto e uma sessao.
6. Se for usar busca web, configure as chaves dos conectores desejados.
7. Se for usar baseline local, ligue o `LM Studio`.
8. Se for testar `.onion`, suba o proxy Tor local antes.

## Troubleshooting rapido

### API nao responde

```bash
curl -fsS http://127.0.0.1:8808/api/health
```

Se instalado:

```bash
launchctl print gui/$UID/ai.orquestra.api
tail -n 100 ~/Library/Logs/Orquestra/api.stderr.log
```

### Web nao sobe

```bash
./scripts/start_orquestra_web.sh
```

### Provider local offline

```bash
curl -fsS http://localhost:1234/v1/models
```

### OSINT sem resultados

Verifique:

- se o conector esta `enabled`
- se o conector esta `ready`
- se a credencial esperada esta no ambiente
- se a investigacao habilitou o conector correto
- se o `Source Registry` tem seeds compatíveis para fallback

### Fetch `via_tor` falhou

Verifique:

- se o proxy local realmente responde em `ORQUESTRA_OSINT_TOR_PROXY_URL`
- se o conector permite `via_tor`
- se a investigacao foi executada com `via_tor=true`

### Build desktop falhou

Revise:

- `orquestra_web/src-tauri/target`
- `cargo check`
- `./scripts/validate_orquestra.sh`
