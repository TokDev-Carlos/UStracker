# Validação humana — AJ-08 a AJ-16 (candidato FINAL2)

Ambiente: **Teste** (nunca validar em Produção). Login de teste habitual.
Schema do banco: **12** (migração aditiva: `expenses.repeat`, `repeat_active`, `converted_sale_id`).

Decisões aplicadas sem resposta explícita (podem ser trocadas depois):
- Mover veículo vale **a partir de hoje** (data editável para o passado; futuro é recusado).
- Identidade visual: **azul da marca + navy + ciano "sinal"** (tirados do logo).
- Pagamento adiantado aceita **desconto opcional**.

## Roteiro rápido (≈15 min)

| # | Onde | Faça | Esperado |
|---|------|------|----------|
| 1 | Financeiro › Recebimentos | **Registrar pagamento** → cliente → assinatura → `+` até 3 meses | Mostra "Cobre mm/aaaa a mm/aaaa", valor sugerido = meses × mensal; atrasados entram primeiro |
| 2 | mesmo diálogo | Mude a data para um dia passado e confirme | Toast "Pago até mm/aaaa"; Comercial mostra a coluna **Pago até** atualizada |
| 3 | mesmo diálogo | Desconto R$ 10,00 | Valor recebido cai R$ 10,00; ao **Estornar** o recebimento, desconto e meses voltam a ficar em aberto |
| 4 | Financeiro › Despesas | Nova despesa: Mensalidades e serviços, Mensal, data de 2 meses atrás, Já paga | Aparecem as ocorrências até o mês atual (a primeira paga); KPI "A pagar" atualiza |
| 5 | Despesas | **Pagar** numa ocorrência; **Parar repetição** no modelo | Paga hoje; não gera mais meses |
| 6 | Despesas | Única · Equipamentos (ex.: Rastreador) → **Vender ao cliente** | Cria Compra Direta em aberto; custo continua nas despesas |
| 7 | Planos/Produtos | **Editar** → `+ Adicionar custo` / `×` remover → salvar | Custo total e margem ao vivo; salva sem erro |
| 8 | Planos/Produtos | **Excluir** item sem uso / **Arquivar** item usado → **Reativar** | Sem uso some; usado fica "Arquivado" e volta ao reativar |
| 9 | Comercial › Assinaturas | **Ações ▾** | Registrar pagamento, Ajustar plano/valor/veículos, Compra direta, Abrir ficha, Pausar/Reativar, Cancelar |
| 10 | Ações › Ajustar | troque plano/quantidade/vencimento/veículos | Mensalidades já lançadas não mudam; as próximas usam o novo valor |
| 11 | Frotas/Veículos, Ficha da Frota ou Ficha do Cliente | **Mover** | Particular → frota, frota → frota, outro cliente; frotas incompatíveis aparecem desabilitadas |
| 12 | Ficha do Cliente | Coluna da esquerda | Foto do cliente no topo; foto do veículo selecionado embaixo (clique na linha do veículo para trocar) |
| 13 | Geral | Clique em botões, abas, menus; Esc fecha painéis | Resposta visual imediata; barra de progresso ao navegar |

## Testes automatizados leves desta etapa
`test_aj08_move_vehicle`, `test_aj10_subscription_amend`, `test_aj11_catalog`, `test_aj12_billing`,
`test_aj13_expenses`, `aj08_aj16_ui.test.mjs` — Python 81 (1 skip sqlcipher3), Node 64/64; smoke de UI sem erros de console.

## Correção encontrada no caminho
`POST /commercial/coverage` e `POST /fiscal/{id}/ensure-expense` chamavam a função sem o banco (erro 500). Corrigido.
