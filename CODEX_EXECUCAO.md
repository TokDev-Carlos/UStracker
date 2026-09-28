# UStracker — Contrato de Execução Direta para Codex

## 0. Autoridade e objetivo

Esta pasta é a **única baseline válida** para esta execução. Ela foi preparada a partir da fonte atualizada fornecida pelo usuário após a correção de fechamento da janela.

O objetivo é implementar o conteúdo funcional do **Plano 1** com o mínimo de investigação possível, preservando o que já funciona e mantendo o produto portátil.

### Não fazer

- NÃO reconstruir a fonte a partir do GitHub.
- NÃO procurar `.Arquivado`, workspace anterior, clone antigo, pacote antigo ou pasta pai.
- NÃO criar `docs/superpowers`, specs, planos auxiliares, relatórios de auditoria, matriz de testes ou nova árvore de handoff.
- NÃO criar nem executar suíte de testes nesta execução.
- NÃO fazer varredura ampla do projeto para “entender tudo”. O contexto necessário está neste arquivo.
- NÃO alterar autenticação, backup, recovery, estação escritora, atualização assinada ou criptografia, salvo erro de integração diretamente causado pelas mudanças desta execução.
- NÃO reintroduzir `pagehide -> /shell/detach`.
- NÃO reintroduzir o antigo fluxo de fechamento coordenado pelo frontend.
- NÃO apontar para caminho absoluto ou arquivo externo ao produto para corrigir ausência de dependência.

## 1. Estado atual que deve ser preservado

### Fechamento

O comportamento atual é intencional:

1. `UStracker.exe` inicia/reutiliza o backend.
2. `UStracker.exe` abre `UStracker.Shell.exe`.
3. O Bootstrap aguarda o Shell encerrar.
4. Ao fechar o Shell pelo X ou pelo comando global, o Shell termina.
5. O Bootstrap lê `UserData/State/backend.json`, confirma o PID do backend e encerra **somente** o `Runtime/pythonw.exe` pertencente a esta instalação.

A baseline já foi endurecida para comparar o executável do PID com `RootPaths.RuntimePython` antes de matar o processo.

### Sessão

- Refresh não faz logout.
- `/shell/detach` é neutro.
- Logout explícito continua em `/auth/logout`.
- O perfil WebView2 foi movido para `UserData/State/WebView2`, portanto acompanha a pasta do produto e não depende de `%LOCALAPPDATA%`.

### Frontend

Já existem módulos e devem ser reutilizados:

- `frontend/ui/api.js` — chamadas HTTP/CSRF/operação.
- `frontend/ui/session.js` — bootstrap/login/logout.
- `frontend/ui/shell.js` — shell/topbar/menu.
- `frontend/ui/table-controller.js` — tabelas.
- `frontend/ui/overlay.js` — drawer/toast.
- `frontend/ui/tokens.css` e `components.css` — sistema visual.
- `frontend/ui/help-catalog.js` — ajuda contextual.
- `frontend/ui/icon-registry.js` — iconografia.

`Clientes` já usa a Tabela Central + drawer. Não voltar para o padrão antigo.

### Backend

- FastAPI local em `127.0.0.1`.
- SQLite/SQLCipher dentro de `UserData/<Environment>/ustracker.db`.
- Schema atual: `2`.
- `payments` representa dinheiro recebido de cobranças de assinatura.
- `disbursements` representa dinheiro efetivamente gasto.
- `media` já é genérica por `entity_type + entity_id` e será reutilizada para Cliente e Veículo.
- `public_projection.py` já expõe branding + catálogo público para a tela de Login.

## 2. Arquivos que você deve ler

Leia somente estes antes de editar:

1. `src/ustracker/db.py`
2. `src/ustracker/services.py`
3. `src/ustracker/extensions.py`
4. `src/ustracker/server.py`
5. `src/ustracker/media.py`
6. `frontend/app.js`
7. `frontend/styles.css`
8. `frontend/ui/components.css`
9. `frontend/ui/tokens.css`
10. `frontend/ui/table-controller.js`
11. `frontend/ui/overlay.js`
12. `frontend/ui/help-catalog.js`
13. `frontend/ui/datasets.js`

Leia `host/*` e `tools/package.ps1` apenas se ocorrer erro de compilação/empacotamento. A portabilidade estrutural desses arquivos já foi preparada.

## 3. Decisões fechadas do Plano 1

### 3.1 Quantidade de Clientes

Contar:

```sql
SELECT COUNT(*) FROM clients WHERE archived=0
```

Não limitar a `status='ACTIVE'`, pois o Plano 1 pede quantidade de Clientes, não apenas clientes ativos.

### 3.2 Quantidade de Produtos

Contar entradas ativas do catálogo:

```sql
SELECT COUNT(*) FROM catalog WHERE active=1
```

`PLAN` e `ITEM` entram. Não contar linhas de assinatura nem de compra como novos produtos.

### 3.3 Quantidade de Veículos

```sql
SELECT COUNT(*) FROM vehicles WHERE archived=0
```

### 3.4 Quantidade de Assinaturas Ativas

O Plano 1 define a quantidade como os **produtos/unidades que estão em assinatura**, seja diária, mensal ou anual. Portanto NÃO contar apenas contratos de `subscriptions`.

Usar:

```sql
SELECT COALESCE(SUM(si.quantity),0)
FROM subscription_items si
JOIN subscriptions s ON s.id=si.subscription_id
WHERE s.lifecycle_status='ACTIVE'
```

Compras diretas nunca entram nesse indicador.

### 3.5 Periodicidade de assinatura

A interface precisa distinguir:

- `DAILY` → Diário
- `MONTHLY` → Mensal
- `ANNUAL` → Anual

Adicionar `billing_cycle` em `subscriptions`.

Manter `billing_interval_months` por compatibilidade nesta revisão. Para novos registros:

- DAILY → `billing_interval_months=0`
- MONTHLY → `billing_interval_months=1`
- ANNUAL → `billing_interval_months=12`

Não criar agora um novo motor automático de geração diária/anual de cobranças. A periodicidade nesta etapa classifica corretamente a assinatura e o Dashboard; a geração de `charges` existente continua por competência manual.

### 3.6 Valor Mensal

Significa **entrada financeira efetivamente realizada no mês calendário atual**.

```text
Valor Mensal
= pagamentos de assinatura não estornados recebidos no mês
+ compras diretas PAID cuja paid_on pertence ao mês
```

Não usar `charges` abertas, receita prevista ou créditos abertos neste card.

### 3.7 Valor Gasto

Significa desembolso efetivamente realizado no mês atual:

```text
Valor Gasto
= SUM(disbursements.amount_cents)
  onde reversed_at IS NULL
  e paid_on está dentro do mês atual
```

Não usar `expenses.expected_amount_cents` neste card.

### 3.8 Lucro Real

```text
Lucro Real = Valor Mensal - Valor Gasto
```

Pode ser negativo.

### 3.9 Valor Acumulado

O Plano 1 diz: “valor total de todos os Lucros de meses anteriores, esse cálculo é anual”.

Definição fechada:

```text
Valor Acumulado
= receitas realizadas de 01/01 do ano atual até o primeiro dia do mês atual
- desembolsos realizados no mesmo intervalo
```

Portanto:

- não inclui o mês corrente;
- reinicia a cada ano;
- em janeiro é zero;
- inclui pagamentos de assinatura + compras diretas pagas;
- subtrai desembolsos não estornados.

### 3.10 Coluna Compras no Dashboard

O PDF não define período para esta coluna. Nesta execução, usar interpretação estável e útil:

```text
Compras = valor histórico total das compras diretas não canceladas do Cliente
```

Não confundir com Valor Mensal.

### 3.11 Coluna Mensalidade no Dashboard

Como um mesmo Cliente pode possuir periodicidades diferentes, NÃO inventar conversão diária/anual para “equivalente mensal”.

O backend deve devolver três valores:

- `subscription_daily_cents`
- `subscription_monthly_cents`
- `subscription_annual_cents`

A célula `Mensalidade` deve mostrar somente os ciclos existentes, por exemplo:

```text
R$ 15,00/dia
R$ 120,00/mês
R$ 1.200,00/ano
```

Se houver mais de um ciclo, concatenar com separador visual curto.

## 4. Alteração de banco — schema 3

Em `src/ustracker/db.py`:

```python
SCHEMA_VERSION = 3
```

### 4.1 subscriptions

No `SCHEMA_SQL`, adicionar:

```sql
billing_cycle TEXT NOT NULL DEFAULT 'MONTHLY',
```

preservando `billing_interval_months`.

Na migração `current_version < 3`:

1. verificar `PRAGMA table_info(subscriptions)`;
2. se `billing_cycle` não existir:

```sql
ALTER TABLE subscriptions ADD COLUMN billing_cycle TEXT NOT NULL DEFAULT 'MONTHLY';
```

3. compatibilizar registros antigos:

```sql
UPDATE subscriptions
SET billing_cycle = CASE
    WHEN billing_interval_months >= 12 THEN 'ANNUAL'
    ELSE 'MONTHLY'
END;
```

### 4.2 direct_sales

Adicionar ao `SCHEMA_SQL`:

```sql
CREATE TABLE IF NOT EXISTS direct_sales(
 id TEXT PRIMARY KEY,
 client_id TEXT NOT NULL REFERENCES clients(id),
 sold_on TEXT NOT NULL,
 status TEXT NOT NULL DEFAULT 'OPEN',
 paid_on TEXT,
 total_cents INTEGER NOT NULL DEFAULT 0,
 notes TEXT,
 revision INTEGER NOT NULL DEFAULT 1,
 created_at TEXT NOT NULL,
 updated_at TEXT NOT NULL
);
```

Estados aceitos pela camada de serviço:

```text
OPEN
PAID
CANCELLED
```

### 4.3 direct_sale_items

```sql
CREATE TABLE IF NOT EXISTS direct_sale_items(
 id TEXT PRIMARY KEY,
 sale_id TEXT NOT NULL REFERENCES direct_sales(id) ON DELETE CASCADE,
 catalog_id TEXT REFERENCES catalog(id),
 vehicle_id TEXT REFERENCES vehicles(id),
 description TEXT NOT NULL,
 quantity INTEGER NOT NULL DEFAULT 1,
 unit_price_cents INTEGER NOT NULL
);
```

Índices:

```sql
CREATE INDEX IF NOT EXISTS ix_direct_sales_client ON direct_sales(client_id,sold_on,status);
CREATE INDEX IF NOT EXISTS ix_direct_sales_paid ON direct_sales(paid_on,status);
CREATE INDEX IF NOT EXISTS ix_direct_sale_items_sale ON direct_sale_items(sale_id);
```

Não criar tabela separada de pagamento de compra nesta revisão. `PAID + paid_on` é suficiente para o Plano 1.

## 5. Backend — funções exatas

Implementar em `services.py`, seguindo o estilo já existente de `uid()`, `now()`, `parse_money_api()`, transação e `audit()`.

### 5.1 create_direct_sale

Assinatura:

```python
def create_direct_sale(db: Database, actor: int, p: dict) -> dict:
```

Payload aceito:

```json
{
  "client_id": "uuid",
  "sold_on": "2026-09-14",
  "status": "OPEN",
  "paid_on": null,
  "notes": "",
  "items": [
    {
      "catalog_id": "uuid",
      "vehicle_id": null,
      "description": "opcional quando houver catalog_id",
      "quantity": 1,
      "unit_price": "199.90"
    }
  ]
}
```

Regras:

- `client_id` obrigatório e deve existir.
- ao menos um item.
- `quantity > 0`.
- se `catalog_id` existir, validar catálogo ativo e usar `catalog.name` como descrição quando ela não vier.
- se `unit_price` não vier e houver catálogo, usar `catalog.price_cents`.
- se `vehicle_id` vier, o veículo deve existir e pertencer ao mesmo Cliente.
- `total_cents = SUM(quantity * unit_price_cents)`.
- status inicial permitido: `OPEN` ou `PAID`.
- se `PAID`, `paid_on = payload.paid_on or sold_on`.
- registrar `DIRECT_SALE_CREATE` em auditoria.
- retornar cabeçalho + `items`.

### 5.2 set_direct_sale_status

```python
def set_direct_sale_status(db: Database, actor: int, sale_id: str, p: dict) -> dict:
```

- aceitar `OPEN`, `PAID`, `CANCELLED`;
- respeitar `expected_revision` quando vier;
- `PAID`: `paid_on = payload.paid_on or today`;
- `OPEN`: `paid_on = NULL`;
- `CANCELLED`: `paid_on = NULL`;
- incrementar `revision` e `updated_at`;
- auditar `DIRECT_SALE_STATUS`.

### 5.3 list_direct_sales

```python
def list_direct_sales(db: Database) -> list[dict]:
```

Retornar cabeçalho das vendas com:

```text
id
client_id
client_name
sold_on
status
paid_on
total_cents
item_count
notes
revision
created_at
updated_at
```

Ordenar por `sold_on DESC, created_at DESC`.

### 5.4 client_profile

Implementar:

```python
def client_profile(db: Database, client_id: str) -> dict:
```

Retornar exatamente esta estrutura conceitual:

```json
{
  "client": {},
  "client_media": [],
  "fleets": [],
  "vehicles": [],
  "vehicle_media": {},
  "subscriptions": [],
  "direct_sales": [],
  "financial": {
    "subscription_received_cents": 0,
    "direct_sales_paid_cents": 0,
    "client_expenses_paid_cents": 0
  }
}
```

Detalhes:

- `client_media`: linhas de `media` com `entity_type='client'` e `entity_id=client_id`.
- `vehicle_media`: mapa `{vehicle_id: [media...]}` para `entity_type='vehicle'`.
- `subscriptions`: cada assinatura deve trazer seus `subscription_items`.
- `direct_sales`: cada compra deve trazer seus `direct_sale_items`.
- `client_expenses_paid_cents`: somente desembolsos de despesas explicitamente vinculadas a esse cliente.

Não criar tabela `companies` nesta revisão. A Ficha usa os campos já existentes do Cliente (`legal_name`, `trade_name`, `public_name`, `document`, contato) para o card de Empresa/Identificação.

## 6. Dashboard — retorno exato da API

Preservar os campos operacionais antigos e acrescentar estes campos principais em `dashboard()`:

```text
clients_count
products_count
vehicles_count
active_subscription_products
accumulated_profit_cents
monthly_value_cents
monthly_spent_cents
real_profit_cents
client_overview
```

### 6.1 Faixas de data

Calcular em Python, não espalhar SQL de datas pelo frontend:

```text
year_start   = 01/01 do ano atual
month_start  = primeiro dia do mês atual
next_month   = primeiro dia do mês seguinte
```

Usar intervalos `[início, fim)`.

### 6.2 client_overview

Cada item:

```json
{
  "client_id": "uuid",
  "client_name": "Nome",
  "cars": 2,
  "subscription_daily_cents": 0,
  "subscription_monthly_cents": 15000,
  "subscription_annual_cents": 0,
  "purchases_cents": 39990
}
```

Somente clientes `archived=0`.

`purchases_cents` soma `direct_sales.total_cents` onde status != `CANCELLED`.

Valores de assinatura são soma de `subscription_items.quantity * unit_price_cents` de assinaturas `ACTIVE`, agrupados por `billing_cycle`.

## 7. Rotas FastAPI

Em `server.py`, importar as novas funções e adicionar:

### GET `/api/v1/direct-sales`

- sessão autenticada;
- `return {'items': list_direct_sales(db)}`.

### POST `/api/v1/direct-sales`

- mutação normal via `mutation()`;
- em Production continua sujeito à regra da estação escritora;
- chamar `create_direct_sale()`.

### PATCH `/api/v1/direct-sales/{sale_id}/status`

- mutação normal via `mutation()`;
- chamar `set_direct_sale_status()`.

### GET `/api/v1/clients/{client_id}/profile`

- sessão autenticada;
- retornar `client_profile()`.

Não criar endpoints redundantes de foto: usar os já existentes `/media/...`.

## 8. Frontend — Dashboard

Substituir o bloco principal atual por oito cards, nesta ordem e com estes textos exatos:

1. `Quantidade de Clientes`
2. `Quantidade de Produtos`
3. `Quantidade de Veículos`
4. `Assinaturas Ativas`
5. `Valor Acumulado`
6. `Valor Mensal`
7. `Valor Gasto`
8. `Lucro Real`

Mapeamento:

```text
Quantidade de Clientes -> clients_count
Quantidade de Produtos -> products_count
Quantidade de Veículos -> vehicles_count
Assinaturas Ativas -> active_subscription_products
Valor Acumulado -> accumulated_profit_cents
Valor Mensal -> monthly_value_cents
Valor Gasto -> monthly_spent_cents
Lucro Real -> real_profit_cents
```

Abaixo, usar `createTableController()` com colunas visuais:

```text
Cliente | Carros | Mensalidade | Compras | Abrir Ficha
```

`Abrir Ficha` deve ser ação de linha, não ID cru.

Indicadores antigos podem permanecer depois da tabela em seção secundária `Indicadores Operacionais`, sem competir visualmente com os oito cards principais.

## 9. Frontend — Compras Diretas

Adicionar navegação:

```text
Compras Diretas
```

Usar chave interna `purchases` no frontend e endpoint `/direct-sales`.

Criar `purchasesPage()` usando os componentes existentes. Não criar novo framework de formulário.

Fluxo mínimo:

1. selecionar Cliente;
2. data da compra;
3. adicionar um ou mais itens do catálogo;
4. veículo opcional;
5. quantidade;
6. preço unitário;
7. status OPEN ou PAID;
8. se PAID, permitir data de pagamento;
9. salvar;
10. listar compras;
11. permitir mudança de status.

Não implementar parcelamento, desconto complexo, impostos ou estoque nesta revisão.

Atualizar `frontend/ui/datasets.js` e `help-catalog.js` para refletir `purchases` e `billing_cycle`.

## 10. Frontend — Ficha do Cliente

Criar função única no `app.js`:

```javascript
async function openClientProfile(clientId) { ... }
```

Ela deve ser usada em dois lugares:

- botão `Abrir Ficha` da tabela do Dashboard;
- ação `Abrir Ficha` da página Clientes.

Usar o `openDrawer()` existente e aplicar classe de largura ampliada ao drawer. Não criar modal paralelo.

### Cards recolhíveis

Usar `<details>` / `<summary>` para atender “cards que podem estender e ocultar”.

Ordem:

1. Cliente
2. Empresa / Identificação
3. Foto do Cliente
4. Frotas
5. Veículos
6. Assinaturas
7. Compras Diretas
8. Resumo Financeiro

### Fotos

- Cliente: primeiro item de `client_media` como foto principal.
- Veículos: primeira mídia de cada veículo como miniatura.
- URL existente: `/api/v1/media/{media_id}/thumb`.
- Não duplicar arquivos, não criar blob em banco, não criar outra pasta de imagens.

## 11. Frontend — Login

Não tocar em autenticação ou sessão. Alterar somente renderização e CSS.

### Layout obrigatório

- cartão amplo/horizontal;
- logo grande do UStracker centralizado na parte superior;
- abaixo do logo, corpo em duas áreas em desktop:
  - Acesso;
  - Planos e Serviços;
- em largura pequena, empilhar as áreas.

### Ambiente

Exibir escolha visível:

```text
REAL | TESTE
```

- `REAL` selecionado por padrão em toda abertura da tela;
- REAL envia `environment='production'`;
- TESTE envia `environment='test'`;
- não alterar nomes internos do backend.

### Planos e Serviços

Usar exclusivamente `pub.catalog` já entregue por `/api/v1/public`.

É uma prévia comercial, não um segundo cadastro.

### Logo

Preferência:

1. `pub.brand.assets.logo` quando existir;
2. fallback para o logo do icon set interno.

Não depender de arquivo externo.

## 12. Regra visual

O Plano 1 pede capitalização, centralização e cores leves/lógicas.

Aplicar assim:

- títulos de página: capitalização consistente e centralização quando forem bloco principal;
- títulos/valores dos oito cards: centralizados;
- cabeçalhos da tabela do Dashboard: centralizados;
- texto de botões: centralizado;
- Login e marketing: centralizados;
- células operacionais longas e labels de formulário podem permanecer com alinhamento natural para legibilidade.

Cores:

- Azul leve: ação principal/informação;
- Verde leve: valor positivo/sucesso;
- Âmbar leve: atenção/pendência;
- Vermelho somente para erro/ação destrutiva;
- Cinza: secundário/neutro.

Reutilizar `tokens.css` e `components.css`. Não introduzir biblioteca CSS nova.

## 13. Portabilidade e estrutura

Estas regras são absolutas:

- o produto deve resolver caminhos a partir da própria pasta;
- `UserData` permanece dentro da pasta do produto;
- perfil WebView2 permanece em `UserData/State/WebView2`;
- Python de runtime permanece em `Runtime/`;
- frontend permanece embarcado na pasta do produto;
- Trust permanece dentro da pasta;
- não usar `%LOCALAPPDATA%` como dependência de estado do UStracker;
- não usar `.Arquivado`;
- não usar `C:\UStracker` ou caminho de workspace;
- não copiar `bin/obj/tests/__pycache__` para o pacote final;
- `tools/package.ps1` deve gerar o pacote a partir da fonte atual, não de executáveis antigos.

O fallback do WebView2 pode usar o instalador offline que está dentro do próprio pacote. Se `Runtime/WebView2` for fornecido no futuro, o Shell já prefere essa versão fixa antes do runtime instalado no Windows.

## 14. Versão

Nesta execução:

- NÃO aumentar `product/version` ainda;
- aumentar apenas `schema_version` de `2` para `3` em:
  - `src/ustracker/db.py`;
  - `VERSION.json`;
  - `current.json`.

A versão do produto será definida depois da revisão visual/funcional do usuário.

## 15. Ordem de execução

Executar sem desviar desta sequência:

1. Schema 3 + migração.
2. Serviços de Compra Direta.
3. Dashboard financeiro/contadores/client_overview.
4. Rotas novas.
5. Periodicidade DAILY/MONTHLY/ANNUAL na Assinatura.
6. Página Compras Diretas.
7. Dashboard visual + tabela Cliente.
8. Ficha do Cliente.
9. Login.
10. Ajustes visuais finais.
11. Atualizar `VERSION.json/current.json` somente no `schema_version`.
12. Executar `tools/package.ps1` uma única vez ao final.
13. Se o build/empacotamento acusar erro, corrigir apenas a causa concreta e repetir o build.

## 16. Critério de parada

Não gerar relatório longo.

Ao terminar, responder somente:

```text
ALTERADOS:
- <arquivos>

PACOTE:
- <caminho do zip gerado>

CORREÇÕES INCIDENTAIS:
- <somente erros reais encontrados durante a execução, se houver>

BLOQUEIO:
- nenhum
```

Se houver bloqueio real que exija decisão do usuário, parar no ponto exato e descrevê-lo em no máximo cinco linhas.
