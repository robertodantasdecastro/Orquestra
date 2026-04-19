# Instalação e Validação no macOS

## Objetivo
Subir o `Orquestra` localmente no Mac com o menor atrito possível e validar que:
- backend responde;
- frontend builda;
- shell desktop passa em `cargo check`;
- chat, memória e `Workspace Multimodal` funcionam em smoke local.

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
cd ~/Desenvolvimento/Orquestra
./scripts/bootstrap_orquestra.sh
```

O bootstrap:
- cria `.venv` se necessário;
- instala dependências Python;
- instala dependências do frontend;
- cria `.env` a partir de `.env.example` se ele ainda não existir.

## Validação automatizada
```bash
cd ~/Desenvolvimento/Orquestra
./scripts/validate_orquestra.sh
```

Essa validação executa:
- `py_compile` do backend e engine `RAG`;
- `bash -n` nos scripts;
- `npm run build` no frontend;
- `cargo check` no shell `Tauri`;
- smoke local da API com:
  - criação de sessão;
  - resumo e resume;
  - transcript;
  - scan de diretório;
  - preview e promoção para memória.

## Rodar manualmente
### API
```bash
cd ~/Desenvolvimento/Orquestra
./scripts/start_orquestra_api.sh
```

### Frontend web
```bash
cd ~/Desenvolvimento/Orquestra
./scripts/start_orquestra_web.sh
```

### Desktop macOS
```bash
cd ~/Desenvolvimento/Orquestra
./scripts/start_orquestra_desktop.sh
```

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

## Observação importante
O scanner multimodal do `Orquestra` é `inventory-first`.
Isso significa:
- não duplica binários por padrão;
- extrai pesado sob demanda;
- cabe melhor no Mac atual.
