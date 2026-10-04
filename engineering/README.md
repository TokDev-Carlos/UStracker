# UStracker Engineering Workspace

Este diretório controla a evolução segura do UStracker a partir da baseline `1.00.01.000 / schema 3`.

## Estado inicial

- A baseline canônica está na tag Git `baseline/1.00.01.000-schema3`.
- O plano funcional está **bloqueado** por `engineering/APPROVAL.json`.
- Nenhuma ferramenta deste diretório instala ou substitui automaticamente `C:\UStracker`.
- `UserData`, bancos reais, credenciais e chaves privadas não pertencem ao workspace.
- O Supabase remoto não é alterado por estes arquivos; a migração em `engineering/supabase/` é somente um artefato preparado.

## Fluxo obrigatório

1. `Invoke-Preflight.ps1` valida baseline, toolchain, processos e integridade.
2. Após autorização explícita, `New-Increment.ps1` cria um Git worktree isolado para um changeset.
3. O implementador segue TDD e altera apenas caminhos permitidos no changeset.
4. `Invoke-Verification.ps1` executa política de diff, regressão, build e registra evidência.
5. `New-Checkpoint.ps1` captura HEAD, base e arquivos alterados.
6. Somente um changeset `VERIFIED` pode passar por `Build-Candidate.ps1`.
7. `Build-Candidate.ps1` gera pacote em área de candidate, mas não instala.
8. Promoção/instalação exige autorização separada e segue o updater existente.

## Regra de não retrocesso

Falhou qualquer gate: a fase para. A correção ocorre no worktree atual ou ele é descartado e recriado a partir de `base_commit`. A baseline e a instalação ativa não são usadas como área de edição.
