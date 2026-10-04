# R23 — Validação pesada antes da 1.004

Data: 2026-10-03. Todos os dados de teste são sintéticos; nenhum dado real foi lido ou usado.

| Bloco | Como | Resultado |
|---|---|---|
| Regressão | Python unittest (84) + Node (64) + engenharia (14) + compileall | OK (1 skip: SQLCipher só existe no runtime Windows) |
| Atualização real 1.001 → 1.004 | Dados gerados com o **código instalado** da 1.001 (System+Data, schema 8): 40 clientes, 120 veículos, 13 frotas, 40 assinaturas, 120 cobranças, pagamentos (1 estornado), vendas, despesas, fotos, anexo e backup. `Data` renomeada para `UserData` e aberta com a 1.004 | 39/39 verificações: login com o cofre antigo, schema 8→12, contagens e valores idênticos, códigos emitidos, cadeia de auditoria íntegra, fotos/anexo legíveis, telas, pagamento 1 clique, despesas, mover veículo, backup novo e restauração do backup antigo |
| Varredura de API | 110 rotas × ids válidos/inexistentes × 6 corpos hostis (641 requisições) | 0 erros 500 (12 respostas 501 são integrações planejadas, por desenho); idempotência e CSRF confirmados |
| Matriz de telas | 9 menus × abas × abridores de diálogo em 1440, 1024 e 390 px (105 células) | 0 erros de console; layout corrigido em 1024/390 |
| Jornadas ponta a ponta | 27 passos pela interface (cliente → empresa → frota → veículos → fotos → mover → assinatura → pagar → pausar/reativar/ajustar/compra/cancelar → estorno → despesas → catálogo → anexo → relatórios → backup) | 27/27 |
| Volume | 1.500 clientes, 4.500 veículos, 4.500 cobranças | Todas as telas < 1,5 s no navegador |

## Erros encontrados e corrigidos
1. **Fotos e anexos da 1.001 deixariam de abrir após a promoção** (caminhos `Data/...` gravados no banco). Resolvedor único aceita `Data/` e `UserData/` com qualquer barra e recusa caminhos absolutos/`..`.
2. **Frotas/Veículos levava 9 minutos com 4.500 veículos** (consultas por linha). Resumos em lote + índices: 0,3 s. Busca de clientes 645 → 30 ms.
3. **Layout cortado em notebooks (1024–1180 px)**: botões Sair/Encerrar cortados, tela de Frotas maior que a janela, colunas sobrepostas na tabela de frotas; tabelas sem rolagem própria no celular.
4. Data padrão da nova assinatura usava UTC (virava o dia seguinte à noite no Brasil).
5. Relatórios sem nomes em português e sem aviso de erro no download.
6. Mensagem de anexo duplicado pouco clara.
7. (Lote anterior) `/commercial/coverage` e `/fiscal/{id}/ensure-expense` respondiam 500.

## Fora do alcance do contêiner
SQLCipher real, WebView2, atalho e ícones no Windows: validados pelo uso do candidato no Windows pelo usuário e pelo primeiro login da 1.004 após a promoção.
