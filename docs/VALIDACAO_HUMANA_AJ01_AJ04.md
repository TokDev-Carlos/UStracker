# Validação humana — Ajustes AJ-01 a AJ-04

Estado: **IMPLEMENTADO, AGUARDANDO VALIDAÇÃO HUMANA**. Versão oficial permanece `1.003` (schema `10`).
Candidato: `Dist/UStracker_1.003-AJ_win-x64` (cópia isolada, com cópia do UserData da homologação).
AJ-04 detalhado em `VALIDACAO_HUMANA_AJ04.md`.

## AJ-02 — Veículos por categoria
1. Visão Geral: bloco "Veículos" com Total Geral e cinco grupos (Carros, Caminhões, Embarcações, Aeronaves, Outros), ícone, nome e quantidade.
2. Total Geral = soma dos cinco grupos.
3. Cadastrar um tipo próprio (ex.: Trator): entra em Outros; passe o mouse em Outros para ver o tipo original.
4. Mesmo mapa em Frotas/Veículos, Ficha da Frota e Ficha do Cliente.

## AJ-03 — Cliente → Mobilidade → Comercial
1. Clientes › Novo cliente › Salvar: a Ficha abre sozinha na jornada (1 Cliente ✓ · 2 Mobilidade · 3 Plano ou compra).
2. Na Ficha, card Veículos: "Adicionar veículo" e "Adicionar frota" (frota exige empresa do cliente).
3. Passo 3: "Assinar plano" (fluxo de assinatura sem reescolher cliente) ou "Compra direta".
4. Card Assinaturas lista assinaturas e compras com código e botão "Abrir no Comercial" (abre a aba certa e destaca a linha).
5. Com a Ficha aberta, a lista de fundo (Clientes/Visão Geral/Frotas) se atualiza sozinha, sem F5.
6. Visão Geral e Clientes: colunas "Valor contratado ativo" e "Receita realizada" separadas — assinatura sem pagamento não aparece mais como R$ 0,00 de valor.

## AJ-01 — Receita Geral × Previsão do Mês
1. Cartão dividido: à esquerda Receita Geral (realizada até hoje), à direita Previsão do Mês (etiqueta "Não realizada · fora do Resultado").
2. Assinatura sem pagamento: aumenta Previsão e Valor contratado; Receita Geral e Resultado não mudam.
3. Registrar recebimento: Receita Geral, Resultado, Ficha do cliente e Clientes mudam juntos; Previsão não dobra.
4. Recebimento com data futura ou compra em aberto não entram na Receita Geral.
5. Resultado = Receita Geral − Despesas Gerais (realizadas).

## Limites
- Passada leve: testes focados + regressão Python/Node no Linux + smoke de interface em navegador headless. Sem smoke Windows automatizado.
- Previsão usa equivalente mensal para assinaturas legadas não mensais (anual ÷ 12, diária × 30).
