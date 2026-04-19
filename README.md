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
  - scripts de operação do backend, frontend e desktop

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
cd ~/Desenvolvimento/Orquestra
./scripts/bootstrap_orquestra.sh
```

Preferência de runtime:
- `python3.12` para evitar incompatibilidades do ecossistema Python mais novo durante bootstrap local.

## Validação rápida
```bash
cd ~/Desenvolvimento/Orquestra
./scripts/validate_orquestra.sh
```

## Rodar a API
```bash
cd ~/Desenvolvimento/Orquestra
source .venv/bin/activate
./scripts/start_orquestra_api.sh
```

API local:
- `http://127.0.0.1:8808`

## Rodar o frontend web
```bash
cd ~/Desenvolvimento/Orquestra
./scripts/start_orquestra_web.sh
```

Frontend local:
- `http://127.0.0.1:4177`

## Rodar o app desktop no macOS
```bash
cd ~/Desenvolvimento/Orquestra
./scripts/start_orquestra_desktop.sh
```

## Build do frontend
```bash
cd ~/Desenvolvimento/Orquestra
./scripts/build_orquestra_web.sh
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
