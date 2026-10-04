# Recuperação — UStracker 1.006

**Caminho principal: a Nuvem.**
1. Instale com `install_UStracker.exe` no computador novo.
2. Na tela inicial: **Já uso o UStracker: restaurar da nuvem** → URL + Código de conexão.
3. Entre com seu usuário e senha de sempre. Este computador passa a ser o que grava.
4. Se o computador antigo voltar, ele não consegue sobrescrever a nuvem (conflito); desligue-o ou escolha qual vale em Sistema → Nuvem.

**Voltar no tempo:** Sistema → Nuvem → Pontos de restauração (últimos 14 dias; o mais recente nunca expira).

**Sem nuvem (backup manual):** Sistema → Cópia de segurança gera `.usbk` cifrado em `UserData\Backups`. Para restaurar, use "Restaurar cópia de segurança" no mesmo sistema.

Regras de segurança:
- Nunca copie o banco com o sistema aberto.
- Só um computador grava por vez (estação escritora). "Assumir gravação" é só para quando o antigo foi perdido.
- `UserData` e `Trust` nunca são substituídos por atualizações.
