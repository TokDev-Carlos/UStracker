# Matriz de execução do handoff

| Fase | Schema | Worktree | Gate de saída |
|---|---:|---|---|
| T0 Infraestrutura | 3 | `main` | baseline + guardrails verificados |
| T1 Fundação visual | 3 → 3 | R01 | shell/formatadores + regressão |
| T2 Clientes | 3 → 4 | R02 | migração + ficha + restore |
| T3 Mobilidade | 4 → 5 | R03 | propriedade reconciliada |
| T4 Catálogo | 5 → 6 | R04 | itens/preços/custos reconciliados |
| T5 Comercial | 6 → 7 | R05 | assinaturas/compras/créditos reconciliados |
| T6 Financeiro | 7 → 7 | R06 | resultado financeiro idêntico |
| T7 Visão Geral | 7 → 7 | R07 | homologação visual e busca |
| T8 Anexos | 7 → 8 | R08 | backup/restore de anexos |
| T9 Compatibilidade | 8 → 8 | R09 | reconciliação completa + recovery |
| T10 Pacote | 8 → 8 | R10 | pacote Windows homologado, sem instalação automática |

Nenhuma fase usa `main` como área de feature. O merge/promoção é uma ação posterior ao aceite do ponto de parada.
