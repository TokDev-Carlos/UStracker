# Contrato de execução

1. A especificação canônica é `docs/handoff/2026-09-28-ustracker-reestruturacao-incremental.md`.
2. `VERSION.json`, `HANDOFF_METADATA.json` e `src/ustracker/db.py` confirmam schema baseline 3. Trechos legados de `CODEX_EXECUCAO.md` que dizem schema 2 não autorizam regressão.
3. Tarefas funcionais 1-10 permanecem bloqueadas enquanto `engineering/APPROVAL.json:user_approved_execution` for `false`.
4. Cada tarefa usa seu changeset, um worktree e um `base_commit` imutável.
5. Código de produção novo ou correções seguem RED → GREEN → REFACTOR.
6. Caminhos sensíveis exigem inclusão explícita em `explicitly_allowed_sensitive_paths`.
7. Não editar `Runtime`, `UserData`, `Dist` nem a instalação ativa.
8. Não publicar, pushar, implantar ou promover release por inferência de autorização.
9. Cada ponto de parada deve conter comandos executados, exit codes e limitações ambientais.
10. Um relatório de worker/agente não é prova: o estado integrado precisa de verificação fresca.
