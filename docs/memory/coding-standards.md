# Padrões de código — UStracker

- **Lint:** Ruff (`ruff check <arquivo>`) só nos arquivos alterados; regras mínimas (`E9`, `F`). Sem formatação em massa.
- **Tipos:** anotar funções novas/públicas; Mypy só nos módulos listados em `pyproject.toml`.
- **Nomes:** `snake_case`, `PascalCase`, `MAIUSCULAS`; termos do domínio em português (ver `glossary.md`).
- **Funções:** pequenas, uma responsabilidade.
- **Erros:** nunca engolir exceção em silêncio; mensagem útil sem dados sensíveis.
- **Dados:** multi-tabela numa transação; backup antes de apagar; lixeira antes de excluir.
- **Segredos:** nunca no código ou no Git (tokens, PIN, chaves); ficam no Drive › Empresas\UStracker\Tokens.
- **Testes:** `tests/test_<id>_<assunto>.py` e `tests/<id>_<assunto>.test.mjs`; RED→GREEN; um teste por bug corrigido.
- **PowerShell:** ASCII, sem funções de 1 letra; caminhos com `-LiteralPath`.
