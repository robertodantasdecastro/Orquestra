# Python Fixes

Padroes recomendados para scripts Python operacionais:

- usar `Path` em vez de concatenacao manual de caminhos
- tratar excecoes com mensagens objetivas
- preservar JSON com `ensure_ascii=False`
- preferir funcoes pequenas e testaveis
- usar `utf-8` ao ler e gravar arquivos texto

Para CLIs, use `argparse` e retorne codigos de saida previsiveis.
