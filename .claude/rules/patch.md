---
paths:
  - "tools/make_patch.py"
  - "tools/patch/**/*"
---
# Pacotes .uspatch e Aplicador
- `make_patch.py` assina com `update_signing_key.pem` (Drive › Empresas\UStracker\Tokens\UStracker); apagar a cópia local da chave depois do uso.
- Aplicador: 1 = esta máquina (backup SHA-256 antes); 2 = lança para os outros (token lido do Drive, nunca salvo).
- Saída JSON do `patch_tool.py` só ASCII; nunca lançar versão igual ou mais antiga que a da nuvem.
