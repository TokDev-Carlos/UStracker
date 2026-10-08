---
paths:
  - "src/**/*.py"
  - "tools/**/*.py"
---
# Python (backend FastAPI)
- Toda operação que altera mais de uma tabela: uma transação (`with db.transaction() as con:`), rollback garantido.
- Bancos com SQLCipher; nos testes use `USTRACKER_DEV_PLAINTEXT=1`. Nunca gravar chave/PIN/token em log.
- Erros para a tela em inglês curto no backend; tradução em `frontend/ui/pt-br-errors.js`.
- Testes: `PYTHONPATH=src;. python -m unittest discover -s tests -p "test_*.py"`; teste novo RED antes da correção.
- `ruff check <arquivo>` nos arquivos alterados (sem formatar o projeto inteiro).
