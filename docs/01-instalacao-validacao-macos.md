# Instalação e Validação no macOS

## Objetivo
Subir o `Orquestra` localmente no Mac com o menor atrito possível e validar que:
- backend responde;
- frontend builda;
- shell desktop passa em `cargo check`;
- shell desktop também pode ser empacotado com `tauri build`;
- pacote macOS `.app`/DMG passa na validação local;
- web e desktop mostram o mesmo dashboard operacional de serviços, processo, memória e execução;
- chat, memória associada ao RAG e `Workspace Multimodal` funcionam em smoke local.

Para o manual completo de operação diária, consulte `docs/02-manual-operacional.md`.

## Pré-requisitos
- macOS
- `python3.12` preferencialmente
- `node` + `npm`
- `rustup` + `cargo`
- opcional:
  - `LM Studio`
  - `ffmpeg`
  - `ffprobe`

## Bootstrap rápido
```bash
cd /caminho/para/Orquestra
./scripts/bootstrap_orquestra.sh
```

O bootstrap:
- cria `.venv` se necessário;
- instala dependências Python;
- instala dependências do frontend;
- cria `.env` a partir de `.env.example` se ele ainda não existir.

## Validação automatizada
```bash
cd /caminho/para/Orquestra
./scripts/validate_orquestra.sh
```

Essa validação executa:
- `py_compile` do backend e engine `RAG`;
- `bash -n` nos scripts;
- `tsc -b` + `vite build` no frontend;
- `cargo check` no shell `Tauri`;
- smoke local da API com:
  - criação de sessão com objetivo/preset;
  - perfil de sessão;
  - candidato revisável de memória;
  - aprovação de candidato com `MemoryRecord`;
  - consulta RAG com memória associada;
  - resumo e resume;
  - transcript;
  - scan de diretório;
  - preview e promoção para memória.

Observação:
- o smoke usa `mock_response` para validar o fluxo sem depender de provider remoto real;
- isso cobre integridade operacional do app, não homologação completa de OpenAI/Anthropic/DeepSeek/Ollama.

## Rodar manualmente
### API
```bash
cd /caminho/para/Orquestra
./scripts/start_orquestra_api.sh
```

### Frontend web
```bash
cd /caminho/para/Orquestra
./scripts/start_orquestra_web.sh
```

### Desktop macOS
```bash
cd /caminho/para/Orquestra
./scripts/start_orquestra_desktop.sh
```

### Desktop macOS com build e verificação
```bash
cd /caminho/para/Orquestra
./script/build_and_run.sh --verify
```

Modos disponíveis:
```bash
./script/build_and_run.sh
./script/build_and_run.sh --skip-build
./script/build_and_run.sh --verify
./script/build_and_run.sh --logs
./script/build_and_run.sh --telemetry
./script/build_and_run.sh --debug
```

### Build desktop
```bash
cd /caminho/para/Orquestra/orquestra_web
npm run desktop:build
```

Saídas atuais:
- `orquestra_web/src-tauri/target/release/bundle/macos/Orquestra AI.app`
- `orquestra_web/src-tauri/target/release/bundle/dmg/Orquestra AI_0.2.0_aarch64.dmg`

### Validar pacote macOS
```bash
cd /caminho/para/Orquestra
./scripts/validate_orquestra_macos_package.sh
```

Essa validação verifica:
- existência do `.app`;
- `Contents/Info.plist`;
- executável `orquestra-desktop`;
- DMG gerado;
- sintaxe do instalador/desinstalador;
- assinatura local. A build atual é `ad-hoc`, suficiente para uso local, mas ainda não notarizada para distribuição pública.

### Instalação de usuário no macOS
```bash
cd /caminho/para/Orquestra
./scripts/install_orquestra_macos.sh
```

Esse instalador:
- prepara o ambiente local;
- recompila o app desktop;
- instala o bundle em `~/Applications`;
- sincroniza o runtime local em `~/Library/Application Support/Orquestra/runtime`;
- cria backup do banco local antes do upgrade quando `orquestra_v2.db` ja existir;
- grava manifesto de instalacao em `experiments/orquestra/install/install_manifest.json`;
- registra um `LaunchAgent` do usuário para a API local.

Opções úteis:
```bash
./scripts/install_orquestra_macos.sh --skip-build
./scripts/install_orquestra_macos.sh --no-launch-agent
./scripts/install_orquestra_macos.sh --no-runtime-sync
./scripts/install_orquestra_macos.sh --open
./scripts/install_orquestra_macos.sh --no-wait-api
./scripts/install_orquestra_macos.sh --skip-package-verify
./scripts/install_orquestra_macos.sh --install-dir "$HOME/Applications/Orquestra AI.app"
```

O `LaunchAgent` roda a API a partir do runtime espelhado, não do diretório original do repositório. Isso evita falhas quando o projeto está em iCloud Drive ou outro caminho com permissões especiais. Para aumentar a espera inicial da API, use:
```bash
ORQUESTRA_INSTALL_API_WAIT_SECONDS=120 ./scripts/install_orquestra_macos.sh --skip-build
```

Para alterar a retenção de backups do banco:
```bash
ORQUESTRA_INSTALL_BACKUP_LIMIT=8 ./scripts/install_orquestra_macos.sh --skip-build
```

O LaunchAgent instalado usa o label `ai.orquestra.api` e grava logs em:
- `~/Library/Logs/Orquestra/api.stdout.log`
- `~/Library/Logs/Orquestra/api.stderr.log`

Arquivos de estado do upgrade:
- manifesto: `~/Library/Application Support/Orquestra/runtime/experiments/orquestra/install/install_manifest.json`
- backups: `~/Library/Application Support/Orquestra/runtime/experiments/orquestra/install/backups`

### Desinstalação
```bash
cd /caminho/para/Orquestra
./scripts/uninstall_orquestra_macos.sh
```

Opcionalmente:
- `./scripts/uninstall_orquestra_macos.sh --purge-data`
  remove também `~/Library/Application Support/Orquestra` e `~/Library/Logs/Orquestra`.
- `./scripts/uninstall_orquestra_macos.sh --no-launch-agent`
  remove apenas o app informado e preserva o LaunchAgent, útil para testes de instalação em diretório temporário.

Por padrão, o desinstalador remove app e LaunchAgent, mas preserva dados e logs do usuário.

## Endereços locais
- API: `http://127.0.0.1:8808`
- Web: `http://127.0.0.1:4177`
- Runtime instalado: `~/Library/Application Support/Orquestra/runtime`
- Manifesto do runtime: `~/Library/Application Support/Orquestra/runtime/experiments/orquestra/install/install_manifest.json`

## Providers reais
No primeiro ciclo, você pode deixar tudo local/mock.

Se quiser providers reais depois, ajuste `.env` com:
- `ORQUESTRA_LITELLM_PROXY_URL`
- `OPENAI_API_KEY`
- `ANTHROPIC_API_KEY`
- `DEEPSEEK_API_KEY`

Para provider local:
- abra o `LM Studio`;
- carregue o modelo;
- mantenha `LMSTUDIO_API_BASE=http://localhost:1234/v1`.

## Status operacional desta fase
- bootstrap local já aceita `uv` quando disponível e cai para `pip` como fallback;
- os scripts principais não dependem mais de um path fixo em `~/Desenvolvimento/Orquestra`;
- `PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python` fica fixado nos fluxos principais para reduzir atrito local;
- a aplicação agora expõe um dashboard operacional unificado em web e desktop para gestão de runtime;
- a versão desktop macOS gera app e DMG locais em `orquestra_web/src-tauri/target/release/bundle/`;
- o instalador real foi validado com runtime em `~/Library/Application Support/Orquestra/runtime`, LaunchAgent `ai.orquestra.api`, API em `/api/health` e app aberto em `~/Applications/Orquestra AI.app`;
- o upgrade real foi validado com backup do banco, manifesto de instalação e `/api/health` expondo `app_version`, `schema_version=2`, `schema_target_version=2`, `migration_required=false`, modo do runtime e backups recentes;
- o app desktop usa a mesma UI web com Assistant Workspace, Memory Inbox, RAG associado, Workspace Browser, dashboards e Execution Center;
- ações como bootstrap, validação, build web, build desktop, instalação e desinstalação podem ser disparadas pela superfície de execução;
- o fluxo remoto de treino e conectores continua propositalmente adiado nesta fase.
- a marca vetorial do Orquestra está em `assets/brand/` e já aparece na UI web/desktop.

## Observação importante
O scanner multimodal do `Orquestra` é `inventory-first`.
Isso significa:
- não duplica binários por padrão;
- extrai pesado sob demanda;
- cabe melhor no Mac atual.
