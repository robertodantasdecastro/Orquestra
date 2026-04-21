# Instalacao e Validacao no macOS

## Objetivo

Este guia cobre o fluxo oficial para:

- preparar o ambiente local
- subir API, web, desktop e Train Plane
- instalar o Orquestra como app macOS
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

## Instalacao do app no macOS

Instalacao padrao:

```bash
./scripts/install_orquestra_macos.sh
```

O instalador:

- valida o ambiente
- gera o bundle quando necessario
- copia `Orquestra AI.app` para `~/Applications`
- sincroniza runtime para `~/Library/Application Support/Orquestra/runtime`
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

Padrao:

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
- Runtime instalado: `~/Library/Application Support/Orquestra/runtime`
- Logs: `~/Library/Logs/Orquestra`
- Manifesto: `~/Library/Application Support/Orquestra/runtime/experiments/orquestra/install/install_manifest.json`
- Backups: `~/Library/Application Support/Orquestra/runtime/experiments/orquestra/install/backups`

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
