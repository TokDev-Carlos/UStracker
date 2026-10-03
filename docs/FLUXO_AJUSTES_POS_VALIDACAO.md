# Fluxo de ajustes pós-validação básica

Estado: AJ-01..AJ-07 e R13..R22 implementados com testes leves (schema 11); aguardando testes pesados e validação humana. Roteiro: `docs/VALIDACAO_HUMANA_ENTREGA_TOTAL.md`.
humana do candidato `1.003`; não promove versão por si só.

## AJ-01 — Visão Geral: realizado acumulado e previsão mensal

### Regra de negócio

- `Receita Geral` representa somente receita realizada e não estornada, acumulada até hoje,
  dentro do período selecionado (`Geral` ou ano).
- O cartão atual de receita será dividido visualmente em dois indicadores lado a lado:
  `Receita Geral` e `Previsão do Mês`.
- `Previsão do Mês` representa o total esperado para a competência do mês corrente a partir
  de cobranças válidas de assinaturas e demais valores previstos pelo contrato financeiro.
- A previsão é informativa: não participa de `Resultado`.
- `Resultado = Receita Geral realizada - Despesas Gerais realizadas`.
- Valores futuros, cobranças anuladas, estornos e reversões não podem inflar a receita realizada.

### Aceite

- Uma assinatura sem pagamento aumenta a previsão/valor contratado, mas não a receita realizada.
- Um pagamento válido atualiza Receita Geral, Resultado, cliente e Comercial na mesma operação.
- A previsão permanece separada e visualmente identificada como não realizada.

## AJ-02 — Indicador detalhado de veículos

### Apresentação

- Exibir `Total Geral` na parte superior.
- Abaixo, exibir cinco grupos compactos com ícone, nome e quantidade:
  `Carros | Caminhões | Embarcações | Aeronaves | Outros`.
- A quantidade fica abaixo do ícone e o mesmo mapa semântico é usado em todas as telas.

### Normalização

- Tipos equivalentes são normalizados no backend para uma das cinco categorias.
- Tipos personalizados ou não reconhecidos entram em `Outros` sem perder o texto original.
- O total geral deve ser exatamente a soma das cinco categorias.

## AJ-03 — Cliente, Comercial e mobilidade como um fluxo único

### Cadastro guiado

O cadastro de cliente passa a permitir, na mesma jornada:

1. criar o cliente e a empresa;
2. adicionar veículo particular ou frota;
3. selecionar plano mensal para veículo(s) ou frota;
4. confirmar a assinatura; ou registrar uma compra direta quando aplicável.

Cada etapa salva pelo serviço de domínio já existente e preserva retomada segura. Não haverá
uma segunda implementação de regras comerciais no frontend.

### Projeções e sincronização

- Assinaturas e compras diretas aparecem dentro da Ficha do Cliente com acesso ao registro
  correspondente no Comercial.
- Comercial, Cliente, Frotas/Veículos e Visão Geral devem ler a mesma fonte de verdade.
- Toda mutação invalida e atualiza imediatamente as projeções afetadas, sem F5.
- A linha do cliente na Visão Geral separa `Valor contratado ativo` de `Receita realizada`.
  Assim, uma assinatura válida não aparece como `R$ 0,00` apenas por ainda não ter pagamento.
- Compra direta somente integra receita quando estiver efetivamente paga; antes disso aparece
  como contratação/valor aberto, não como receita.

## AJ-04 — Identificadores lógicos e tabelas compactas

### Identidade

- UUIDs atuais permanecem como chaves técnicas internas e deixam de ser exibidos nas tabelas.
- Cliente recebe sequência imutável e código público `CLI-0001`.
- Entidades dependentes recebem sequência por cliente:
  - veículo: `CLI-0001-V01`, `CLI-0001-V02`;
  - frota: `CLI-0001-F01`;
  - assinatura: `CLI-0001-A01`;
  - compra direta: `CLI-0001-C01`.
- Exclusão, arquivamento ou transferência não reutiliza números antigos.
- Registros existentes recebem códigos por migração aditiva e determinística, ordenados por
  data de criação e UUID como critério de desempate.

### Exibição

- Código lógico aparece em fonte menor e monoespaçada, sem dominar a tabela.
- Uma referência detalhada de veículo pode mostrar `CLI-0001-V02 · Marca Modelo · Placa` em
  contexto de detalhe, busca ou ficha.
- Em colunas cujo significado seja `Veículo`, o valor principal é a categoria (`Carro`,
  `Caminhão`, `Embarcação`, `Aeronave` ou `Outro`), não placa, nome ou UUID.
- Marca, modelo e placa ficam disponíveis como informação secundária, tooltip, expansão ou ficha.
- Números automáticos longos de assinatura, venda, cobrança e pagamento também usam código curto
  de apresentação; o identificador técnico nunca é truncado para persistência ou API.

## Ordem de execução

1. AJ-04: migração e serviço central de códigos lógicos.
2. AJ-02: normalização das categorias e agregados de veículos.
3. AJ-03: projeções unificadas e jornada Cliente → Mobilidade → Comercial.
4. AJ-01: indicadores financeiros e previsão mensal sobre as novas projeções.
5. Auditoria cruzada, regressão, validação visual Windows e promoção de versão.

Essa ordem evita construir tabelas e indicadores sobre contratos de identidade ainda instáveis.
