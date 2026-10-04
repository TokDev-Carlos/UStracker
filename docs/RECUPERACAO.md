# Recuperação — UStracker 2.0.0

**Computador novo ou perdido: só instalar.**
1. Execute `UStracker_install_x64.exe` no computador novo.
2. Abra o UStracker e entre com seu usuário e senha de sempre. Os dados chegam sozinhos da nuvem e o computador vira o próximo **Servidor**.
3. Sem internet na primeira abertura? A tela espera a nuvem e tenta de novo sozinha (nada é criado às cegas).

**Voltar no tempo:** Sistema → Nuvem → Pontos de restauração (últimos 14 dias; o mais recente nunca expira).

**Uso interno do Administrador:** Sistema → Nuvem → Avançado → *Restaurar da nuvem* troca à força os dados **deste** computador pelos de uma nuvem (URL + código). Os dados atuais vão antes para `UserData\Backups`.

**Sem nuvem (backup manual):** Sistema → Backup gera `.usbk` cifrado em `UserData\Backups`.

Regras:
- Nunca copie o banco com o sistema aberto (use **Encerrar**).
- `UserData` nunca é substituído por atualizações nem pela desinstalação.
