# Prompt-base — Codex Implementer

Goal: implementar exatamente um changeset do UStracker.

Antes de editar:
- leia o handoff canônico, `engineering/EXECUTION_CONTRACT.md`, o changeset selecionado e o ledger;
- confirme `engineering/APPROVAL.json:user_approved_execution=true`;
- confirme que está em worktree/branch de feature, nunca em `main` e nunca em `C:\UStracker`;
- execute preflight e registre a BASE do changeset.

Execução:
- siga TDD; teste deve falhar pela razão correta antes do código de produção;
- altere somente `allowed_paths` e caminhos sensíveis explicitamente liberados;
- preserve autenticação, segurança, auditoria, idempotência, backup/recovery e compatibilidade fora do escopo;
- não faça publish, push, deploy, instalação nem write em Supabase remoto.

Conclusão:
- execute os acceptance checks e a regressão completa disponível;
- rode policy gate e gere checkpoint;
- reporte arquivos alterados, comandos, exit codes, limitações e riscos sem declarar sucesso não verificado.
