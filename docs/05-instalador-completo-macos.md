# Instalador Completo para macOS

## Objetivo

Este guia descreve a instalacao completa do Orquestra em um Mac que pode nao ter nenhuma dependencia instalada.

O fluxo novo e hibrido seguro:

- instala dependencias CLI obrigatorias quando o usuario autoriza
- guia dependencias opcionais
- explica onde criar logins e API keys
- configura `.env` local sem versionar segredos
- valida app, runtime, providers, OSINT e multimodal
- oferece desinstalacao seletiva com backup de memorias e dados

## Scripts principais

- `scripts/install_orquestra_macos_full.sh`
- `scripts/check_orquestra_macos_installation.sh`
- `scripts/uninstall_orquestra_macos_full.sh`

O instalador antigo `scripts/install_orquestra_macos.sh` continua existindo como instalador base do app e runtime. O instalador completo chama esse script depois de preparar o Mac.

## O que e obrigatorio

Obrigatorio para instalar, buildar e rodar o Orquestra localmente:

- macOS
- Command Line Tools da Apple
- Homebrew
- `python@3.12`
- `node` e `npm`
- `rust`/`cargo`
- `uv`
- `git`
- dependencias Python do `requirements-orquestra.txt`
- dependencias frontend do `orquestra_web/package-lock.json`

## O que e opcional

Opcionais por recurso:

- `LM Studio`: modelo local e baseline local
- `OpenAI`: provider remoto por `OPENAI_API_KEY`
- `Anthropic`: provider remoto por `ANTHROPIC_API_KEY`
- `DeepSeek`: provider remoto por `DEEPSEEK_API_KEY`
- `Brave Search API`: busca web OSINT por `BRAVE_SEARCH_API_KEY`
- `Tavily`: busca/extracao OSINT por `TAVILY_API_KEY`
- `Exa`: busca semantica OSINT por `EXA_API_KEY`
- `YouTube Data API`: conector de video por `YOUTUBE_API_KEY`
- `Shodan`: threat intel por `SHODAN_API_KEY`
- `Censys`: attack surface por `CENSYS_API_ID` e `CENSYS_API_SECRET`
- `Tor`: proxy local para fetch `.onion`
- `ffmpeg`: extracao de audio/video e frames
- `whisper`: transcricao local de audio/video
- `Ollama`: provider local alternativo

## Instalacao do zero

Primeiro rode somente diagnostico:

```bash
./scripts/install_orquestra_macos_full.sh --check-only
```

Instalacao obrigatoria, guiada:

```bash
./scripts/install_orquestra_macos_full.sh
```

Instalacao obrigatoria sem perguntas simples:

```bash
./scripts/install_orquestra_macos_full.sh --yes --required-only
```

Instalacao com opcionais comuns para OSINT e multimodal:

```bash
./scripts/install_orquestra_macos_full.sh --yes --with-optional ffmpeg,tor,brave
```

Instalacao com LM Studio e Tor:

```bash
./scripts/install_orquestra_macos_full.sh --yes --with-optional lmstudio,tor
```

Instalacao com preenchimento guiado do `.env`:

```bash
./scripts/install_orquestra_macos_full.sh --configure-env
```

## Flags do instalador completo

- `--check-only`: apenas verifica e orienta, sem instalar
- `--yes`: assume sim para instalacoes CLI obrigatorias
- `--required-only`: ignora opcionais
- `--with-optional brave,lmstudio,tor,ffmpeg,whisper,ollama`: instala opcionais selecionados
- `--configure-env`: guia preenchimento do `.env`
- `--skip-build`: usa bundle existente
- `--no-launch-agent`: nao registra LaunchAgent da API
- `--no-runtime-sync`: nao sincroniza runtime instalado
- `--open`: abre o app ao final
- `--skip-validation`: nao roda `validate_orquestra.sh` ao final

## Configuracao de logins e chaves

O instalador nao cria contas externas automaticamente. Ele orienta e valida.

### LM Studio

1. Instale o app pelo site do LM Studio ou via opcional `lmstudio`.
2. Baixe um modelo local.
3. Ative o Local Server.
4. Confirme o endpoint:

```bash
curl -fsS http://localhost:1234/v1/models
```

Variavel:

```bash
LMSTUDIO_API_BASE=http://localhost:1234/v1
```

### OpenAI

1. Crie login em `https://platform.openai.com/`.
2. Gere uma chave em `https://platform.openai.com/api-keys`.
3. Preencha no `.env`:

```bash
OPENAI_API_KEY=
ORQUESTRA_OPENAI_MODEL=gpt-4.1-mini
```

### Anthropic

1. Crie login em `https://console.anthropic.com/`.
2. Gere uma chave em `https://console.anthropic.com/settings/keys`.
3. Preencha:

```bash
ANTHROPIC_API_KEY=
ORQUESTRA_ANTHROPIC_MODEL=claude-3-7-sonnet-latest
```

### DeepSeek

1. Crie login em `https://platform.deepseek.com/`.
2. Gere uma chave em `https://platform.deepseek.com/api_keys`.
3. Preencha:

```bash
DEEPSEEK_API_KEY=
ORQUESTRA_DEEPSEEK_MODEL=deepseek-chat
```

### Brave Search API

1. Crie acesso em `https://api.search.brave.com/`.
2. Gere a chave de busca.
3. Preencha:

```bash
BRAVE_SEARCH_API_KEY=
```

### Tavily

1. Crie login em `https://app.tavily.com/`.
2. Gere a chave.
3. Preencha:

```bash
TAVILY_API_KEY=
```

### Exa

1. Crie login em `https://dashboard.exa.ai/`.
2. Gere a chave em API keys.
3. Preencha:

```bash
EXA_API_KEY=
```

### YouTube Data API

1. Crie ou selecione um projeto no Google Cloud Console.
2. Habilite `YouTube Data API v3`.
3. Crie uma API key.
4. Preencha:

```bash
YOUTUBE_API_KEY=
```

### Shodan

1. Crie login em `https://account.shodan.io/`.
2. Copie a API key do perfil.
3. Preencha:

```bash
SHODAN_API_KEY=
```

### Censys

1. Crie login em `https://search.censys.io/`.
2. Acesse a area de API.
3. Copie `API ID` e `API Secret`.
4. Preencha:

```bash
CENSYS_API_ID=
CENSYS_API_SECRET=
```

## Tor proxy local

Instalar:

```bash
brew install tor
brew services start tor
```

Configurar:

```bash
ORQUESTRA_OSINT_TOR_PROXY_URL=socks5h://127.0.0.1:9050
```

Verificar:

```bash
./scripts/check_orquestra_macos_installation.sh --check-only
```

Observacao:

- o Orquestra nao roteia a aplicacao inteira por Tor
- apenas fetch/crawl OSINT usa o proxy quando `via_tor=true`

## ffmpeg e whisper

Instalar `ffmpeg`:

```bash
brew install ffmpeg
```

Instalar `whisper`:

```bash
brew install pipx
pipx install openai-whisper
pipx ensurepath
```

Configurar modelo:

```bash
ORQUESTRA_WHISPER_MODEL=turbo
```

## Verificador de instalacao

Relatorio completo:

```bash
./scripts/check_orquestra_macos_installation.sh --check-only
```

Modo estrito para dependencias obrigatorias:

```bash
./scripts/check_orquestra_macos_installation.sh --strict
```

Categorias verificadas:

- sistema
- build
- app
- runtime
- providers
- osint
- multimodal
- validacao

## Validacao apos instalacao

Validacao local completa:

```bash
./scripts/validate_orquestra.sh
```

Provider real opcional:

```bash
./scripts/validate_orquestra.sh --real-provider lmstudio
./scripts/validate_orquestra_real_provider_smoke.sh --provider openai
```

Checklist de providers:

```bash
./scripts/check_orquestra_providers.sh
```

## Desinstalacao seletiva

Diagnosticar sem remover:

```bash
./scripts/uninstall_orquestra_macos_full.sh --dry-run
```

Modo seguro seletivo:

```bash
./scripts/uninstall_orquestra_macos_full.sh --mode safe
```

Preservar dependencias globais:

```bash
./scripts/uninstall_orquestra_macos_full.sh --mode preserve-deps
```

Remover tudo, com confirmacao forte:

```bash
./scripts/uninstall_orquestra_macos_full.sh --mode all
```

Remover itens especificos:

```bash
./scripts/uninstall_orquestra_macos_full.sh --select app,launch_agent,logs
./scripts/uninstall_orquestra_macos_full.sh --select memory,osint,workspace --backup-data
```

## Itens removiveis

Dados do Orquestra:

- `app`
- `launch_agent`
- `runtime_all`
- `logs`
- `db`
- `memory`
- `rag_indexes`
- `osint`
- `workspace`
- `workflows`
- `operations`
- `trainplane`
- `install_backups`
- `runtime_venv`

Dependencias globais, apenas com selecao explicita:

- `brew_python`
- `brew_node`
- `brew_rust`
- `brew_uv`
- `brew_ffmpeg`
- `brew_tor`
- `brew_ollama`
- `cask_brave`
- `cask_lmstudio`

## Arquivos sensiveis

Podem conter memoria, evidencias, datasets ou chaves locais:

- `.env`
- `~/Library/Application Support/Orquestra/runtime`
- `~/Library/Application Support/Orquestra/runtime/experiments/orquestra/orquestra_v2.db`
- `~/Library/Application Support/Orquestra/runtime/experiments/orquestra/memorygraph`
- `~/Library/Application Support/Orquestra/runtime/experiments/orquestra/osint`
- `~/Library/Application Support/Orquestra/runtime/experiments/orquestra/workspace`
- `~/Library/Application Support/Orquestra/runtime/experiments/orquestra/rag_runtime`

Antes de remover esses itens, use:

```bash
./scripts/uninstall_orquestra_macos_full.sh --select memory,osint,workspace,db --backup-data
```
