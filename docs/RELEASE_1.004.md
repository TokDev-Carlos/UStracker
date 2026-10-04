# UStracker 1.004 — versão oficial

Data: 2026-10-03 · Schema do banco: **12** · Plataforma: Windows x64 portátil (pasta única com `UStracker.exe` e `UserData`).

## O que há de novo desde a 1.001 instalada
- **Clientes:** códigos lógicos (`CLI-0001`, `-V01`, `-F01`, `-A01`…), ficha enxuta em abas com foto do cliente e do veículo selecionado.
- **Frotas/Veículos:** categorias (Carros, Caminhões, Embarcações, Aeronaves, Outros), Grupo da frota, visão Cliente › Empresa › Frota › Grupo, contagem de assinaturas com detalhe, **Mover veículo** em um passo.
- **Comercial:** menu **Ações** por assinatura (pagamento, ajuste de plano/valor/veículos, compra direta, pausar, reativar, cancelar) e coluna **Pago até**.
- **Financeiro:** **Registrar pagamento** em um clique (meses atrasados e adiantados, data retroativa, desconto opcional, sobra vira crédito); despesas **Mensal/Anual/Única** com categorias padrão, Pagar em um clique e "Vender ao cliente".
- **Planos/Produtos:** custos editáveis, excluir (sem uso) ou arquivar (em uso).
- **Visão Geral:** receita realizada × previsão do mês, resultado e detalhamento por período.
- **Visual:** identidade da marca, respostas visuais, telas que cabem em notebook.

## Atualização dos dados da 1.001
- A pasta `Data` da 1.001 passa a se chamar `UserData` (mesmos arquivos, mesmo login, mesma estação gravadora).
- No primeiro login o banco é atualizado do schema 8 para o 12 (só acréscimos; nada é apagado) e um backup automático é feito.
- Fotos e anexos gravados pela 1.001 (`Data/...`) continuam abrindo.
- Backups `.usbk` antigos continuam restauráveis.

## Verificação (R23)
Ver `engineering/reports/R23-heavy-validation/README.md`.
