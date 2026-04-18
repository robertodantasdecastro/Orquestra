# Local Ops Workflows

O workspace Orquestra usa:

- `./scripts/status.sh` para snapshot do stack
- `./scripts/start_dashboards.sh` para dashboards
- `./scripts/stop_all.sh` para desligar tudo
- `./scripts/rag_pipeline.sh` para operar a camada RAG

Boas praticas:

- manter o stack desligado por padrao
- usar `Phoenix` e `Langfuse` apenas quando precisar observar ou avaliar
- exportar dados do RAG para `datasets/rag_exports/` antes de enviar para treino remoto
