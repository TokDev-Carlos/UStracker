# UStracker — instruções para o Claude (local e nuvem)

Sistema Windows de clientes, frotas, finanças e nuvem (dono: Carlos / CRJ). Responder em português do Brasil.

## Regras do projeto (obrigatórias)
1. Ser conciso — direto ao ponto.
2. Dados limpos — backup antes de qualquer alteração; lixeira antes de apagar.
3. Fontes testadas — só código com testes RED→GREEN passando.
4. Uma coisa por vez — sequência lógica, sem dependência cruzada.
5. Memória focada — só pontos críticos: checklists, decisões, bloqueadores, URIs.
6. Progresso sequencial — cada etapa conclui antes da próxima, marco visível.
7. Sem perfeccionismo — suficiente para validar, melhorar depois.
8. Testes pesados só após validação do usuário.
9. Nunca apagar sem confirmação — lista exata e hash do backup conferido.
10. Transações ACID — operação multi-tabela numa transação única.
11. Zero residual — nada de temporário, log ou candidato após promoção.
12. Usuário primeiro — perguntar decisões e aguardar resposta antes de executar.

Segurança: nunca mostrar, logar ou commitar tokens, PIN, senha ou chave da empresa.

## Antes de começar
- `docs/memory/project-context.md` (stack, dados, integrações) · `business-rules.md` · `coding-standards.md` · `glossary.md`.
- Decisões, problemas, ideias e validações: `D:\PROGRAMAS\UStracker_Project\Conhecimento\` (consultar `Problemas_Solucoes` antes de investigar erro).
- Regras por área: `.claude/rules/` (carregam só ao mexer nos arquivos daquela área).

## Fluxo (misto)
- Nuvem (Claude no claude.ai/Cowork): código, testes, build, pacotes → GitHub branch `Dev`.
- Local (Claude Code neste PC): aplicar e testar no Windows real seguindo o `VALIDAR.md` da entrega.

## Mapa
| Onde | O quê |
|---|---|
| `src/ustracker/` | backend Python (FastAPI) |
| `frontend/` | telas |
| `host/` | host .NET (WebView2, Updater) |
| `cloud/Code.gs` | Apps Script da nuvem (Drive) |
| `release/` | instalador NSIS, LEIA-ME, documentos do usuário |
| `tools/` | build do instalador, patch (`make_patch.py`, `patch/`), scripts locais (`dev/`) |
| `tests/` | `test_*.py` e `*.test.mjs` |

PC: programa `C:\Program Files\UStracker\` · dados `C:\ProgramData\UStracker\UserData\` · projeto `D:\PROGRAMAS\UStracker_Project\` (`Codigo`, `Entregas\<versão>`, `Ferramentas`, `Conhecimento`, `Logs`) · backups `Documents\UStracker_Backups\`.
Drive: `Empresas\UStracker\Desenvolvimento\` (cópia de Conhecimento/Ferramentas/Entregas) · `Empresas\UStracker\Tokens\GitHub` e `\UStracker` · registro de pastas `Bancos\registro_pastas.json`. A nuvem do sistema acha a pasta `UStracker Cloud` pelo ID (`Code.gs`, `FOLDER_ID`).
GitHub `TokDev-Carlos`: `UStracker` (main = lançada, `Dev` = desenvolvimento, `updates/` = canal) · `acesso-UStracker` (privado).

## Lançar versão
Só com o check **Testes** (GitHub Actions) verde no commit da `Dev`. Testes pesados: `tools/dev/testes_pesados.py <pasta> 500 1500`.

## Testes rápidos
`Ferramentas\Testes_Rapidos.ps1` ou `$env:PYTHONPATH="src;."; $env:USTRACKER_DEV_PLAINTEXT="1"; .venv\Scripts\python -m unittest discover -s tests -p "test_*.py"` e `node --test tests/*.test.mjs`.

## Estado atual (2026-10-09)
- Lançada: 2.7.0 — frota = 1 assinatura por veículo, pagar frota toda, avisos de backup corrigidos.
- Lançada: 2.6.0 (main, tag, Release) — confiança: nuvem automática e vez de gravar corrigida, backup diário conferido, Diagnóstico, LGPD (prazos 14 dias/5 anos, exportar dados), CI no GitHub.
- 2.5.0 e 2.6.0 ainda não validadas no PC do Carlos (`Entregas\2.5.0\VALIDAR.md` e `Entregas\2.6.0\VALIDAR.md`). Canal `updates/` anuncia 2.4.1 (lançar pelo Aplicador opção 2).
- Próximo: 2.8 Cobrança (recibo, lembretes, PIX; plano no projeto claude.ai: `PANORAMA_2.5_E_PLANO_PROFISSIONAL.md`).
- Frota (decisão 2026-10-09): cada veículo é uma assinatura; a frota só agrupa e pode ser paga de uma vez; veículo novo na frota não ganha assinatura sozinho.
