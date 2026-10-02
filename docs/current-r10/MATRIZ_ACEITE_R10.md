# Matriz de aceite — R10

| Critério | Evidência automatizada | Estado |
|---|---|---|
| R01 shell/formatos preservados | testes R01 + Node global | PASS automatizado |
| Clientes schema 4 | suíte backend/frontend acumulada | PASS automatizado + homologado pelo usuário no Ponto 2 |
| Frotas/Veículos schema 5 | suíte acumulada | PASS automatizado; homologação manual incorporada ao pacote cumulativo |
| Planos/Produtos schema 6 | testes de código, custo, histórico e concorrência | PASS automatizado |
| Comercial schema 7 | cobertura, compra Avulsa, créditos | PASS automatizado |
| Financeiro sem dupla contabilização | testes fiscal/despesa/recorrência | PASS automatizado |
| Visão Geral | busca sem acento, receita realizada, contagens | PASS automatizado |
| Anexos schema 8 | MIME/assinatura, cifra, hash, backup/restore | PASS automatizado |
| Migração/reconciliação | reabertura idempotente, invariantes e aliases | PASS automatizado |
| Windows 10 x64 físico | atalho, WebView2, login, shutdown, updater/rollback | PENDENTE homologação física |
| Build nativo .NET x64 | Bootstrap/Shell/Updater | PENDENTE: SDK .NET indisponível neste ambiente |
| Assinatura do instalador | pipeline Windows | PENDENTE ambiente/pipeline de assinatura |
| sqlcipher3 real em teste automatizado local | teste legado de fixture SQLCipher | PENDENTE: módulo ausente neste ambiente; suíte registra 1 SKIP |

Release de produção só deve ser marcado após os itens Windows físicos e build/assinatura ficarem concluídos.
