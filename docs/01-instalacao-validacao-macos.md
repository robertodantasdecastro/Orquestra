# Instalacao e Validacao no macOS

## Objetivo
Este guia cobre o fluxo oficial para colocar o Orquestra em funcionamento no macOS e validar que:

- a API local responde
- a UI web builda
- o shell desktop Tauri passa em `cargo check`
- o pacote `.app`/`.dmg` pode ser validado localmente
- memoria, planner, workflow, workspace e RAG passam em smoke automatizado

Para uso diario, consulte tambem [docs/02-manual-operacional.md](./02-manual-operacional.md).

## Pre-requisitos
- macOS
- `python3.12` preferencialmente
- `node` + `npm`
- `rustup` + `cargo`
- opcionais:
  - `LM Studio`
  - `ffmpeg`
  - `ffprobe`
  - `whisper`

## Bootstrap
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
### API
```bash
./scripts/start_orquestra_api.sh
```

### Web
```bash
./scripts/start_orquestra_web.sh
```

### Stack local
```bash
./scripts/start_orquestra_stack.sh
```

### Desktop
```bash
./scripts/start_orquestra_desktop.sh
```

### Build e verificacao do desktop
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

## Validacao automatizada principal
```bash
./scripts/validate_orquestra.sh
```

Essa validacao executa:
- `python -m py_compile` no backend, RAG e utilitarios locais
- `pytest -q`
- `bash -n` nos scripts shell
- `vitest`
- `tsc -b`
- `vite build`
- `cargo check`
- `validate_orquestra_macos_package.sh` quando `.app` e `.dmg` estao disponiveis
- smoke da API cobrindo:
  - criacao de sessao com objetivo e preset
  - perfil de sessao
  - `Memory Inbox` e aprovacao de candidato
  - recall associado ao RAG
  - compactacao manual
  - planner e tarefas
  - workflow local multi-step
  - resume e transcript
  - scan de workspace, preview, extracao e memorize

Observacoes:
- o smoke usa `mock_response` para nao depender de provider remoto real
- esse comando e a porta oficial de validacao do repositório

## Build do desktop e pacote macOS
Build do desktop:
```bash
cd orquestra_web
npm run desktop:build
```

Saidas atuais:
- `orquestra_web/src-tauri/target/release/bundle/macos/Orquestra AI.app`
- `orquestra_web/src-tauri/target/release/bundle/dmg/Orquestra AI_0.2.0_aarch64.dmg`

Validacao do pacote:
```bash
./scripts/validate_orquestra_macos_package.sh
```

Essa validacao confere:
- existencia do `.app`
- `Contents/Info.plist`
- executavel `orquestra-desktop`
- DMG gerado
- sintaxe dos scripts de instalacao/desinstalacao
- assinatura local `ad-hoc`

Observacao:
- a build atual e adequada para uso local
- ela ainda nao e notarizada para distribuicao publica

## Instalacao do usuario no macOS
Instalar:
```bash
./scripts/install_orquestra_macos.sh
```

O instalador:
- valida o ambiente
- gera o bundle do app quando necessario
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

## Enderecos e caminhos
- API: `http://127.0.0.1:8808`
- Web: `http://127.0.0.1:4177`
- App instalado: `~/Applications/Orquestra AI.app`
- Runtime: `~/Library/Application Support/Orquestra/runtime`
- Logs: `~/Library/Logs/Orquestra`
- Manifesto: `~/Library/Application Support/Orquestra/runtime/experiments/orquestra/install/install_manifest.json`
- Backups: `~/Library/Application Support/Orquestra/runtime/experiments/orquestra/install/backups`

## Providers reais
O fluxo de validacao oficial pode permanecer totalmente local/mock.

Quando quiser habilitar providers reais:
- configure `.env` local
- use `LM Studio` para o provider local
- mantenha chaves remotas fora do Git

Checklist rapido:
```bash
./scripts/check_orquestra_providers.sh
```

Exemplos de gate estrito:
```bash
./scripts/check_orquestra_providers.sh --strict --require lmstudio
./scripts/check_orquestra_providers.sh --strict --require openai
```

Entradas comuns:
- `OPENAI_API_KEY`
- `ANTHROPIC_API_KEY`
- `DEEPSEEK_API_KEY`
- `ORQUESTRA_LITELLM_PROXY_URL`
- `LMSTUDIO_API_BASE=http://localhost:1234/v1`

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

Depois:
```text
http://127.0.0.1:4177
```

### Provider local offline
```bash
curl -fsS http://localhost:1234/v1/models
```

### Build desktop falhou
Revise:
- `orquestra_web/src-tauri/target`
- `cargo check`
- `./scripts/validate_orquestra.sh`

## Estado atual desta fase
- o fluxo local esta fechado para backend, web e desktop
- o instalador e o desinstalador ja fazem parte do produto
- a validacao principal cobre memoria, compactacao, planner e workflow
- o runtime segue local-first e nao depende do repositorio antigo `Local_RAG`
- conectores remotos continuam como catalogo/intencao, com EC2 adiado para proxima fase
