# UStracker — Plano de Reestruturação Incremental

> **Para execução por agentes:** SUB-SKILL OBRIGATÓRIA: usar `superpowers:subagent-driven-development` (recomendado) ou `superpowers:executing-plans` para executar este plano tarefa por tarefa. As etapas usam caixas de seleção (`- [ ]`) para acompanhamento.

**Objetivo:** Evoluir o UStracker 1.00.01.000 para a nova organização operacional, comercial e financeira, preservando autenticação, segurança, backup, auditoria, banco criptografado, cálculos existentes e identidade visual já funcional.

**Arquitetura:** Manter o frontend JavaScript modular, o backend FastAPI/Python, o host Windows/WebView2 e o SQLCipher. A evolução será feita por migrações aditivas de banco, serviços de domínio isolados, endpoints compatíveis e composição de páginas por abas; módulos redundantes deixam o menu, mas seus registros financeiros continuam disponíveis internamente até a migração ser validada.

**Stack confirmada no pacote:** JavaScript ES Modules, HTML/CSS, Python 3.13, FastAPI, SQLCipher/SQLite, Pillow, host .NET Framework/WebView2, Windows x64.

**Instalação ativa verificada:** `C:\UStracker` — versão 1.00.01.000, schema 3.

**Pacote de instalação verificado:** `C:\Users\Carlos Alberto\Downloads\UStracker_1.00.01.000_instalacao_20260915_2337.zip` — SHA256 `D7E6AE841C794D5704F9F4455B5D70EA144663AB8BD41FD2119C79B3033C025F`.

**Fonte canônica verificada:** `C:\UStracker\.Arquivado\R2_source_20260915\UStracker` — contém frontend, backend, host .NET, testes, documentação e empacotador correspondentes à instalação ativa. Esta árvore ainda não possui `.git`.

**Especificação:** Este documento consolida os requisitos fornecidos em 28/09/2026, a auditoria do pacote e a comparação direta com a instalação ativa e a fonte canônica.

## Resumo da auditoria

- O frontend já está separado em `frontend/app.js`, `frontend/ui/shell.js`, `frontend/ui/table-controller.js`, `frontend/ui/r2-ui.js`, tokens e componentes CSS.
- O backend está em `Runtime/Lib/site-packages/ustracker/`, com rotas em `server.py`, serviços em `services.py` e `extensions.py`, schema em `db.py`, mídia em `media.py` e dinheiro em `money.py`.
- O banco de Produção é SQLCipher; alterações devem ser feitas por migração versionada, nunca editando o arquivo diretamente.
- A autenticação, estação escritora, idempotência, auditoria, backup/recovery e revisão otimista já existem e devem ser preservados.
- O favicon está inicialmente configurado como `data:,`; a marca dinâmica só aparece quando existe branding cadastrado.
- O rótulo `PRODUÇÃO · ESCRITORA` é gerado por `environmentLabel()` em `frontend/ui/shell.js`.
- A barra superior não é fixa e hoje contém a busca global; a busca solicitada para a Visão Geral deve ser uma busca contextual separada.
- Valores são armazenados em centavos, mas a API atual espera decimal com ponto. A interface brasileira precisa de uma camada única de máscara e normalização.
- Todos os 1.508 arquivos não pertencentes a `UserData` no ZIP coincidem byte a byte com `C:\UStracker`.
- Dentro de `UserData`, 272 arquivos coincidem, 54 divergem e 4 arquivos antigos não existem mais na instalação ativa. As divergências incluem `Auth/auth.db`, `Production/ustracker.db`, projeção pública, estado de backup e cache WebView2; portanto o ZIP não é backup do estado atual.
- O ZIP contém dados operacionais e autenticação. Ele não deve ser enviado a uma IA externa sem remoção de `UserData/Auth`, `UserData/Production`, `UserData/Test`, `UserData/Backups` e `UserData/State/WebView2`.
- O pacote de instalação não contém o projeto-fonte C#, `.csproj`, testes ou scripts de build. Esses itens existem na fonte canônica local e devem acompanhar qualquer transferência para outra IA.
- A fonte canônica corresponde ao produto ativo: 18/18 arquivos do backend, 51/51 arquivos do frontend e os três executáveis compilados têm hashes iguais aos arquivos instalados.

## Contrato de execução por outra IA

1. `C:\UStracker` é referência instalada e fonte dos dados atuais. Não editar, compilar ou testar diretamente nessa pasta.
2. `C:\UStracker\.Arquivado\R2_source_20260915\UStracker` é a baseline de código. Copiá-la para uma árvore de trabalho isolada antes de qualquer alteração.
3. A árvore recomendada nesta máquina é `C:\UStracker\.Arquivado\workspaces\ustracker_reestruturacao_20260928`.
4. Alterações de backend devem ocorrer em `src/ustracker/`; nunca editar `Runtime/Lib/site-packages/ustracker/` manualmente.
5. O pacote distribuível é sempre gerado por `tools/package.ps1`; arquivos de `Runtime` são produto de build.
6. Não copiar nem versionar `UserData`. Testes usam diretórios temporários e fixtures anônimas.
7. Para execução em outra máquina/IA, enviar dois artefatos: o ZIP de instalação como referência binária e um ZIP de fonte/handoff contendo a fonte canônica, este plano e o relatório de auditoria, sem `UserData`, `bin`, `obj`, `Dist`, `.venv`, `__pycache__` ou caches.
8. Se a outra IA receber somente o ZIP de instalação, deve parar. Não decompilar ou remendar executáveis.
9. O pipeline atual gera ZIP portátil e SHA256; ele não assina os executáveis do produto e não cria MSI/Setup. Não alegar assinatura ou instalador até existir certificado e pipeline próprios.
10. Nenhuma etapa publica release nem substitui `C:\UStracker` sem autorização expressa.

### Preflight obrigatório

Na máquina atual, iniciar com:

```powershell
$InstallRoot = 'C:\UStracker'
$SourceBase = 'C:\UStracker\.Arquivado\R2_source_20260915\UStracker'
$WorkRoot = 'C:\UStracker\.Arquivado\workspaces\ustracker_reestruturacao_20260928'
$ReferenceZip = 'C:\Users\Carlos Alberto\Downloads\UStracker_1.00.01.000_instalacao_20260915_2337.zip'

Get-FileHash -Algorithm SHA256 -LiteralPath $ReferenceZip
Test-Path -LiteralPath "$SourceBase\src\ustracker\server.py"
Test-Path -LiteralPath "$SourceBase\host\Shell\Shell.csproj"
Test-Path -LiteralPath "$SourceBase\tests\test_r2_backend.py"
```

Resultado obrigatório: hash igual ao declarado acima e os três `Test-Path` retornando `True`. Se qualquer verificação falhar, interromper a execução.

Toolchain verificada nesta máquina em 28/09/2026: Python 3.13.15 com pip 26.2.1, Node 24.19.0 e .NET SDK 10.0.400. O launcher `py` não está instalado; usar `python` ou o caminho explícito `C:\UStracker\Runtime\python.exe` conforme os comandos deste plano.

`tools/package.ps1` precisa baixar artefatos com hashes fixos ou receber previamente o cache de `C:\UStracker\.Arquivado\R2_build_20260915\_cache`. Em ambiente externo sem rede, fornecer esse cache separadamente; não remover nem flexibilizar as verificações SHA256 e Authenticode do WebView2.

## Decisões funcionais consolidadas

1. A instrução financeira mais recente prevalece: **Fiscal fica dentro de Financeiro**, junto de Despesas e Recebimentos.
2. A navegação final será: **Visão Geral; Clientes; Frotas/Veículos; Planos/Produtos; Comercial; Financeiro; Fotos/Arquivos; Relatórios; Sistema**.
3. **Comercial** terá abas internas: Assinaturas, Compras Diretas e Créditos/Tempo Ativo.
4. **Financeiro** terá abas internas: Recebimentos, Despesas e Fiscal.
5. Cobranças saem do menu, mas a tabela e a lógica de `charges` permanecem como razão interna de assinaturas, alocações, créditos e inadimplência.
6. “Excluir cliente” será exclusão lógica/arquivamento. Exclusão física quebraria vínculos históricos, auditoria e financeiro.
7. Documentos de cliente serão registros próprios (CPF, RG ou CNH), exigindo ao menos um; contato exige e-mail ou telefone.
8. Empresa deixa de ser um único texto e passa a aceitar uma ou mais empresas vinculadas ao cliente.
9. Veículo sem frota é Particular. Frota só pode ser criada para uma empresa vinculada ao cliente e começa limitada a 100 veículos ativos.
10. Transferência de propriedade terá um caso pendente isolado; a propriedade vigente só muda quando o caso é concluído com sucesso.
11. Crédito monetário e tempo de serviço pré-pago são conceitos distintos. O sistema preservará o saldo financeiro existente e criará cobertura temporal calculada por período.
12. Fotos usarão a API de mídia já existente, com miniatura e versão operacional compactada. PDFs, assinaturas e arquivos online usarão um repositório de anexos separado, preparado para futuro Google Drive.

## Restrições globais

- Não reescrever o frontend em framework novo.
- Não alterar o formato criptografado dos bancos fora das migrações oficiais.
- Não remover tabelas ou endpoints antigos antes de migração, compatibilidade e backup restaurável serem comprovados.
- Toda escrita em Produção continua exigindo estação escritora, CSRF, idempotência e auditoria.
- Todo valor monetário é armazenado em centavos inteiros e exibido em pt-BR, por exemplo `R$ 0,00` e `R$ 1.234,56`.
- Campos monetários são texto com `inputmode="decimal"`; nunca `input type="number"`.
- Datas persistem em ISO; a interface exibe `DD/MM/AAAA - HH:MM:SS` quando houver hora e `DD/MM/AAAA` quando o domínio tiver apenas data.
- A primeira entrega é desktop. CSS e componentes não devem impedir adaptação posterior para tablet e celular.
- Nenhuma fase avança sem backup válido, testes da fase e homologação do ponto de parada.
- Migrações devem ser sequenciais, idempotentes e testadas partindo do schema 3. Nunca marcar uma versão de schema como concluída antes de todas as operações daquela migração terminarem na mesma transação.
- Clientes legados sem documento ou contato não recebem dados fictícios: permanecem legíveis e são marcados para revisão; a obrigatoriedade vale para novos cadastros e para registros legados quando forem editados.
- O número da versão instalada não muda durante desenvolvimento. A versão final deve ser maior que `1.00.01.000` e só será definida com autorização de release.

## Foco de revisão

- Migração de uma base schema 3 com dados reais, sem perda e com restore confirmado.
- Valores digitados como `1.234,56`, `1234,56`, `0,00`, colagem com `R$` e rejeição de entradas ambíguas.
- Clientes com vínculos históricos não podem ser destruídos por exclusão em lote.
- Frota no limite de 100 veículos deve bloquear o 101º sem afetar veículos particulares.
- Transferência pendente, cancelada e concluída deve preservar uma única propriedade vigente.
- Pagamento antecipado deve produzir cobertura temporal correta em mudanças de mês, anos bissextos e planos anuais.
- Abas e rotas antigas não podem interromper relatórios, busca global, auditoria ou backups.

---

## Estrutura de arquivos prevista

### Arquivos existentes a modificar

- `frontend/index.html` — favicon padrão confiável.
- `frontend/app.js` — roteamento das novas páginas compostas e retirada de itens redundantes do menu.
- `frontend/styles.css` — shell fixo, tabelas compactas, quebra de texto e acabamento visual.
- `frontend/ui/shell.js` — cabeçalho fixo, identidade do usuário e ações globais.
- `frontend/ui/table-controller.js` — busca por Enter/botão, seleção múltipla e colunas responsivas.
- `frontend/ui/r2-ui.js` — ficha do cliente e componentes já existentes.
- `frontend/ui/help-catalog.js` e `frontend/ui/pt-br.js` — ajuda e terminologia nova.
- `src/ustracker/db.py` — migrações e índices; a baseline atual usa `SCHEMA_VERSION = 3`.
- `src/ustracker/server.py` — endpoints `/api/v1` e compatibilidade.
- `src/ustracker/services.py` — regras de clientes, produtos, compras e dashboard.
- `src/ustracker/extensions.py` — frotas, transferências e finanças complementares.
- `src/ustracker/money.py` — contrato monetário.
- `src/ustracker/media.py` — validação de imagens e entidades permitidas.
- `src/ustracker/backup.py`, `recovery.py`, `reports.py` e `public_projection.py` — consumidores obrigatórios de qualquer mudança de schema.
- `host/Bootstrap/Bootstrap.csproj` e `Program.cs` — inicialização e atalho.
- `host/Shell/Shell.csproj`, `App.xaml` e `MainWindow.xaml*` — WebView2, janela e encerramento.
- `host/Updater/Updater.csproj` e `Program.cs` — atualização e rollback.
- `tools/package.ps1` e `tools/generate_sbom.py` — empacotamento portátil e SBOM.

### Arquivos novos recomendados

- `frontend/ui/formatters.js` — dinheiro, datas, placa e documentos.
- `frontend/ui/forms.js` — validação e serialização comum.
- `frontend/pages/dashboard.js`
- `frontend/pages/clients.js`
- `frontend/pages/mobility.js`
- `frontend/pages/catalog.js`
- `frontend/pages/commercial.js`
- `frontend/pages/finance.js`
- `src/ustracker/clients.py`
- `src/ustracker/mobility.py`
- `src/ustracker/catalog.py`
- `src/ustracker/commercial.py`
- `src/ustracker/finance.py`
- `src/ustracker/attachments.py`
- `tests/test_clients.py`, `test_mobility.py`, `test_catalog.py`, `test_commercial.py`, `test_finance.py`, `test_attachments.py` e testes Node correspondentes.

---

### Tarefa 0: Materializar a base de desenvolvimento e congelar o baseline

**Entrega:** repositório Git isolado, compilável e testável da 1.00.01.000, sem dados reais, com comparação reproduzível contra o pacote instalado.

**Entrada:** `C:\UStracker\.Arquivado\R2_source_20260915\UStracker`.

**Saída:** `C:\UStracker\.Arquivado\workspaces\ustracker_reestruturacao_20260928`.

- [ ] Confirmar que nenhum processo `UStracker`, `UStracker.Shell`, `UStracker.Updater`, `python` ou `pythonw` aponta para a árvore de trabalho.
- [ ] Copiar a fonte canônica para `WorkRoot`, excluindo `UserData`, `bin`, `obj`, `Dist`, `.venv`, `__pycache__` e caches de teste.
- [ ] Inicializar Git em `WorkRoot`, revisar `.gitignore`, criar o commit `chore: baseline 1.00.01.000` e a tag `baseline-1.00.01.000`. Não incluir bancos, credenciais, mídia operacional ou chaves privadas.
- [ ] Criar `tools/verify_baseline.ps1` para comparar SHA256 de `frontend/`, `src/ustracker/` e builds .NET com `C:\UStracker`, mapeando `src/ustracker` para `Runtime/Lib/site-packages/ustracker`.
- [ ] Registrar no relatório: ZIP fornecido `D7E6AE841C794D5704F9F4455B5D70EA144663AB8BD41FD2119C79B3033C025F`; 1.508 arquivos estáticos idênticos; 18 arquivos backend idênticos; 51 arquivos frontend idênticos; três executáveis idênticos.
- [ ] Executar os testes Python existentes com o runtime conhecido:

```powershell
$env:PYTHONPATH = "$PWD\src"
$env:USTRACKER_DEV_PLAINTEXT = '1'
& 'C:\UStracker\Runtime\python.exe' -m unittest discover -s tests -p 'test_r2_*.py' -v
```

  Resultado baseline esperado: 11 testes, 0 falhas. `ResourceWarning` de conexões de teste é dívida conhecida, não aprovação para criar novos vazamentos.

- [ ] Executar frontend e validações estáticas:

```powershell
node --test tests\r2_ui.test.mjs
node --check frontend\app.js
& 'C:\UStracker\Runtime\python.exe' -m compileall -q src\ustracker tests
```

  Resultado baseline esperado: 8 testes Node, 0 falhas; demais comandos com exit code 0.

- [ ] Compilar os três projetos sem restaurar pacotes, usando os assets já presentes:

```powershell
dotnet build host\Bootstrap\Bootstrap.csproj -c Release -p:Platform=x64 --no-restore --nologo
dotnet build host\Shell\Shell.csproj -c Release -p:Platform=x64 --no-restore --nologo
dotnet build host\Updater\Updater.csproj -c Release -p:Platform=x64 --no-restore --nologo
```

  Resultado baseline esperado: três builds com 0 erros. O aviso `NU1900` por indisponibilidade do índice de vulnerabilidades do NuGet é limitação de rede, não erro de compilação.

- [ ] Criar fixtures anônimas em diretório temporário representando clientes, frotas, veículos, assinaturas, cobranças, recebimentos, créditos, despesas e fiscal.
- [ ] Produzir um pacote baseline em `WorkRoot\Dist`; não instalar sobre `C:\UStracker`.
- [ ] Confirmar manualmente no pacote isolado: login, Produção/Teste de fixture, estação escritora, backup/restore, recovery, auditoria, busca, botão X e encerramento do backend.

**Ponto de parada 0:** não iniciar alterações se fonte, testes, builds ou comparação de hashes falharem. Não usar o ZIP fornecido como banco atual e não copiar `UserData` real para a árvore de trabalho.

### Tarefa 1: Criar a fundação visual e os formatadores globais

**Entrega:** shell fixo e estável, moeda/data consistentes e componentes reutilizáveis, sem alterar regras de negócio.

**Interfaces:** `frontend/ui/formatters.js` exporta `formatBRL(cents)`, `parseBRLInput(text)`, `formatDateBR(iso, withTime)`, `normalizePlate(text)` e `normalizeDocument(type, text)`; todas as páginas novas consomem essas funções.

- [ ] Escrever testes para formatação `R$ 0,00`, `R$ 1.234,56`, negativos, datas, data/hora e entradas monetárias brasileiras.
- [ ] Criar `formatters.js` e manter os centavos como inteiro no contrato interno.
- [ ] Criar componente de campo monetário textual, sem setas e com cursor/seleção estáveis.
- [ ] Ajustar a API ou o serializador para aceitar a representação brasileira sem perda de centavos.
- [ ] Tornar o cabeçalho superior `position: sticky`, acima do conteúdo, com logo UStracker à esquerda e Ajuda, nome do usuário, Sair e Encerrar à direita.
- [ ] Exibir no topo somente o nome do usuário e sua função, por exemplo `Carlos · Administrador`; mover o estado da estação para Sistema ou indicador técnico discreto.
- [ ] Manter o menu lateral rolável independentemente do cabeçalho.
- [ ] Aplicar bordas, foco, hover e sombras suaves usando os tokens existentes.
- [ ] Fazer o favicon usar `icons/default/brand/favicon.png` como fallback antes do branding personalizado.
- [ ] Incorporar `.ico` válido nos executáveis e definir o ícone da janela WebView2 no projeto .NET.
- [ ] Criar atalho idempotente na Área de Trabalho no primeiro início; atualizar o alvo se a pasta mudar e nunca duplicar atalhos.

**Testes:** unitários de formatadores; screenshot/smoke do shell; teste Windows do recurso `.ico`; teste de primeira e segunda inicialização do atalho.

**Ponto de parada 1:** homologar o shell e os formatos em uma cópia de Teste antes de tocar nos domínios.

### Tarefa 2: Evoluir Clientes e a Ficha do Cliente

**Entrega:** cadastro validado, empresas/documentos/contatos estruturados, foto, compras e exclusão lógica em lote.

**Interfaces:** `src/ustracker/clients.py` concentra documentos, empresas e arquivamento; `server.py` mantém `/api/v1/clients` e acrescenta recursos filhos `/clients/{cid}/documents` e `/clients/{cid}/companies`. A ficha continua sendo lida por `/clients/{cid}/profile`.

- [ ] Migrar para schema 4 com tabelas `client_documents` e `client_companies`, mantendo `clients.document`, `email`, `phone` e demais campos legados somente para leitura/compatibilidade durante a transição.
- [ ] Não converter `trade_name` automaticamente em empresa vinculada: hoje ele é o nome fantasia do próprio cliente. Clientes legados sem vínculo estruturado devem receber estado `NEEDS_REVIEW`, sem dados inventados.
- [ ] Definir tipos de documento `CPF`, `RG`, `CNH`; normalizar número; impedir duplicidade válida por tipo/número.
- [ ] Exigir nome, ao menos um documento e ao menos um contato entre e-mail/telefone para novos clientes e para clientes legados quando editados; registros legados continuam consultáveis até revisão.
- [ ] Permitir empresa opcional e múltiplas empresas dentro da ficha.
- [ ] Manter `POST/PATCH /clients` compatível e criar endpoints filhos para documentos e empresas.
- [ ] Transformar a tabela de Clientes em seleção múltipla, com uma única ação de linha `Abrir Ficha`.
- [ ] Limitar a tabela aos dados essenciais: Cliente, Empresa principal, Contato principal, Veículos, Valor Gerado, Status e Ação; aplicar quebra de texto coesa.
- [ ] Adicionar ação `Excluir selecionados`, confirmação com quantidade e arquivamento transacional.
- [ ] Bloquear arquivamento quando houver operação pendente incompatível; explicar quais clientes não foram arquivados.
- [ ] Expandir a ficha com cartões recolhíveis: Dados Básicos, Empresas, Documentos, Contatos, Foto, Mobilidade, Assinaturas/Arquivos e Compras.
- [ ] Reusar `/media/client/{id}` para a foto, com validação de JPEG/PNG/WebP, limites de tamanho e compressão operacional.
- [ ] Unificar Compras Diretas e Resumo Financeiro no cartão `Compras`.
- [ ] Exibir no resumo final `Quantidade de Veículos | Valor Gerado`, separando particular e total de frota apenas quando necessário.

**Testes:** matriz de obrigatoriedade; documento duplicado; cliente com vários contatos/empresas; exclusão em lote parcial/total; foto inválida; compatibilidade dos clientes existentes.

**Ponto de parada 2:** cadastrar, editar, consultar, fotografar e arquivar clientes no ambiente Teste; restaurar backup e repetir a consulta.

### Tarefa 3: Unificar Frotas e Veículos

**Entrega:** uma página `Frotas/Veículos` com abas Particulares e Frotas, fichas completas e transferência segura.

**Interfaces:** `src/ustracker/mobility.py` produz `create_transfer_case`, `complete_transfer_case` e `cancel_transfer_case`; `server.py` expõe `/api/v1/vehicle-transfer-cases` e preserva o endpoint legado de transferência durante a transição.

- [ ] Substituir os dois itens laterais por uma página única sem apagar as rotas antigas.
- [ ] Criar filtros por cliente, frota e placa, com Enter e botão Pesquisar.
- [ ] Exibir colunas `ID | Cliente | Frota(s) | Data Contratação | Data Revisão | Valor Total`.
- [ ] Definir a origem de Data Contratação, Data Revisão e Valor Total em consultas de domínio, sem cálculo duplicado no JavaScript.
- [ ] Migrar para schema 5 e adicionar `client_company_id` anulável nas frotas existentes. Novas frotas exigem uma `client_company`; frotas legadas sem vínculo permanecem operacionais com `NEEDS_REVIEW` até associação explícita.
- [ ] Aplicar limite configurável inicial de 100 veículos ativos por frota.
- [ ] Tratar veículo sem `fleet_id` como Particular.
- [ ] Reduzir os dados obrigatórios do veículo a Tipo, Marca, Série/Modelo, Ano e Placa; manter RENAVAM e demais campos como adicionais opcionais.
- [ ] Oferecer tipos Carro, Caminhão, Embarcação, Aeronave e `Novo tipo…`.
- [ ] Criar ficha da frota para editar grupo, adicionar veículos, anexar fotos e consultar totais/valores individuais.
- [ ] Reusar mídia para fotos de veículo e frota, com miniaturas compactadas.
- [ ] Criar `vehicle_transfer_cases` com estados `PENDING`, `COMPLETED`, `CANCELLED` e endpoints próprios para criar, concluir e cancelar casos.
- [ ] Preservar `POST /api/v1/vehicles/{vid}/transfer` durante uma versão de transição; documentar e testar sua delegação ao novo serviço sem mudar silenciosamente o contrato dos consumidores atuais.
- [ ] Enquanto pendente, mostrar aviso sem alterar a propriedade vigente; concluir em uma transação que fecha `ownerships` e cria a nova propriedade.

**Testes:** particular/frota; empresa obrigatória; limite 100/101; placa duplicada; ficha; transferência pendente/cancelada/concluída; conflito de revisão.

**Ponto de parada 3:** comparar quantidade e propriedade de todos os veículos antes/depois da migração e obter diferença zero fora dos casos executados.

### Tarefa 4: Reestruturar Planos/Produtos

**Entrega:** catálogo único, código automático, categoria controlada e custo detalhado.

**Interfaces:** `src/ustracker/catalog.py` produz `next_catalog_code`, `replace_cost_components` e `catalog_total_cost`; `services.py` continua sendo a fachada compatível usada pelas rotas `/api/v1/catalog`.

- [ ] Migrar para schema 6 e renomear a interface para `Planos/Produtos` sem renomear tabelas físicas desnecessariamente.
- [ ] Gerar códigos `PRD001`, `PRD002`… no backend, dentro da transação, sem colisão concorrente.
- [ ] Substituir Nome por `Descrição` e categoria livre por seleção `Avulsa` ou `Mensal`.
- [ ] Remover Tipo da interface e manter compatibilidade interna durante a migração.
- [ ] Criar `catalog_cost_components` com descrição opcional para o primeiro componente e obrigatória quando houver dois ou mais.
- [ ] Calcular `cost_cents` exclusivamente como soma dos componentes; não aceitar divergência enviada pelo navegador.
- [ ] Manter uma única tabela e uma ação Editar por linha.
- [ ] Preservar histórico de preços/custos em `catalog_prices`.

**Testes:** sequência de código; concorrência; categorias; um custo simples; múltiplos custos discriminados; soma; edição; histórico.

**Ponto de parada 4:** todos os itens antigos aparecem uma vez na tabela nova e mantêm preço/custo original.

### Tarefa 5: Criar o módulo Comercial

**Entrega:** Assinaturas, Compras Diretas e Créditos/Tempo Ativo em abas internas, apoiados pelo razão financeiro existente.

**Interfaces:** `src/ustracker/commercial.py` produz `create_coverage_period` e `coverage_status`; pagamentos e créditos monetários continuam pertencendo a `services.py`, sem reutilizar `credits` para representar tempo.

- [ ] Migrar para schema 7 para os períodos de cobertura e criar abas internas com URL/estado navegável, sem duplicar funções de carregamento.
- [ ] Montar a tabela de Assinaturas: `ID | Cliente | Plano | Veículo(s) | Valor Total | Tempo Ativo`.
- [ ] Calcular Valor Total no backend pelos itens da assinatura.
- [ ] Exibir veículos particulares individualmente e frotas como quantidade/resumo; detalhes individuais ficam na ficha da frota.
- [ ] Abrir Compras Diretas por botão da linha da assinatura/cliente e listar somente produtos `Avulsa`.
- [ ] Registrar data de contratação, valor efetivo e meio de pagamento.
- [ ] Ocultar Cobranças do menu; conservar geração, ajustes, alocações e status como infraestrutura interna.
- [ ] Separar crédito monetário existente de cobertura temporal pré-paga.
- [ ] Criar períodos de cobertura com início, término, assinatura, pagamento de origem, quantidade de ciclos e valor aplicado.
- [ ] Para pagamento em 10/09 de uma mensalidade, calcular cobertura até 10/10; para 12 ciclos, avançar 12 meses de calendário.
- [ ] Exibir cronômetro como diferença calculada entre agora e `coverage_end_at`; não manter processo em segundo plano gravando contagem.

**Testes:** assinatura individual/frota; compra avulsa; total; pagamentos de 1 e 12 ciclos; virada de mês/ano; cancelamento/estorno; cobertura expirada.

**Ponto de parada 5:** reconciliar total de assinaturas, compras, cobranças, pagamentos e créditos com os relatórios da versão anterior.

### Tarefa 6: Criar o módulo Financeiro

**Entrega:** abas Recebimentos, Despesas e Fiscal, com lançamentos fiscais refletidos corretamente em despesas.

**Interfaces:** `src/ustracker/finance.py` produz `create_fiscal_with_expense` como única operação transacional para obrigação fiscal com valor; as rotas antigas continuam delegando aos serviços compatíveis.

- [ ] Reagrupar as páginas atuais sem alterar inicialmente seus endpoints.
- [ ] Manter recebimentos, alocações, estornos e créditos com o mesmo livro-razão.
- [ ] Melhorar Despesas para obrigações mensais, anuais ou pontuais, com recorrência explícita.
- [ ] Tratar Fiscal como controle administrativo de licenças, termos, taxas e obrigações; continuar sem emissão fiscal oficial.
- [ ] Ao gerar valor fiscal, criar/vincular uma despesa em uma única transação idempotente.
- [ ] Impedir dupla contabilização quando uma obrigação fiscal já possuir `expense_id`.
- [ ] Aplicar moeda e data padronizadas em todas as três abas.

**Testes:** fiscal com/sem valor; criação única da despesa; recorrência mensal/anual; recebimento/estorno; desembolso/estorno; reconciliação do dashboard.

**Ponto de parada 6:** resultado financeiro antes e depois da reorganização deve ser idêntico para a mesma data-base.

### Tarefa 7: Reorganizar a Visão Geral

**Entrega:** indicadores operacionais no topo, busca clara e tabela compacta de clientes com lucratividade/atividade.

**Interfaces:** `/api/v1/dashboard` continua sendo o read model principal e passa a devolver o resumo por cliente; `/api/v1/search` permanece busca global, separada do filtro local da página.

- [ ] Posicionar Indicadores Operacionais acima da busca e da tabela de Clientes.
- [ ] Manter a barra global no cabeçalho apenas para busca global; criar busca contextual da Visão Geral abaixo dos indicadores.
- [ ] Aceitar Enter e clique em Pesquisar; disponibilizar Limpar.
- [ ] Incluir por cliente: nome, quantidade de veículos, assinaturas/atividade, compras e valor gerado.
- [ ] Definir valor gerado no backend a partir de recebimentos realizados e compras pagas, evitando somar receita prevista como realizada.
- [ ] Ajustar tabela para `table-layout: fixed`, larguras por coluna, `overflow-wrap`, duas linhas quando necessário e ações compactas.
- [ ] Manter o conteúdo dentro da largura do desktop; rolagem horizontal será fallback apenas em resoluções mínimas.
- [ ] Preparar breakpoints sem tentar concluir agora o layout mobile.

**Testes:** busca com acentos; botão/Enter; nomes longos; 0/1/100 veículos; valores grandes; resolução desktop mínima definida na homologação.

**Ponto de parada 7:** homologação visual com conjunto pequeno, grande e nomes longos, sem corte de ações nem desalinhamento.

### Tarefa 8: Comprovantes assinados e anexos

**Entrega:** comprovantes de assinatura do cliente em imagem, PDF ou link, distintos das assinaturas comerciais, com armazenamento local substituível por Google Drive.

**Interfaces:** `src/ustracker/attachments.py` define `AttachmentStore`, `LocalAttachmentStore.put/open/delete` e os serviços de metadados; `DriveAttachmentStore` não é implementado nem habilitado nesta versão.

- [ ] Migrar para schema 8 e criar `attachments` com metadados, tipo de entidade, hash, MIME, tamanho, origem local/link e timestamps.
- [ ] Definir interface de storage com implementação `LocalAttachmentStore`; deixar `DriveAttachmentStore` desativada até a integração futura.
- [ ] Validar extensão e assinatura real do arquivo; limitar tamanho; bloquear execução de conteúdo.
- [ ] Criptografar arquivos locais com chave derivada já usada pelo ambiente.
- [ ] Vincular anexos de assinatura ao cliente, assinatura e, quando aplicável, veículo/frota.
- [ ] Incluir anexos em backup, recovery e restauração.

**Testes:** JPG/PNG/WebP/PDF/link; MIME falso; duplicado por hash; download; backup/restore; ausência de arquivo.

**Ponto de parada 8:** restaurar um backup em instalação limpa e abrir todos os anexos de amostra.

### Tarefa 9: Migração, compatibilidade e remoção controlada do menu antigo

**Entrega:** schema final migrado, dados reconciliados e nenhum link antigo quebrado.

**Interfaces:** `db.py` executa migrações 3→4→5→6→7→8 em ordem; `tools/verify_migration.py` gera contagens e totais antes/depois sem registrar dados pessoais.

- [ ] Implementar migrações sequenciais e reexecutáveis, sem `DROP` na primeira versão.
- [ ] Criar script de inspeção que conte e reconcilie registros antes/depois.
- [ ] Manter aliases de rotas antigas por uma versão de transição.
- [ ] Atualizar busca, relatórios, projeção pública, backup, recovery, auditoria e manual.
- [ ] Registrar toda migração e falha sem dados sensíveis.
- [ ] Testar upgrade a partir de cópias Production e Teste, downgrade por restore e reexecução após interrupção.

**Ponto de parada 9:** só considerar a migração aprovada com reconciliação completa e recuperação comprovada.

### Tarefa 10: Empacotamento e homologação Windows

**Entrega:** pacote portátil Windows da nova versão, com SHA256 e SBOM, homologado sem substituir automaticamente a instalação ativa.

**Interfaces:** `tools/package.ps1 -RepoRoot <WorkRoot> -OutDir <WorkRoot>\Dist` é o único caminho aceito para criar o pacote final; a instalação ativa é alterada somente por operação separada e autorizada.

- [ ] Compilar host, shell e updater com ícones incorporados.
- [ ] Definir uma versão maior que `1.00.01.000` somente após autorização de release; atualizar de forma consistente `pyproject.toml`, `VERSION.json` e `current.json`.
- [ ] Gerar SBOM, hashes e pacote de atualização usando `tools/package.ps1`.
- [ ] Instalar em pasta limpa e atualizar uma instalação 1.00.01.000 existente.
- [ ] Validar Windows 10 x64 físico: atalho, ícone, WebView2, login, shutdown e updater/rollback. Validar também na versão de Windows realmente suportada pelo usuário se for diferente.
- [ ] Rodar suíte unitária, API, integração, migração, frontend smoke e restauração.
- [ ] Atualizar Manual do Usuário, Relatório de Entrega e matriz de aceite.

**Ponto de parada 10:** release somente após aceite funcional, visual, financeiro e de recuperação. Assinatura de código fica fora desta entrega até existir certificado; o SHA256 não deve ser descrito como assinatura digital.

---

## Ordem recomendada de execução

1. Baseline e fonte reproduzível.
2. Fundação visual e formatos.
3. Clientes.
4. Frotas/Veículos.
5. Planos/Produtos.
6. Comercial.
7. Financeiro.
8. Visão Geral.
9. Anexos.
10. Migração final, documentação e pacote Windows.

Essa ordem evita construir dashboards e resumos sobre modelos ainda instáveis. Cada fase entrega software executável e pode ser aceita ou revertida isoladamente.

## Critérios de aceite finais

- Menu e cabeçalho correspondem à organização consolidada.
- Nome/função do usuário substituem `PRODUÇÃO · ESCRITORA` na área principal.
- Logo, favicon, ícone da janela e atalho funcionam em instalação limpa.
- Todos os valores aparecem em real brasileiro e não possuem setas numéricas.
- Cadastro de cliente cumpre nome + documento + contato.
- Cliente suporta empresas, foto, veículos/frotas, assinaturas, anexos e compras.
- Frotas/Veículos operam em uma página, com limite e transferência pendente segura.
- Produtos recebem código automático e custo composto auditável.
- Comercial e Financeiro usam abas sem duplicar ou perder lançamentos.
- Cobranças deixam o menu sem quebrar o razão interno.
- Tempo de assinatura pré-paga é calculado corretamente.
- Dashboard mostra atividade, veículos e valor gerado por cliente.
- Upgrade preserva 100% dos registros e o restore retorna ao estado anterior.

## Estratégia de commits

- Um commit por migração ou comportamento testável.
- Nunca misturar alteração de schema, redesign amplo e mudança financeira no mesmo commit.
- Usar mensagens como `feat(clients): add structured documents`, `feat(mobility): add pending transfers` e `refactor(nav): compose commercial tabs`.
- Ao final de cada ponto de parada, criar tag interna de homologação e guardar o relatório de testes.

## Estado real para execução

Não existe bloqueio de fonte nesta máquina: `C:\UStracker\.Arquivado\R2_source_20260915\UStracker` contém o código correspondente e os comandos baseline foram verificados em 28/09/2026:

- Python `unittest`: 11 testes, 0 falhas.
- Node: 8 testes, 0 falhas.
- `node --check` e `compileall`: exit code 0.
- Bootstrap, Shell e Updater: três builds, 0 erros com `--no-restore`.
- Comparação do pacote: todos os 1.508 arquivos estáticos coincidem com a instalação ativa.

O único bloqueio para execução por uma IA externa é de transferência: o ZIP fornecido é binário, contém dados reais e não leva a fonte. Antes de enviá-lo, deve ser produzido um pacote de handoff separado contendo a fonte canônica, este plano e um relatório de hashes, excluindo integralmente `UserData`, caches e artefatos de build. A IA externa deve interromper o trabalho se não receber esse pacote-fonte.
