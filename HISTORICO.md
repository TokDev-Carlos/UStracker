# Histórico do UStracker (branch `Dev`)

O branch **`main`** guarda só a versão oficial (2.0.0 em diante, começa limpo).
Este branch **`Dev`** é o arquivo completo e a área de trabalho de desenvolvimento.

## Linhas do tempo arquivadas aqui
| Origem | Período | O que foi | Como entrou |
|---|---|---|---|
| `Dev` original | 12/09/2026 | Baseline PECSUS 1.2.1 | base deste branch |
| `main` antigo | 12–13/09/2026 → 04/10/2026 | Produto 1.00.00.000 / 1.00.01.000, primeiras placas | avanço direto (commits preservados; arquivo de placa em texto livre removido do histórico) |
| `fix/session-persistence-20260914` (PR #3) | 13–14/09/2026 | Sessão preservada ao recarregar | merge de arquivo (substituído pela 2.0.0) |
| `release/sanitize-1.00.01.000` (PR #4) | 17/09/2026 | Recuperação e saneamento da 1.00.01.000 | merge de arquivo (substituído pela 2.0.0) |
| `codex/r11-r23` (desenvolvimento local) | 14/09 → 04/10/2026 | 1.001 → 1.004 (R/AJ), 1.005 nuvem e Lixeira, 1.006 frota e instalador, 1.007 Servidores/usuários/placa, **2.0.0** | merge de arquivo; a árvore atual deste branch é a dele |

## Versões
- **2.0.0** (04/10/2026): Release 2, entrega oficial. Instalador único, entrada automática em computador novo, base zerada.
- **1.007**: usuários e pacotes, Servidores com vez de gravar, placa de direção assinada.
- **1.006**: frotas/veículos (exclusão, placa única), primeiro instalador.
- **1.005**: nuvem Google Drive e Lixeira de 14 dias.
- **1.004 e anteriores**: base do produto.

## Como trabalhar daqui em diante
1. Desenvolver e testar no `Dev` (RED→GREEN).
2. Validado: levar ao `main` só os arquivos do produto (ver estrutura do `main`), subir a versão (`2.0.1`, `2.1.0`…) e publicar o Release com `UStracker_install_x64.exe`.
