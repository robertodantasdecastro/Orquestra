# Instalação e Validação no macOS

## Objetivo
Subir o `Orquestra` localmente no Mac com o menor atrito possível e validar que:
- backend responde;
- frontend builda;
- shell desktop passa em `cargo check`;
- shell desktop também pode ser empacotado com `tauri build`;
- web e desktop mostram o mesmo dashboard operacional de serviços, processo, memória e execução;
- chat, memória e `Workspace Multimodal` funcionam em smoke local.

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
  - criação de sessão;
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

### Build desktop
```bash
cd /caminho/para/Orquestra/orquestra_web
npm run desktop:build
```

Saídas atuais:
- `orquestra_web/src-tauri/target/release/bundle/macos/Orquestra AI.app`
- `orquestra_web/src-tauri/target/release/bundle/dmg/Orquestra AI_0.2.0_aarch64.dmg`

### Instalação de usuário no macOS
```bash
cd /caminho/para/Orquestra
./scripts/install_orquestra_macos.sh
```

Esse instalador:
- prepara o ambiente local;
- recompila o app desktop;
- instala o bundle em `~/Applications`;
- registra um `LaunchAgent` do usuário para a API local.

Opções úteis:
```bash
./scripts/install_orquestra_macos.sh --skip-build
./scripts/install_orquestra_macos.sh --no-launch-agent
./scripts/install_orquestra_macos.sh --install-dir "$HOME/Applications/Orquestra AI.app"
```

O LaunchAgent instalado usa o label `ai.orquestra.api` e grava logs em:
- `~/Library/Logs/Orquestra/api.stdout.log`
- `~/Library/Logs/Orquestra/api.stderr.log`

### Desinstalação
```bash
cd /caminho/para/Orquestra
./scripts/uninstall_orquestra_macos.sh
```

Opcionalmente:
- `./scripts/uninstall_orquestra_macos.sh --purge-data`
  remove também `~/Library/Application Support/Orquestra` e `~/Library/Logs/Orquestra`.

Por padrão, o desinstalador remove app e LaunchAgent, mas preserva dados e logs do usuário.

## Endereços locais
- API: `http://127.0.0.1:8808`
- Web: `http://127.0.0.1:4177`

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
- ações como bootstrap, validação, build web, build desktop, instalação e desinstalação podem ser disparadas pela superfície de execução;
- o fluxo remoto de treino e conectores continua propositalmente adiado nesta fase.
- a marca vetorial do Orquestra está em `assets/brand/` e já aparece na UI web/desktop.

## Observação importante
O scanner multimodal do `Orquestra` é `inventory-first`.
Isso significa:
- não duplica binários por padrão;
- extrai pesado sob demanda;
- cabe melhor no Mac atual.
