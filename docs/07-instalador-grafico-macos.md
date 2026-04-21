# Instalador e Desinstalador Grafico macOS

![Orquestra](../assets/brand/orquestra-logo.png)

## Objetivo

Este guia descreve o wizard grafico do Orquestra para macOS. Ele nao substitui os scripts: ele usa os scripts oficiais como motor confiavel e renderiza planos/eventos JSON na interface.

A entrega V1 gera:

- `Orquestra AI.app`
- `Orquestra Installer.app`
- `Orquestra Uninstaller.app`
- `Orquestra AI Installer_0.2.0_aarch64.dmg`

O DMG simples `Orquestra AI_0.2.0_aarch64.dmg` continua sendo apenas o pacote do app. O wizard completo e o DMG `Orquestra AI Installer_*`.

A identidade visual padrao agora segue duas variantes:

```text
Logo1.png -> wordmark com texto
Logo2.png -> icon-only
assets/brand/orquestra-logo.png -> wordmark canonico
assets/brand/orquestra-icon.png -> icone canonico
```

Regra de uso:

- documentacao e cabecalhos amplos podem usar o wordmark com texto
- sidebar, chips, app icon, `.icns` e `.ico` usam apenas o icone sem texto

## Quando usar

Use o instalador grafico quando:

- o Mac pode nao ter dependencias instaladas
- voce quer revisar dependencias antes de instalar
- voce quer configurar runtime, storage, providers e opcionais em uma tela guiada
- voce quer instalar e validar sem decorar comandos

Use o desinstalador grafico quando:

- voce quer remover o app preservando dados
- voce quer remover memoria/RAG/OSINT com backup
- voce quer escolher item por item
- voce quer remover tudo com confirmacao forte

## Build

Gerar o DMG completo:

```bash
./scripts/build_orquestra_macos_graphical_installer.sh
```

Esse script executa:

- build do `Orquestra AI.app`
- build do `Orquestra Installer.app`
- build do `Orquestra Uninstaller.app`
- staging com payload local
- criacao do DMG completo

Observacao operacional importante:

- `Orquestra Installer.app` e `Orquestra Uninstaller.app` sao empacotados como `.app` dedicados.
- o DMG final `Orquestra AI Installer_*` e montado pelo script oficial do Orquestra.
- isso evita depender do `bundle_dmg.sh` do Tauri para os wizards dedicados e torna o empacotamento mais estavel.

Artefato final:

```text
orquestra_web/src-tauri/target/release/bundle/dmg/Orquestra AI Installer_0.2.0_aarch64.dmg
```

Abrir:

```bash
open "orquestra_web/src-tauri/target/release/bundle/dmg/Orquestra AI Installer_0.2.0_aarch64.dmg"
```

## Validacao

Validar scripts, configs, apps e DMG:

```bash
./scripts/validate_orquestra_macos_graphical_installer.sh
```

O validador confere:

- `tauri.installer.conf.json`
- `tauri.uninstaller.conf.json`
- scripts de build/validacao
- `Orquestra AI.app`
- `Orquestra Installer.app`
- `Orquestra Uninstaller.app`
- DMG completo
- contratos JSON de instalacao/desinstalacao
- assinatura local quando houver
- ausencia de notarizacao Developer ID como aviso aceitavel na V1 local

Distribuicao publica notarizada fica fora da V1. Variaveis planejadas para suporte futuro:

- `DEVELOPER_ID_APPLICATION`
- `DEVELOPER_ID_INSTALLER`
- `APPLE_ID`
- `APPLE_TEAM_ID`
- `APP_SPECIFIC_PASSWORD`

## Fluxo do Orquestra Installer.app

O instalador grafico mostra:

1. Boas-vindas e modo de instalacao.
2. Diagnostico do Mac.
3. Dependencias obrigatorias:
   - Command Line Tools
   - Homebrew
   - Python 3.12
   - Node/npm
   - Rust/Cargo
   - uv
   - git
4. Recursos opcionais:
   - LM Studio
   - Ollama
   - Tor
   - ffmpeg
   - Whisper
   - Brave
   - providers remotos
5. Runtime e storage:
   - runtime padrao por usuario
   - runtime compartilhado avancado
   - SSD externo
   - cloud mounted
   - S3/SFTP apenas para frio/backup/export
   - quotas
6. Providers e chaves:
   - OpenAI
   - Anthropic
   - DeepSeek
   - Brave
   - Tavily
   - Exa
   - YouTube
   - Shodan
   - Censys
   - Train Plane
7. Cofre de segredos:
   - Keychain por padrao
   - `.env` apenas como fallback/importacao
8. Instalacao do app:
   - copia `Orquestra AI.app`
   - sincroniza runtime
   - cria `runtime.json`
   - cria manifesto
   - registra LaunchAgent quando selecionado
   - valida API/web/app
9. Tela final:
   - abrir app
   - abrir Settings Center
   - mostrar caminhos reais
   - mostrar pendencias opcionais

Ao clicar em `Instalar agora`, o wizard abre um dialogo de execucao com:

- barra de progresso
- etapa atual
- lista de passos
- log detalhado do processo
- estado final de sucesso ou falha sem despejar o erro bruto na barra lateral

## Fluxo do Orquestra Uninstaller.app

O desinstalador grafico detecta:

- app instalado
- LaunchAgent
- runtime
- logs
- banco SQLite
- MemoryGraph/memdir
- RAG/Chroma/Qdrant
- evidencias OSINT
- workspace scans/extractions
- workflows
- Train Plane local
- backups
- `.venv`
- metadados de Keychain

Modos:

- `Seguro seletivo`: padrao, remove apenas itens escolhidos.
- `Preservar dependencias`: remove Orquestra sem tocar dependencias compartilhadas.
- `Remover tudo`: seleciona todos os itens removiveis e exige confirmacao forte.

Antes de apagar memoria, banco, OSINT, workspace ou RAG, o wizard oferece backup `.tar.gz`.

## Contratos JSON usados pela UI

O app grafico usa comandos Tauri que chamam estes contratos:

```bash
./scripts/install_orquestra_macos_full.sh --check-only --json
./scripts/uninstall_orquestra_macos_full.sh --dry-run --json
./scripts/check_orquestra_macos_installation.sh --check-only --json
```

Comandos Tauri expostos:

- `installer_preflight`
- `installer_build_plan`
- `installer_run_plan`
- `installer_cancel`
- `installer_open_external_url`
- `installer_store_secret`
- `uninstaller_scan`
- `uninstaller_build_plan`
- `uninstaller_run_plan`
- `uninstaller_create_backup`
- `uninstaller_cancel`

Tipos minimos:

- `InstallPlan`
- `InstallStepEvent`
- `InstallResult`
- `RuntimeConfig`
- `StorageLocation`
- `StorageAssignment`
- `SecretMetadata`
- `ProviderSetup`
- `UninstallPlan`
- `UninstallItem`
- `BackupArtifact`

## Segredos e logs

Regra fixa:

- nenhuma chave aparece em log
- nenhuma chave aparece em JSON retornado para a UI
- nenhuma chave entra no Git
- a UI mostra apenas estado, `secret_ref` e se o segredo esta configurado

No macOS, o storage padrao e:

```text
service: ai.orquestra.secrets
```

## Settings Center apos instalar

Depois da instalacao, abra `Settings` no Orquestra para revisar:

- caminhos reais do runtime
- storage locations
- assignments por dominio
- quotas
- providers ligados/desligados
- chaves configuradas sem revelar valores
- modelos detectados
- decisao simulada do router
- agentes configurados

## Limitacoes da V1

- O alvo principal e DMG com wizard Tauri; `.pkg` fica para etapa futura.
- Assinatura/notarizacao Developer ID ficam prontas para evolucao, mas nao sao requisito da V1 local.
- Storage S3/SFTP e frio: nao usar para SQLite ou indice RAG ativo.
- O wizard depende dos scripts oficiais; se um script falhar, o app grafico mostra o erro e a acao recomendada.

## Checklist manual recomendado

Antes de considerar o instalador pronto para distribuicao interna:

1. Gerar o DMG completo.
2. Rodar o validador grafico.
3. Abrir o DMG e iniciar `Orquestra Installer.app`.
4. Rodar instalacao obrigatoria em usuario descartavel.
5. Validar `Settings`.
6. Testar LM Studio local quando disponivel.
7. Testar Brave Search API quando houver chave.
8. Rodar `Orquestra Uninstaller.app` em modo seguro.
9. Testar remocao de memoria/RAG/OSINT com backup.
10. Confirmar que dependencias Homebrew nao sao removidas sem selecao explicita.
