# Instruções do Projeto (Orquestra)

## Objetivo
Operar o `Orquestra` como aplicação independente, macOS-first, para:
- chat multi-provider;
- memória estruturada de sessão e memória durável;
- leitura multimodal de diretórios;
- consulta RAG local;
- operações de treino e jobs remotos;
- comparação e registro de modelos por projeto.

## Regras inegociáveis
1. Nunca versionar segredos, chaves privadas ou credenciais reais.
2. Preferir automação por script a passos manuais repetitivos.
3. Toda mudança relevante de operação deve atualizar `README.md` ou a documentação em `docs/`.
4. Manter o comportamento `local-first` como padrão.
5. Evitar dependência implícita do repositório `Local_RAG`.

## Base operacional
- `README.md`
- `docs/11-orquestra-ai-control-plane.md`
- `docs/12-orquestra-v2-memorygraph-workspace.md`
- `scripts/start_orquestra_api.sh`
- `scripts/start_orquestra_web.sh`
- `scripts/start_orquestra_desktop.sh`

## Definition of Done
Uma tarefa fecha quando:
- o comportamento foi validado;
- a documentação afetada foi atualizada;
- os scripts principais seguem funcionando;
- o backend e o frontend/build desktop continuam íntegros.
