# Orquestra

Plataforma macOS-first para orquestrar IA local e remota com chat multi-provider, memória evolutiva, RAG, análise multimodal de diretórios e operações de treino/modelos em um único workspace.

## O que a aplicação faz
- conversa com múltiplos providers em uma única interface:
  - `LM Studio`
  - `OpenAI`
  - `Anthropic`
  - `DeepSeek`
  - `Ollama`
- mantém memória estruturada de sessão e memória durável;
- anexa diretórios inteiros e analisa conteúdo multimodal:
  - código e texto
  - imagem
  - PDF
  - Office
  - áudio
  - vídeo
- consulta o engine RAG embutido;
- prepara e acompanha jobs remotos;
- compara modelos e registra artefatos por projeto.

## Estrutura
- `orquestra_ai/`
  - backend FastAPI, MemoryGraph, Workspace Multimodal, gateway, registry e jobs
- `orquestra_web/`
  - frontend React/Vite e shell desktop Tauri
- `rag/`
  - engine RAG local reutilizado pelo backend
- `training/local/`
  - utilitários compartilhados de ingestão e avaliação
- `scripts/`
  - scripts de operação do backend, frontend, desktop e ciclo de instalação macOS

## Estado atual
- backend, frontend web e shell desktop estão íntegros no fluxo local de desenvolvimento;
- `./scripts/validate_orquestra.sh` é hoje a principal verificação automatizada do projeto;
- o build desktop do Tauri já fecha localmente no macOS;
- web e desktop compartilham agora um dashboard operacional com:
  - serviços
  - processo
  - memória
  - execução
- chat, memória, RAG e `Workspace Multimodal` já funcionam em smoke local;
- providers reais continuam opcionais e o fluxo de validação usa modo mock/local-safe;
- `Train Ops`, conectores e registry já existem na API/UI com gestão operacional e ações locais, mas a execução remota real ainda está em fase posterior.

## Requisitos
- macOS
- `python3`
- `node` + `npm`
- `rustup` / `cargo`
- opcional:
  - `LM Studio`
  - `ffmpeg`
  - `ffprobe`
  - `whisper`

## Instalação rápida
```bash
cd /caminho/para/Orquestra
./scripts/bootstrap_orquestra.sh
```

Preferência de runtime:
- `python3.12` para evitar incompatibilidades do ecossistema Python mais novo durante bootstrap local.

## Validação rápida
```bash
cd /caminho/para/Orquestra
./scripts/validate_orquestra.sh
```

## Rodar a API
```bash
cd /caminho/para/Orquestra
source .venv/bin/activate
./scripts/start_orquestra_api.sh
```

API local:
- `http://127.0.0.1:8808`

## Rodar o frontend web
```bash
cd /caminho/para/Orquestra
./scripts/start_orquestra_web.sh
```

Frontend local:
- `http://127.0.0.1:4177`

## Rodar o app desktop no macOS
```bash
cd /caminho/para/Orquestra
./scripts/start_orquestra_desktop.sh
```

## Build do frontend
```bash
cd /caminho/para/Orquestra
./scripts/build_orquestra_web.sh
```

## Build do app desktop
```bash
cd /caminho/para/Orquestra/orquestra_web
npm run desktop:build
```

Artefatos gerados:
- `orquestra_web/src-tauri/target/release/bundle/macos/Orquestra AI.app`
- `orquestra_web/src-tauri/target/release/bundle/dmg/Orquestra AI_0.2.0_aarch64.dmg`

## Instalar no macOS
```bash
cd /caminho/para/Orquestra
./scripts/install_orquestra_macos.sh
```

O instalador:
- executa bootstrap local;
- gera o app desktop;
- instala o bundle em `~/Applications/Orquestra AI.app`;
- registra um `LaunchAgent` do usuário para manter a API local disponível.

## Desinstalar no macOS
```bash
cd /caminho/para/Orquestra
./scripts/uninstall_orquestra_macos.sh
```

Para remover também logs e dados de suporte do usuário:
```bash
cd /caminho/para/Orquestra
./scripts/uninstall_orquestra_macos.sh --purge-data
```

## Guias
- `docs/01-instalacao-validacao-macos.md`
- `docs/11-orquestra-ai-control-plane.md`
- `docs/12-orquestra-v2-memorygraph-workspace.md`

## Segurança
- não versionar `.env` real;
- armazenar credenciais fora do repositório;
- usar `.env.example` como referência;
- manter a aplicação operando local-first por padrão.
