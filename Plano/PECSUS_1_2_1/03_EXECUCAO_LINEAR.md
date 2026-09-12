# UStracker V1 Implementation Plan — PECSUS 1.2.1

> IA executora: usar fluxo disciplinado por tarefa; executar inline. Se Superpowers estiver disponível, usar executing-plans. Este arquivo é gerado de TAREFAS.json; não editar diretamente.

**Goal:** criar e homologar UStracker 1.00.00.000 com evidência real.

**Architecture:** monólito modular local Python/FastAPI/SQLCipher; Host WPF net48/WebView2; PUBLIC separado; uma escritora participante por dataset.

**Tech Stack:** CPython 3.13.15 x64 embeddable, sqlcipher3 0.6.2, WPF .NET Framework 4.8 x64, Microsoft.Web.WebView2 1.0.4191.47, HTML/CSS/ES modules locais.

**Spec:** 01_ESPECIFICACAO.md + 02_CONTRATOS.md + MATRIZ_ESCOPO_HISTORICO.csv.

## Global Constraints

Windows10 formal; Win11 compatibilidade adicional. Gates obrigatórios não são pulados. T01 antecede T02. PUBLIC nunca recebe dados privados. Dinheiro int cents/Decimal. Integrações futuras desativadas. Não executar scripts legados. Plano original imutável; Estado/ e Evidence/ pertencem à engenharia.


---

### T01: Fundação, dependências e spike nativo G1

**Depends on:** G0_DOCUMENTAL

**Requirements:** R01, R17, R18, R19, R24, R30, R33, R35

**Goal:** Fechar G1 com raiz portátil, runtime Python, SQLCipher real, Host WPF/WebView2 e handshake local antes de qualquer domínio.

**Files:**
- Create/modify: `pyproject.toml`
- Create/modify: `requirements.in`
- Create/modify: `requirements.lock`
- Create/modify: `package.json`
- Create/modify: `package-lock.json`
- Create/modify: `Directory.Build.props`
- Create/modify: `Directory.Packages.props`
- Create/modify: `src/ustracker/contracts.py`
- Create/modify: `src/ustracker/core/paths.py`
- Create/modify: `src/ustracker/security/key_provider.py`
- Create/modify: `src/ustracker/__main__.py`
- Create/modify: `host/Bootstrap/Bootstrap.csproj`
- Create/modify: `host/Shell/Shell.csproj`
- Create/modify: `host/Updater/Updater.csproj`
- Create/modify: `host/Shared/RootPaths.cs`
- Create/modify: `host/Shared/PipeProtocol.cs`
- Create/modify: `tools/build.ps1`
- Create/modify: `tools/verify.py`
- Create/modify: `docs/DEPENDENCIES.md`
- Create/modify: `tests/unit/test_paths_version.py`
- Create/modify: `tests/native/test_foundation_smoke.py`
- Create/modify: `src/ustracker_verification/__init__.py`
- Create/modify: `src/ustracker_verification/__main__.py`

**Interfaces:** Produz RootPaths.resolve, VERSION/current parsing, DatabaseKeyProvider protocol, runtime manifest, host skeleton e verify harness.

- [ ] **Step 1:** Criar raiz de engenharia separada da documentação e de qualquer pasta sincronizada. Registrar hashes do pacote PECSUS 1.2.1; ler FONTES_E_DECISOES.md. Histórico arquivado é consulta opcional, não dependência de T01; nenhum script antigo é executado.

- [ ] **Step 2:** Fixar CPython 3.13.15 x64 embeddable e exigir SHA-256 d1f04d990aee1253d8569e8e5104e30fa9f5fa830899f14843448872d936a2cf do pacote oficial. Fixar sqlcipher3 0.6.2 cp313 win_amd64 e exigir SHA-256 9dc959ff792228c6df836cfd3667c713ae13e6e18dc2905c9d5666558606e832 antes de instalar no Runtime.

- [ ] **Step 3:** Host V1 deve targetar .NET Framework 4.8 x64, WPF e Microsoft.Web.WebView2 1.0.4191.47. Não adicionar .NET 10 ao cliente. Build usa toolchain de engenharia; cliente usa componentes do SO + WebView2 Runtime.

- [ ] **Step 4:** Definir DatabaseKeyProvider.get_key(environment,dataset_id,purpose)->bytes em security/key_provider.py. Criar StaticTestKeyProvider somente em tests/support; T03 não pode importar Vault.

- [ ] **Step 5:** Criar Bootstrap/Shell/Updater separados. Bootstrap resolve root/current, valida release e inicia Runtime\pythonw.exe -m ustracker; backend mantém bind 127.0.0.1:0 e anuncia porta reservada, nonce e identidade por named pipe com ACL do usuário atual. Seguir seção 12 de 02_CONTRATOS.md.

- [ ] **Step 6:** Criar endpoint /api/v1/health mínimo sem DB privado. Shell aguarda handshake, abre WebView2 e fecha de modo cooperativo. G1 deve rodar em Windows antes de T02.

- [ ] **Step 7:** Implementar tools/verify.py com --task, --integration, --native, --evidence-dir, --explain e --profile win10_22h2|windows11. --task executa TODOS os casos obrigatórios da tarefa, inclusive nativos, mesmo sem --native; perfil incompatível marca BLOCKED e exit_code não zero. --explain só descreve, sem PASS. Gates T01/T16/T18 exigem win10_22h2; casos win11 adicionais geram relatório separado.

- [ ] **Step 8:** Executar pytest tests/unit/test_paths_version.py -q e python tools/verify.py --task T01 --native --profile win10_22h2 --evidence-dir Evidence. Qualquer caso obrigatório não PASS bloqueia T02. Executar compatibilidade Win11 quando disponível e registrar PASS/FAIL/BLOCKED separadamente, sem invalidar ou inflar a prova formal.

- [ ] **Step 9:** Fechar composição do Runtime embeddable, DLLs nativas e trust store conforme seção 15 de 02_CONTRATOS.md. Registrar versão/hash de TODAS dependências transitivas resolvidas em requirements.lock e pacote nativo lockado; nenhuma dependência latest/flutuante. Não gerar a chave privada produtiva dentro do runtime.


**Acceptance cases:** T01-C01, T01-C02, T01-C03, T01-C04, T01-C05, T01-C06, T01-C07, T01-C08, T01-C09

**Gate proof:** Evidence/T01 deve provar cada caso obrigatório listado em acceptance_cases, com command/stdout/stderr/exit_code/UTC/environment/build/hashes. Casos adicionais de compatibilidade têm relatório separado.

**Required command pattern:**
```powershell
& .\.venv\Scripts\python.exe tools\verify.py --task T01 --native --profile win10_22h2 --evidence-dir Evidence
if ($LASTEXITCODE -ne 0) { throw 'T01 gate failed' }
```

**Checkpoint:** atualizar Estado/PONTO_DE_PARADA.json e Evidence/ na engenharia, mantendo semente e catálogo do plano imutáveis. Invalidar evidências afetadas por mudança; só avançar com casos obrigatórios PASS.


---

### T02: Dinheiro, datas e invariantes de cálculo

**Depends on:** T01

**Requirements:** R13

**Goal:** Eliminar float monetário e fechar cálculo de centavos, vencimento, competência, timezone e políticas versionadas.

**Files:**
- Create/modify: `src/ustracker/core/money.py`
- Create/modify: `src/ustracker/core/dates.py`
- Create/modify: `src/ustracker/core/policies.py`
- Create/modify: `tests/unit/test_money_dates.py`

**Interfaces:** Produz Money helpers, due_date, Clock/TimezonePolicy e RoundingPolicy consumidos por todo domínio.

- [ ] **Step 1:** Escrever testes parametrizados primeiro para parsing canônico/UI, NaN/Infinity, escalas, splits, empates, vencimento 29/30/31, leap year e timezone.

- [ ] **Step 2:** Implementar parse_money_api somente decimal com ponto e <=2 casas; parse_money_ptbr aceita 1.234,56 e rejeita ambíguos; persistência sempre int cents.

- [ ] **Step 3:** Implementar split_cents(total,weights) determinístico com soma exata e distribuição de resto estável; policy_id ROUND_V1_HALF_EVEN.

- [ ] **Step 4:** Implementar due_date com calendar.monthrange; competência YYYY-MM e datas civis não são convertidas para UTC; timestamps de evento são UTC e UI exibe America/Sao_Paulo.

- [ ] **Step 5:** Rodar pytest tests/unit/test_money_dates.py -q e tools/verify.py --task T02; revisar funções públicas e exceções antes de fechar gate.


**Acceptance cases:** T02-C01, T02-C02, T02-C03, T02-C04, T02-C05

**Gate proof:** Evidence/T02 deve provar cada caso obrigatório listado em acceptance_cases, com command/stdout/stderr/exit_code/UTC/environment/build/hashes. Casos adicionais de compatibilidade têm relatório separado.

**Required command pattern:**
```powershell
& .\.venv\Scripts\python.exe tools\verify.py --task T02 --evidence-dir Evidence
if ($LASTEXITCODE -ne 0) { throw 'T02 gate failed' }
```

**Checkpoint:** atualizar Estado/PONTO_DE_PARADA.json e Evidence/ na engenharia, mantendo semente e catálogo do plano imutáveis. Invalidar evidências afetadas por mudança; só avançar com casos obrigatórios PASS.


---

### T03: Persistência cifrada, migrações e unidade de trabalho

**Depends on:** T02

**Requirements:** R17, R21, R34

**Goal:** Implementar SQLCipher, schema canônico, idempotência, revisão, journal DB+arquivo e auditoria sem depender da T04.

**Files:**
- Create/modify: `src/ustracker/storage/db.py`
- Create/modify: `src/ustracker/storage/uow.py`
- Create/modify: `src/ustracker/storage/repositories.py`
- Create/modify: `src/ustracker/storage/migrations/0001.sql`
- Create/modify: `src/ustracker/storage/file_journal.py`
- Create/modify: `src/ustracker/core/audit.py`
- Create/modify: `tests/integration/test_storage.py`
- Create/modify: `tests/support/keys.py`

**Interfaces:** Consome DatabaseKeyProvider protocol via StorageFactory; produz Database, UnitOfWork e repos; T04 posteriormente injeta VaultKeyProvider.

- [ ] **Step 1:** Escrever migration 0001 integral a partir de 02_CONTRATOS.md, incluindo constraints/FKs/unique/indexes. Proibido copiar banco ASCALPI.

- [ ] **Step 2:** Nos testes, injetar StaticTestKeyProvider. Production code recebe DatabaseKeyProvider; nunca importar security.vault nem senha em db.py.

- [ ] **Step 3:** Abrir SQLCipher com PRAGMA key, cipher_version assert não vazio, foreign_keys=ON, synchronous=FULL, journal_mode=DELETE e busy_timeout=5000; schema mais novo que aplicação é bloqueante.

- [ ] **Step 4:** UnitOfWork usa lock local por dataset + BEGIN IMMEDIATE. operations tem chave única environment,dataset_id,operation_id e hash canônico de method/route/actor/payload.

- [ ] **Step 5:** File journal cifra staging e usa estados PREPARED/COMMITTED/FINALIZED/ROLLED_BACK/QUARANTINED; recovery nunca apaga path fora de root validada.

- [ ] **Step 6:** Audit event é gravado na mesma transação, com before_json/after_json sanitizados, previous_hash/event_hash. Falha de audit aborta a mutação.

- [ ] **Step 7:** Rodar pytest tests/integration/test_storage.py -q e tools/verify.py --task T03; abrir DB também com sqlite3 comum para provar falha.

- [ ] **Step 8:** Aplicar ordem autorização→idempotência→revision/UoW conforme seção16 de 02_CONTRATOS.md; operations.response_json guarda MutationResult sem PII para não recriar dados anonimizados em replay.


**Acceptance cases:** T03-C01, T03-C02, T03-C03, T03-C04, T03-C05, T03-C06, T03-C07

**Gate proof:** Evidence/T03 deve provar cada caso obrigatório listado em acceptance_cases, com command/stdout/stderr/exit_code/UTC/environment/build/hashes. Casos adicionais de compatibilidade têm relatório separado.

**Required command pattern:**
```powershell
& .\.venv\Scripts\python.exe tools\verify.py --task T03 --evidence-dir Evidence
if ($LASTEXITCODE -ne 0) { throw 'T03 gate failed' }
```

**Checkpoint:** atualizar Estado/PONTO_DE_PARADA.json e Evidence/ na engenharia, mantendo semente e catálogo do plano imutáveis. Invalidar evidências afetadas por mudança; só avançar com casos obrigatórios PASS.


---

### T04: Três admins, AuthStore, VaultStore e sessão

**Depends on:** T03

**Requirements:** R02, R03, R04, R17, R25

**Goal:** Fechar bootstrap de três slots, VRK/envelopes, chaves Production/Test, reset por enrollment e sessões revogáveis.

**Files:**
- Create/modify: `src/ustracker/security/auth.py`
- Create/modify: `src/ustracker/security/vault.py`
- Create/modify: `src/ustracker/security/sessions.py`
- Create/modify: `src/ustracker/security/bootstrap.py`
- Create/modify: `src/ustracker/security/key_provider.py`
- Create/modify: `tests/integration/test_auth.py`
- Create/modify: `host/Shell/MainWindow.xaml.cs`
- Create/modify: `host/Shell/SessionLifecycle.cs`
- Create/modify: `tests/native/test_shell_session.py`

**Interfaces:** Produz AuthService, VaultService, VaultKeyProvider e SessionService. VaultKeyProvider implementa o protocolo definido em T01.

- [ ] **Step 1:** AuthStore: três slots fixos. Password verifier/KEK por scrypt N=131072,r=8,p=1, salt aleatório 16+ bytes; benchmark T04 pode registrar custo, mas não reduzir sem nova revisão de segurança.

- [ ] **Step 2:** Gerar VRK aleatória 32 bytes. Cada slot ENROLLED mantém envelope AES-256-GCM da mesma VRK sob KEK da senha. VaultStore mantém chaves production/test e media keyring cifradas pela VRK.

- [ ] **Step 3:** Bootstrap/enrollment seguem seção 12 de 02_CONTRATOS.md: wizard com capacidade via pipe, setup atômico retomável, tickets one-use 15 min, hash-only; produção requer três slots ENROLLED. Login/setup não dependem de ADMIN ou do DB operacional fechado.

- [ ] **Step 4:** Reset de outro admin: exigir admin autenticado+motivo; revogar sessões; remover envelope daquele slot somente se outro envelope/recovery utilizável existir; voltar PENDING_ENROLLMENT; emitir ticket. Não aceitar temp_password administrativamente.

- [ ] **Step 5:** Sessão token256bit em memória; idle60min/absolute12h; cookie e vínculo shell conforme seção 12. Polling/heartbeat não atualiza last_human_activity. Password change revoga sessões do slot e rewrap VRK. Auth mutations auditadas e atômicas no AuthStore, com KDF/KEK separados e throttle.

- [ ] **Step 6:** production/test usam keys distintas sob VRK. Reset Test gera novas keys Test e base vazia; AuthStore/Production não mudam.

- [ ] **Step 7:** X/window detach ou perda de heartbeat/pipe revoga sessão. Última sessão fecha DBs/keys após jobs privados checkpointarem em WAITING. Nova sessão reautoriza retomada; nenhum job privado continua com segredo indefinidamente após logout.

- [ ] **Step 8:** Rodar pytest tests/integration/test_auth.py -q e tools/verify.py --task T04; pelo menos KDF/envelope/session test real em Windows.


**Acceptance cases:** T04-C01, T04-C02, T04-C03, T04-C04, T04-C05, T04-C06, T04-C07, T04-C08, T04-C09, T04-C10

**Gate proof:** Evidence/T04 deve provar cada caso obrigatório listado em acceptance_cases, com command/stdout/stderr/exit_code/UTC/environment/build/hashes. Casos adicionais de compatibilidade têm relatório separado.

**Required command pattern:**
```powershell
& .\.venv\Scripts\python.exe tools\verify.py --task T04 --evidence-dir Evidence
if ($LASTEXITCODE -ne 0) { throw 'T04 gate failed' }
```

**Checkpoint:** atualizar Estado/PONTO_DE_PARADA.json e Evidence/ na engenharia, mantendo semente e catálogo do plano imutáveis. Invalidar evidências afetadas por mudança; só avançar com casos obrigatórios PASS.


---

### T05: API segura, projeção pública e lifecycle básico

**Depends on:** T04

**Requirements:** R02, R04, R19, R29, R34

**Goal:** Criar API loopback com fronteira PUBLIC/ADMIN, CSRF/Origin e projeção pública independente do DB privado.

**Files:**
- Create/modify: `src/ustracker/api/app.py`
- Create/modify: `src/ustracker/api/dependencies.py`
- Create/modify: `src/ustracker/api/errors.py`
- Create/modify: `src/ustracker/api/routers/auth.py`
- Create/modify: `src/ustracker/api/routers/public.py`
- Create/modify: `src/ustracker/core/lifecycle.py`
- Create/modify: `src/ustracker/public_projection/service.py`
- Create/modify: `tests/integration/test_api_security.py`

**Interfaces:** Consome Auth/Vault/Storage/Lifecycle; produz /api/v1, Error, public projection e shutdown/drain.

- [ ] **Step 1:** Factory create_app(settings,services); Uvicorn um worker, 127.0.0.1, socket alocado pelo próprio backend e anunciado via pipe; sem reload/docs públicas no pacote final.

- [ ] **Step 2:** GET /auth/csrf gera pré-sessão; POST login exige token+Host/Origin. Todas rotas privadas passam require_admin e environment da sessão.

- [ ] **Step 3:** Gerar UserData/Public/production/view.json e Public/Assets com DTO allowlist. public_dirty é persistido antes de commit de publicação/revogação; enquanto dirty, PUBLIC retorna503.

- [ ] **Step 4:** PUBLIC nunca abre SQLCipher; conteúdo privado não é enviado para DOM/cache para depois borrar. IDs operacionais, placas, contatos, fotos e finanças não entram na projeção.

- [ ] **Step 5:** Lifecycle estados RUNNING/DRAINING/RECOVERY_REQUIRED/MAINTENANCE. Shutdown bloqueia writes, aguarda checkpoints, flush journals, fecha DBs e sinaliza Host.

- [ ] **Step 6:** Rodar teste parametrizado sobre registry/OpenAPI para exigir access class em toda rota e tools/verify.py --task T05.

- [ ] **Step 7:** Aplicar tabela de exceções auth/setup da seção 12 e capacidades de Shell. Persistir public_dirty fora do DB privado antes do commit, com fail-closed durante crash/restore; reabrir somente após rebuild seguro. Verificar CSRF/Host/Origin inclusive pré-login.


**Acceptance cases:** T05-C01, T05-C02, T05-C03, T05-C04, T05-C05, T05-C06

**Gate proof:** Evidence/T05 deve provar cada caso obrigatório listado em acceptance_cases, com command/stdout/stderr/exit_code/UTC/environment/build/hashes. Casos adicionais de compatibilidade têm relatório separado.

**Required command pattern:**
```powershell
& .\.venv\Scripts\python.exe tools\verify.py --task T05 --evidence-dir Evidence
if ($LASTEXITCODE -ne 0) { throw 'T05 gate failed' }
```

**Checkpoint:** atualizar Estado/PONTO_DE_PARADA.json e Evidence/ na engenharia, mantendo semente e catálogo do plano imutáveis. Invalidar evidências afetadas por mudança; só avançar com casos obrigatórios PASS.


---

### T06: Clientes, veículos, frotas e propriedade

**Depends on:** T05

**Requirements:** R05, R06

**Goal:** Implementar cadastros completos históricos sem duplicar dados contratuais dentro do veículo.

**Files:**
- Create/modify: `src/ustracker/clients/service.py`
- Create/modify: `src/ustracker/vehicles/service.py`
- Create/modify: `src/ustracker/fleets/service.py`
- Create/modify: `src/ustracker/api/routers/clients.py`
- Create/modify: `src/ustracker/api/routers/vehicles.py`
- Create/modify: `src/ustracker/api/routers/fleets.py`
- Create/modify: `tests/integration/test_registry.py`

**Interfaces:** Produz ClientService, VehicleService, FleetService e ownership history conforme DTOs canônicos.

- [ ] **Step 1:** Implementar clients com legal_name obrigatório, trade_name/public_name/document/contacts/address/notes/status; normalized fields para busca, sem destruir valor original.

- [ ] **Step 2:** Implementar vehicles com plate, type, renavam opcional, tracker refs/serial, installed_on, tracking_status e notes; placa única entre veículos não arquivados.

- [ ] **Step 3:** Implementar fleets por cliente/sector_or_unit e ownerships sem sobreposição; transfer exige effective_on e valida vínculo de assinatura.

- [ ] **Step 4:** Plano/valor mensal são derivados de assinatura, não colunas do veículo. Cobranças antigas nunca mudam ao transferir ownership.

- [ ] **Step 5:** Implementar create/get/list/update/archive/transfer com revision/Idempotency-Key e audit before/after.

- [ ] **Step 6:** Busca administrativa por campos R05/R06; PUBLIC só usa public projection.

- [ ] **Step 7:** Rodar pytest tests/integration/test_registry.py -q e tools/verify.py --task T06.

- [ ] **Step 8:** Usar nomes de Address e regra phones[0] principal conforme contratos; archived separado de ClientStatus. Ownership/fleet são validados por data; congelar dimensões financeiras nas emissões antes de transferências.


**Acceptance cases:** T06-C01, T06-C02, T06-C03, T06-C04, T06-C05, T06-C06, T06-C07, T06-C08

**Gate proof:** Evidence/T06 deve provar cada caso obrigatório listado em acceptance_cases, com command/stdout/stderr/exit_code/UTC/environment/build/hashes. Casos adicionais de compatibilidade têm relatório separado.

**Required command pattern:**
```powershell
& .\.venv\Scripts\python.exe tools\verify.py --task T06 --evidence-dir Evidence
if ($LASTEXITCODE -ne 0) { throw 'T06 gate failed' }
```

**Checkpoint:** atualizar Estado/PONTO_DE_PARADA.json e Evidence/ na engenharia, mantendo semente e catálogo do plano imutáveis. Invalidar evidências afetadas por mudança; só avançar com casos obrigatórios PASS.


---

### T07: Catálogo, assinaturas, competências e ajustes de cobrança

**Depends on:** T06

**Requirements:** R07, R08, R09

**Goal:** Preservar catálogo completo, contrato versionado, periodicidade e geração idempotente com ajustes manuais auditáveis.

**Files:**
- Create/modify: `src/ustracker/catalog/service.py`
- Create/modify: `src/ustracker/subscriptions/service.py`
- Create/modify: `src/ustracker/charges/service.py`
- Create/modify: `src/ustracker/api/routers/catalog.py`
- Create/modify: `src/ustracker/api/routers/subscriptions.py`
- Create/modify: `src/ustracker/api/routers/charges.py`
- Create/modify: `tests/integration/test_contracts_charges.py`

**Interfaces:** Produz CatalogService, SubscriptionService, ChargeService e financial status derivado.

- [ ] **Step 1:** Catalog: code unique, name, description, category, kind PLAN/ITEM, billing_interval_months, price/cost history, notes, public, active.

- [ ] **Step 2:** Subscription: signed_on,start_on,end_on,due_day,billing_interval_months,renewal_mode,lifecycle_status e versions effective_month; itens congelam descrição/quantidade/preço/vehicle.

- [ ] **Step 3:** AWAITING_PAYMENT/OVERDUE não são status contratuais persistidos; derivar de saldo/due_on/default_grace_days. Nenhuma suspensão automática de rastreamento.

- [ ] **Step 4:** Gerar charge UNIQUE subscription_id/competence; respeitar intervalo/pause/cancel/end; mês inicial integral salvo ajuste manual.

- [ ] **Step 5:** Charge adjustments tipados DISCOUNT/SURCHARGE/PENALTY/INTEREST/OTHER e reschedule_due_date exigem reason, revision, operation_id; não calcular taxa legal automaticamente.

- [ ] **Step 6:** VOID só sem recebimento líquido; cobrança com pagamento exige reversões antes.

- [ ] **Step 7:** Rodar pytest tests/integration/test_contracts_charges.py -q e tools/verify.py --task T07.

- [ ] **Step 8:** Implementar regras fechadas de renovação, itens únicos, intervalos e versionamento completo da seção 13. Gerar categorias do catálogo em domínio separado das despesas. Ajuste nunca reduz net abaixo de recebimento líquido; 409 atômico.


**Acceptance cases:** T07-C01, T07-C02, T07-C03, T07-C04, T07-C05, T07-C06, T07-C07, T07-C08, T07-C09, T07-C10

**Gate proof:** Evidence/T07 deve provar cada caso obrigatório listado em acceptance_cases, com command/stdout/stderr/exit_code/UTC/environment/build/hashes. Casos adicionais de compatibilidade têm relatório separado.

**Required command pattern:**
```powershell
& .\.venv\Scripts\python.exe tools\verify.py --task T07 --evidence-dir Evidence
if ($LASTEXITCODE -ne 0) { throw 'T07 gate failed' }
```

**Checkpoint:** atualizar Estado/PONTO_DE_PARADA.json e Evidence/ na engenharia, mantendo semente e catálogo do plano imutáveis. Invalidar evidências afetadas por mudança; só avançar com casos obrigatórios PASS.


---

### T08: Recebimentos, créditos, alocação e estorno

**Depends on:** T07

**Requirements:** R09, R13, R21

**Goal:** Implementar caixa sem dupla contagem, parcial, crédito futuro explícito, idempotência e reversão.

**Files:**
- Create/modify: `src/ustracker/payments/service.py`
- Create/modify: `src/ustracker/credits/service.py`
- Create/modify: `src/ustracker/api/routers/payments.py`
- Create/modify: `src/ustracker/api/routers/credits.py`
- Create/modify: `tests/integration/test_payments.py`
- Create/modify: `src/ustracker/payments/dimensions.py`

**Interfaces:** Produz PaymentService e CreditService; saldos são projeções de ledgers imutáveis/reversões.

- [ ] **Step 1:** Pagamento amount>0 pertence a um cliente; allocations só em charges desse cliente e <= saldo atual dentro da mesma UoW.

- [ ] **Step 2:** Permitir allocations soma<amount somente se create_credit=true; diferença cria client_credit OPEN. Sem flag, 422.

- [ ] **Step 3:** Aplicar crédito cria credit_allocation idempotente; crédito não vira receita novamente, pois a receita caixa nasce no payment original.

- [ ] **Step 4:** Mesma operation_id+payload de negócio dá replay autorizado; divergência409. Duplicate warning/confirmation token segue seção 13: primeira tentativa não grava payment, reenvio confirmado com mesma chave pode concluir uma única vez.

- [ ] **Step 5:** Payment reversal integral única segue seção 13: invalida allocations e reverte aplicações ativas do crédito originado no mesmo commit, reabrindo charges consumidoras. CreditService.reverse desfaz aplicação, não receita. Registrar reversed_on/applied_on e impedir datas inconsistentes; caixa é reconhecido uma vez.

- [ ] **Step 6:** Rodar pytest tests/integration/test_payments.py -q e tools/verify.py --task T08.

- [ ] **Step 7:** Persistir movimentos financial_dimensions de classificação de recebimentos/créditos e reversões conforme seção 14. Validar soma por dimensões=caixa total, inclusive crédito não atribuído, sem perder relatórios passados.


**Acceptance cases:** T08-C01, T08-C02, T08-C03, T08-C04, T08-C05, T08-C06, T08-C07, T08-C08, T08-C09, T08-C10

**Gate proof:** Evidence/T08 deve provar cada caso obrigatório listado em acceptance_cases, com command/stdout/stderr/exit_code/UTC/environment/build/hashes. Casos adicionais de compatibilidade têm relatório separado.

**Required command pattern:**
```powershell
& .\.venv\Scripts\python.exe tools\verify.py --task T08 --evidence-dir Evidence
if ($LASTEXITCODE -ne 0) { throw 'T08 gate failed' }
```

**Checkpoint:** atualizar Estado/PONTO_DE_PARADA.json e Evidence/ na engenharia, mantendo semente e catálogo do plano imutáveis. Invalidar evidências afetadas por mudança; só avançar com casos obrigatórios PASS.


---

### T09: Despesas, recorrência e fiscal manual

**Depends on:** T08

**Requirements:** R10, R11

**Goal:** Controlar despesas/recorrências e obrigações fiscais sem confundir referência fiscal com gasto duplicado.

**Files:**
- Create/modify: `src/ustracker/expenses/service.py`
- Create/modify: `src/ustracker/fiscal/service.py`
- Create/modify: `src/ustracker/api/routers/expenses.py`
- Create/modify: `src/ustracker/api/routers/fiscal.py`
- Create/modify: `tests/integration/test_expenses_fiscal.py`

**Interfaces:** Produz ExpenseService, RecurrenceService e FiscalService.

- [ ] **Step 1:** ExpenseInput permite category,description,competence,due_on,expected_amount,supplier e links opcionais client/vehicle/subscription/catalog; validar coerência de cliente.

- [ ] **Step 2:** Recorrência gera UNIQUE recurrence_id/competence e alterações só afetam futuras emissões.

- [ ] **Step 3:** Disbursement parcial e reversal integral; soma líquida <= valor efetivo da despesa. Ajuste de previsto só enquanto regra permitida e sempre auditado.

- [ ] **Step 4:** Fiscal obligation pode referenciar expense_id; nesse caso não cria segundo gasto. Mudança de valor vinculada é atômica e bloqueada com desembolso ativo quando incoerente.

- [ ] **Step 5:** Referências fiscais são texto/external key; nenhum PDF fiscal/upload de NF/validação oficial/transmissão na V1.

- [ ] **Step 6:** Rodar pytest tests/integration/test_expenses_fiscal.py -q e tools/verify.py --task T09.

- [ ] **Step 7:** Criar expenses.recurrence_id com UNIQUE(recurrence_id,competence), snapshots de fleet_id e category domain separado. Redução do previsto abaixo do pago líquido retorna409. Eventos de ajuste têm effective_on; recorrência alterada não reescreve emissões.


**Acceptance cases:** T09-C01, T09-C02, T09-C03, T09-C04, T09-C05, T09-C06, T09-C07, T09-C08

**Gate proof:** Evidence/T09 deve provar cada caso obrigatório listado em acceptance_cases, com command/stdout/stderr/exit_code/UTC/environment/build/hashes. Casos adicionais de compatibilidade têm relatório separado.

**Required command pattern:**
```powershell
& .\.venv\Scripts\python.exe tools\verify.py --task T09 --evidence-dir Evidence
if ($LASTEXITCODE -ne 0) { throw 'T09 gate failed' }
```

**Checkpoint:** atualizar Estado/PONTO_DE_PARADA.json e Evidence/ na engenharia, mantendo semente e catálogo do plano imutáveis. Invalidar evidências afetadas por mudança; só avançar com casos obrigatórios PASS.


---

### T10: Fotos, mídia cifrada e journal

**Depends on:** T09

**Requirements:** R16, R17, R21

**Goal:** Validar/reencodar/cifrar fotos sem caminhos fornecidos por usuário e com recuperação crash-safe.

**Files:**
- Create/modify: `src/ustracker/media/service.py`
- Create/modify: `src/ustracker/media/crypto.py`
- Create/modify: `src/ustracker/media/images.py`
- Create/modify: `src/ustracker/api/routers/media.py`
- Create/modify: `tests/integration/test_media.py`

**Interfaces:** Produz MediaService e private media download; usa file journal de T03.

- [ ] **Step 1:** Validar assinatura real/MIME, dimensão <=40MP, tamanho <=20MiB, sem animação; aplicar orientação EXIF e remover metadata/GPS.

- [ ] **Step 2:** Gerar WebP operacional <=1920px qualidade82 e thumb<=320px qualidade75; não ampliar menores. Original só se retain_original=true.

- [ ] **Step 3:** Cifrar cada variante AES-256-GCM com keyring de ambiente; nonce 96-bit único e AAD contendo dataset/media/variant/version. Nonce nunca reutilizado com mesma key.

- [ ] **Step 4:** Gravar stage cifrado, journal PREPARED, referência DB, COMMITTED e FINALIZED; recovery trata cada estado.

- [ ] **Step 5:** Download exige ADMIN e environment, Cache-Control no-store; logout/window detach limpa blob URLs/frontend store.

- [ ] **Step 6:** Rodar pytest tests/integration/test_media.py -q e tools/verify.py --task T10.

- [ ] **Step 7:** Deduplicação e retenção seguem seção 14: mesmo dataset e transformação; duas photos podem compartilhar media; não remover arquivo com referências. Original opt-in cifrado pode conter metadados, variante operacional deve removê-los.


**Acceptance cases:** T10-C01, T10-C02, T10-C03, T10-C04, T10-C05, T10-C06, T10-C07

**Gate proof:** Evidence/T10 deve provar cada caso obrigatório listado em acceptance_cases, com command/stdout/stderr/exit_code/UTC/environment/build/hashes. Casos adicionais de compatibilidade têm relatório separado.

**Required command pattern:**
```powershell
& .\.venv\Scripts\python.exe tools\verify.py --task T10 --evidence-dir Evidence
if ($LASTEXITCODE -ne 0) { throw 'T10 gate failed' }
```

**Checkpoint:** atualizar Estado/PONTO_DE_PARADA.json e Evidence/ na engenharia, mantendo semente e catálogo do plano imutáveis. Invalidar evidências afetadas por mudança; só avançar com casos obrigatórios PASS.


---

### T11: Dashboard, busca, CSV/XLSX e performance

**Depends on:** T10

**Requirements:** R12, R13, R19

**Goal:** Entregar visão financeira por caixa/competência, busca global completa e exports seguros.

**Files:**
- Create/modify: `src/ustracker/dashboard/service.py`
- Create/modify: `src/ustracker/search/service.py`
- Create/modify: `src/ustracker/reports/service.py`
- Create/modify: `src/ustracker/reports/xlsx.py`
- Create/modify: `src/ustracker/api/routers/dashboard.py`
- Create/modify: `src/ustracker/api/routers/search.py`
- Create/modify: `src/ustracker/api/routers/reports.py`
- Create/modify: `tests/integration/test_reports.py`
- Create/modify: `tests/performance/test_profile_p1.py`

**Interfaces:** Produz Summary, SearchResult, CSV/XLSX e métricas P1.

- [ ] **Step 1:** Cash usa datas de pagamento/reversão; accrual usa competence do previsto efetivo. Não reescrever passado pelo saldo atual.

- [ ] **Step 2:** Summary inclui clientes/veículos/assinaturas ativos, receita prevista/recebida, aberto/vencido, gastos previstos/pagos, resultado/margem, próximos vencimentos, inadimplentes, séries e distribuição por plano.

- [ ] **Step 3:** SearchService cobre nome/documento/telefone/email/placa/veículo/plano/assinatura/cobrança/pagamento/despesa; paginação e sort allowlist.

- [ ] **Step 4:** CSV UTF-8-SIG ; e XLSX admin-only; neutralizar =,+,-,@ em texto; metadados de filtro/basis/data; números como números no XLSX.

- [ ] **Step 5:** Integrações mostram PREPARED_DISABLED; não chamar provider externo.

- [ ] **Step 6:** Criar seed P1 sintético D22; medir P95 busca e dashboard12m, registrar hardware/OS/DB size; falha de performance é bloqueante para T18 até otimizar ou revisar formalmente o perfil.

- [ ] **Step 7:** Rodar pytest tests/integration/test_reports.py -q, pytest tests/performance/test_profile_p1.py -q e tools/verify.py --task T11.

- [ ] **Step 8:** Implementar ReportFilter com vehicle_id/fleet_id/catalog_id/as_of e Summary ampliado conforme seção 14. Agrupar por dimensões congeladas, distribuir centavos com soma exata; despesa geral e crédito sem atribuição ficam explícitos. Validar visão passada após transferência de veículo, aplicação/estorno de crédito e data de evento.


**Acceptance cases:** T11-C01, T11-C02, T11-C03, T11-C04, T11-C05, T11-C06, T11-C07, T11-C08, T11-C09, T11-C10

**Gate proof:** Evidence/T11 deve provar cada caso obrigatório listado em acceptance_cases, com command/stdout/stderr/exit_code/UTC/environment/build/hashes. Casos adicionais de compatibilidade têm relatório separado.

**Required command pattern:**
```powershell
& .\.venv\Scripts\python.exe tools\verify.py --task T11 --evidence-dir Evidence
if ($LASTEXITCODE -ne 0) { throw 'T11 gate failed' }
```

**Checkpoint:** atualizar Estado/PONTO_DE_PARADA.json e Evidence/ na engenharia, mantendo semente e catálogo do plano imutáveis. Invalidar evidências afetadas por mudança; só avançar com casos obrigatórios PASS.


---

### T12: Interface completa e acessível

**Depends on:** T11

**Requirements:** R02, R12, R14, R15, R19

**Goal:** Construir UI modular pública/admin sem entregar segredo ao navegador e com comportamento consistente.

**Files:**
- Create/modify: `frontend/index.html`
- Create/modify: `frontend/css/tokens.css`
- Create/modify: `frontend/css/layout.css`
- Create/modify: `frontend/css/components.css`
- Create/modify: `frontend/js/api.js`
- Create/modify: `frontend/js/store.js`
- Create/modify: `frontend/js/router.js`
- Create/modify: `frontend/js/components/data_table.js`
- Create/modify: `frontend/js/pages/*.js`
- Create/modify: `tests/ui/test_ui.py`

**Interfaces:** Consome API v1; produz shell PUBLIC/login/admin e páginas funcionais.

- [ ] **Step 1:** ES modules locais sem CDN. api.js é única fronteira HTTP; store privado é esvaziado em 401/logout/window detach.

- [ ] **Step 2:** Páginas: Dashboard, Clientes, Veículos, Planos/Itens, Assinaturas, Recebimentos/Créditos, Despesas, Fiscal, Relatórios e Sistema. Pesquisa global no topo.

- [ ] **Step 3:** Componente DataTable único: page_size50 max100, sort/filter allowlist, clear filters, sticky header, números direita, texto esquerda.

- [ ] **Step 4:** Autosave apenas cadastros: debounce800ms+blur+revision. Financeiro/destrutivo exige botão/modal explícito e idempotency key por ação.

- [ ] **Step 5:** Renderizar conteúdo de usuário via textContent/encoding; impedir XSS; keyboard/focus/aria-live; status com texto/ícone além de cor.

- [ ] **Step 6:** Validar 1366x768@125% e 1920x1080; Playwright/browser tests podem cobrir DOM, mas WebView2 nativo fecha em T16/T18.

- [ ] **Step 7:** Rodar tools/verify.py --task T12 e suite UI.


**Acceptance cases:** T12-C01, T12-C02, T12-C03, T12-C04, T12-C05, T12-C06

**Gate proof:** Evidence/T12 deve provar cada caso obrigatório listado em acceptance_cases, com command/stdout/stderr/exit_code/UTC/environment/build/hashes. Casos adicionais de compatibilidade têm relatório separado.

**Required command pattern:**
```powershell
& .\.venv\Scripts\python.exe tools\verify.py --task T12 --evidence-dir Evidence
if ($LASTEXITCODE -ne 0) { throw 'T12 gate failed' }
```

**Checkpoint:** atualizar Estado/PONTO_DE_PARADA.json e Evidence/ na engenharia, mantendo semente e catálogo do plano imutáveis. Invalidar evidências afetadas por mudança; só avançar com casos obrigatórios PASS.


---

### T13: Administração, branding e laboratório Test

**Depends on:** T12

**Requirements:** R03, R15, R25, R35

**Goal:** Permitir configuração segura e um laboratório destrutível sem tocar Production/Auth.

**Files:**
- Create/modify: `src/ustracker/settings/service.py`
- Create/modify: `src/ustracker/branding/service.py`
- Create/modify: `src/ustracker/sandbox/service.py`
- Create/modify: `src/ustracker/clients/anonymize.py`
- Create/modify: `src/ustracker/api/routers/settings.py`
- Create/modify: `src/ustracker/api/routers/sandbox.py`
- Create/modify: `frontend/js/pages/system.js`
- Create/modify: `tests/integration/test_sandbox_settings.py`

**Interfaces:** Produz BrandingService, SettingsService, SandboxService e anonymization.

- [ ] **Step 1:** Settings com schema/allowlist: company_legal_name,company_display_name,contact_phone,contact_email,address_display,theme tokens permitidos,display texts/default_grace_days. Segurança usa rotas próprias.

- [ ] **Step 2:** Brand assets PNG/JPEG/WebP/ICO validados/reencodados; icon slots fixos. Restore default não altera copyright/licenças.

- [ ] **Step 3:** Test possui database/media/jobs/exports/backups/dataset keys separados. Environment vem da sessão, não query/header.

- [ ] **Step 4:** Reset Test exige expected_dataset_id + confirmação LIMPAR TESTES, drena jobs, arquiva staging, recria dataset/generation/keys Test e preserva AuthStore/Production.

- [ ] **Step 5:** Anonymize exige reason/confirmation, remove PII/public projection/media elegível, preserva IDs/agregados/finance audit; informa backups antigos por retenção.

- [ ] **Step 6:** Rodar pytest tests/integration/test_sandbox_settings.py -q e tools/verify.py --task T13.

- [ ] **Step 7:** Audit before/after de cadastro não guarda PII bruta; anonimização não deixa cópia de nome/documento/endereço no audit atual. Backups históricos seguem retenção e alerta explícito. Branding não altera identificador interno UStracker nem license/copyright.


**Acceptance cases:** T13-C01, T13-C02, T13-C03, T13-C04, T13-C05, T13-C06, T13-C07, T13-C08

**Gate proof:** Evidence/T13 deve provar cada caso obrigatório listado em acceptance_cases, com command/stdout/stderr/exit_code/UTC/environment/build/hashes. Casos adicionais de compatibilidade têm relatório separado.

**Required command pattern:**
```powershell
& .\.venv\Scripts\python.exe tools\verify.py --task T13 --evidence-dir Evidence
if ($LASTEXITCODE -ne 0) { throw 'T13 gate failed' }
```

**Checkpoint:** atualizar Estado/PONTO_DE_PARADA.json e Evidence/ na engenharia, mantendo semente e catálogo do plano imutáveis. Invalidar evidências afetadas por mudança; só avançar com casos obrigatórios PASS.


---

### T14: Backup, restore, recovery export e transferência

**Depends on:** T13

**Requirements:** R20, R22, R25

**Goal:** Criar formatos de backup/recuperação autenticados e transferência writer sem merge offline.

**Files:**
- Create/modify: `src/ustracker/backup/format.py`
- Create/modify: `src/ustracker/backup/service.py`
- Create/modify: `src/ustracker/backup/recovery_export.py`
- Create/modify: `src/ustracker/stations/service.py`
- Create/modify: `src/ustracker/api/routers/backups.py`
- Create/modify: `src/ustracker/api/routers/stations.py`
- Create/modify: `tests/integration/test_backup_transfer.py`
- Create/modify: `src/ustracker/stations/identity.py`

**Interfaces:** Produz LOCAL_BACKUP_V1, RECOVERY_EXPORT_V1, BackupService e StationService.

- [ ] **Step 1:** Implementar BINARY_CONTAINER_V1 exatamente conforme seção 9 de 02_CONTRATOS.md: magic/header/chunks/EOF, HKDF/scrypt por formato, nonce_prefix8 e AAD=SHA256(header_bytes)||uint32_be(chunk_index)||uint32_be(total_chunks). Validar limites antes de alocar e rejeitar truncamento/reordenação/bytes extras.

- [ ] **Step 2:** Capturar snapshot consistente sob manutenção/lock e journal finalizado; incluir DB/media/projeção/settings/envelopes do ambiente. LOCAL_BACKUP não restaura AuthStore; merge de keyring é aditivo e rejeita conflito de key_id. Nenhum payload privado em plaintext no disco.

- [ ] **Step 3:** Backup só VALID depois de restore em sandbox temporária + cipher/integrity/FK/hash media. Retenção D21.

- [ ] **Step 4:** RECOVERY_EXPORT_V1 segue passphrase/KDF/framing da seção 9; ação explícita com AuthStore/Vault/datasets escolhidos. Import em raiz isolada, credenciais antigas requerem re-enrollment antes de produção. Test não restaura nem apaga credenciais compartilhadas.

- [ ] **Step 5:** Restore sob maintenance: validar/staging/par dataset+keyring/journal, promover ponteiro único, preservar anterior até aceite e reverter conjunto íntegro em falha. Recovery incrementa geração acima da maior conhecida e exige retirada administrativa de clones antigos; não promete revogação offline remota.

- [ ] **Step 6:** STATION_TRANSFER_V1 segue seção 9: X25519/HKDF e assinatura Ed25519, fingerprint previamente confiada, privadas locais DPAPI fora de backup/release, mesma linhagem VRK, transfer journal, TRANSFERRED antes de publicar pacote. Crash reentrega mesmos bytes; target/generation incorretos e replay não substituem dataset.

- [ ] **Step 7:** Rodar pytest tests/integration/test_backup_transfer.py -q e tools/verify.py --task T14.


**Acceptance cases:** T14-C01, T14-C02, T14-C03, T14-C04, T14-C05, T14-C06, T14-C07, T14-C08, T14-C09, T14-C10, T14-C11, T14-C12, T14-C13

**Gate proof:** Evidence/T14 deve provar cada caso obrigatório listado em acceptance_cases, com command/stdout/stderr/exit_code/UTC/environment/build/hashes. Casos adicionais de compatibilidade têm relatório separado.

**Required command pattern:**
```powershell
& .\.venv\Scripts\python.exe tools\verify.py --task T14 --evidence-dir Evidence
if ($LASTEXITCODE -ne 0) { throw 'T14 gate failed' }
```

**Checkpoint:** atualizar Estado/PONTO_DE_PARADA.json e Evidence/ na engenharia, mantendo semente e catálogo do plano imutáveis. Invalidar evidências afetadas por mudança; só avançar com casos obrigatórios PASS.


---

### T15: Updater manual assinado e rollback

**Depends on:** T14

**Requirements:** R23, R24, R31

**Goal:** Aplicar release isolada assinada sem tocar dados até staging/migração/validação completos.

**Files:**
- Create/modify: `src/ustracker/update/service.py`
- Create/modify: `src/ustracker/update/manifest.py`
- Create/modify: `host/Updater/Program.cs`
- Create/modify: `tools/build_update.py`
- Create/modify: `tests/integration/test_update.py`

**Interfaces:** Produz UpdateService, manifest/signature verifier e updater externo.

- [ ] **Step 1:** Patch manifest JSON canônico: format,product,package_id,from_version,to_version,schema_from,to,compat_sequence,created_at,files(path,size,sha256),total_expanded_bytes,key_id. manifest.sig Ed25519 sobre bytes exatos.

- [ ] **Step 2:** Inspect valida assinatura antes de extrair; rejeita traversal, absolute/UNC, ADS, symlink/reparse, case collision, zip bomb, UserData/Auth replacement e tamanho expandido > limite do manifest/2GiB V1.

- [ ] **Step 3:** Entrar QUIESCED/maintenance, bloquear writes e drenar jobs/journals; então criar LOCAL_BACKUP pre-update VALID do checkpoint congelado e checar espaço. Só depois STAGED/extrair release candidata. Manter freeze até ACCEPTED; seguir protocolo da seção 15 de 02_CONTRATOS.md.

- [ ] **Step 4:** Migrar cópia do dataset; smoke de health/storage/auth/public; SWITCH de current.json aponta atomicamente o par release+dataset compatível. Persistir update journal; somente VERIFIED→ACCEPTED libera writes. Testar crash em cada transição.

- [ ] **Step 5:** Falha antes de ACCEPTED retorna release+dataset+files ao mesmo checkpoint. Rollback posterior jamais restaura banco antigo se houve novas writes; só troca release se schema backward-compatible; senão bloqueia e orienta recovery.

- [ ] **Step 6:** Rodar pytest tests/integration/test_update.py -q e tools/verify.py --task T15.


**Acceptance cases:** T15-C01, T15-C02, T15-C03, T15-C04, T15-C05, T15-C06, T15-C07

**Gate proof:** Evidence/T15 deve provar cada caso obrigatório listado em acceptance_cases, com command/stdout/stderr/exit_code/UTC/environment/build/hashes. Casos adicionais de compatibilidade têm relatório separado.

**Required command pattern:**
```powershell
& .\.venv\Scripts\python.exe tools\verify.py --task T15 --evidence-dir Evidence
if ($LASTEXITCODE -ne 0) { throw 'T15 gate failed' }
```

**Checkpoint:** atualizar Estado/PONTO_DE_PARADA.json e Evidence/ na engenharia, mantendo semente e catálogo do plano imutáveis. Invalidar evidências afetadas por mudança; só avançar com casos obrigatórios PASS.


---

### T16: Launcher Windows, WebView2 e ciclo completo

**Depends on:** T15

**Requirements:** R18, R19, R20

**Goal:** Fechar implementação nativa sobre a fundação T01 e provar lifecycle/portabilidade no Windows real/VM.

**Files:**
- Create/modify: `host/Bootstrap/Program.cs`
- Create/modify: `host/Shell/App.xaml`
- Create/modify: `host/Shell/MainWindow.xaml`
- Create/modify: `host/Shell/ProcessSupervisor.cs`
- Create/modify: `host/Shared/RootPaths.cs`
- Create/modify: `host/Shared/PipeProtocol.cs`
- Create/modify: `tools/package_portable.ps1`
- Create/modify: `tests/native/test_host.py`

**Interfaces:** Consome API/lifecycle/updater; produz UStracker.exe/Host x64, supervisor e pacote portátil.

- [ ] **Step 1:** Compilar net48 x64. Bootstrap valida current/release/hash, WebView2 Runtime e Runtime Python; cria profile WebView2 efêmero por Shell em LocalAppData.

- [ ] **Step 2:** Mutex por installation/dataset + named pipe ACL usuário atual e nonce. Reusar supervisor identificado; não confiar só em PID/porta.

- [ ] **Step 3:** X chama detach seguro, revoga sessão, fecha WebView2/profile; remove profile após liberação dos handles ou enfileira limpeza. Backend persiste e jobs privados aguardam login em WAITING após última sessão. Crash de Shell detectado pelo pipe/heartbeat; segundo launch usa profile novo PUBLIC_UI.

- [ ] **Step 4:** Encerrar Sistema exige ADMIN, DRAINING/flush/close e supervisor mata somente processos filhos/handles próprios. Shutdown intencional não reinicia.

- [ ] **Step 5:** Crash backend: máximo3 tentativas com backoff 1s/3s/10s; depois diagnóstico sem loop. Porta/PID alheio nunca terminado.

- [ ] **Step 6:** Explorer: destinos enum Backups/Exports/Logs, ProcessStartInfo.FileName absoluto, UseShellExecute=false e Arguments com helper de quoting Windows compatível net48, conforme seção 15. Não usar cmd.exe, string shell arbitrária ou API ausente nesse target.

- [ ] **Step 7:** Rodar tools/verify.py --task T16 --native --profile win10_22h2; relatório adicional --profile windows11. Falha nativa formal bloqueia; ausência de ambiente de compatibilidade é registrada e não declarada PASS.

- [ ] **Step 8:** Provar dependências do Runtime e portabilidade em VM limpa. Executar harness nativo em VerificationBundle separado usando Runtime do candidato; cliente inicia sem SDK/dependências de teste globais.


**Acceptance cases:** T16-C01, T16-C02, T16-C03, T16-C04, T16-C05, T16-C06, T16-C07

**Gate proof:** Evidence/T16 deve provar cada caso obrigatório listado em acceptance_cases, com command/stdout/stderr/exit_code/UTC/environment/build/hashes. Casos adicionais de compatibilidade têm relatório separado.

**Required command pattern:**
```powershell
& .\.venv\Scripts\python.exe tools\verify.py --task T16 --native --profile win10_22h2 --evidence-dir Evidence
if ($LASTEXITCODE -ne 0) { throw 'T16 gate failed' }
```

**Checkpoint:** atualizar Estado/PONTO_DE_PARADA.json e Evidence/ na engenharia, mantendo semente e catálogo do plano imutáveis. Invalidar evidências afetadas por mudança; só avançar com casos obrigatórios PASS.


---

### T17: Integrações futuras desativadas

**Depends on:** T16

**Requirements:** R26, R27, R28, R29, R30

**Goal:** Preservar portas futuras sem rede, segredo ou falsa funcionalidade na V1.

**Files:**
- Create/modify: `src/ustracker/integrations/contracts.py`
- Create/modify: `src/ustracker/integrations/disabled.py`
- Create/modify: `src/ustracker/api/routers/integrations.py`
- Create/modify: `frontend/js/pages/integrations.js`
- Create/modify: `tests/integration/test_disabled_integrations.py`

**Interfaces:** Produz CloudProvider/TrackingProvider/FiscalProvider disabled e IntegrationStatus.

- [ ] **Step 1:** Config só aceita provider/folder_id/identificadores não secretos. Campos token,password,secret,private_key são rejeitados.

- [ ] **Step 2:** Status V1 enabled=false,implemented=false; UI “Preparado para versão futura”.

- [ ] **Step 3:** Qualquer execute/sync/connect retorna501 INTEGRATION_NOT_IMPLEMENTED e não abre socket/HTTP.

- [ ] **Step 4:** Interfaces de domínio não importam Drive/tracking/fiscal clients. Provider futuro é adapter substituível.

- [ ] **Step 5:** Não criar GitHub remote, OAuth, webhook público, WhatsApp/e-mail ou hosting nesta release.

- [ ] **Step 6:** Rodar pytest tests/integration/test_disabled_integrations.py -q e tools/verify.py --task T17.


**Acceptance cases:** T17-C01, T17-C02, T17-C03, T17-C04

**Gate proof:** Evidence/T17 deve provar cada caso obrigatório listado em acceptance_cases, com command/stdout/stderr/exit_code/UTC/environment/build/hashes. Casos adicionais de compatibilidade têm relatório separado.

**Required command pattern:**
```powershell
& .\.venv\Scripts\python.exe tools\verify.py --task T17 --evidence-dir Evidence
if ($LASTEXITCODE -ne 0) { throw 'T17 gate failed' }
```

**Checkpoint:** atualizar Estado/PONTO_DE_PARADA.json e Evidence/ na engenharia, mantendo semente e catálogo do plano imutáveis. Invalidar evidências afetadas por mudança; só avançar com casos obrigatórios PASS.


---

### T18: Integração completa, homologação e entrega

**Depends on:** T17

**Requirements:** R01, R31, R32, R33, R34, R36

**Goal:** Entregar release 1.00.00.000 reproduzível com todas as funções obrigatórias provadas e nenhum bloqueante aberto.

**Files:**
- Create/modify: `tests/e2e/test_complete_flow.py`
- Create/modify: `tests/native/test_release.py`
- Create/modify: `tools/release_gate.py`
- Create/modify: `docs/MANUAL_USUARIO.md`
- Create/modify: `docs/RECUPERACAO.md`
- Create/modify: `docs/RELATORIO_ENTREGA.md`
- Create/modify: `docs/RASTREABILIDADE.csv`
- Create/modify: `docs/AJUSTES_FUTUROS.log`

**Interfaces:** Consome gates T01–T17 e produz ZIP runtime, Source snapshot, SBOM/licenças, manuais, hashes e evidências.

- [ ] **Step 1:** Congelar candidato e manifest hashes. Gerar docs/RASTREABILIDADE.csv requisito→H-item→arquivo/função→caso→evidência.

- [ ] **Step 2:** Executar TODOS os IDs de T18 definidos em CASOS_ACEITE.json no candidato congelado; mudança de código/contrato invalida evidência dependente e exige nova prova. Não presumir limite C08 se a matriz crescer.

- [ ] **Step 3:** Executar suites unit/integration/ui/performance/native no perfil win10_22h2; registrar OS build, WebView2 Runtime, Python, SQLCipher, hardware/tempos/hashes. Win11 tem relatório separado; sem PASS nesse perfil não declarar compatibilidade homologada.

- [ ] **Step 4:** Classificar achados: BLOCKING corrige agora e reroda dependências; somente cosmetic/nonblocking entra AJUSTES_FUTUROS.log com reprodução/impacto/alvo.

- [ ] **Step 5:** Empacotar runtime sem dados reais, sessão, secrets ou signing private key. Incluir Licenses/SBOM/diagnóstico/recovery. Ao proprietário, incluir Source.zip/snapshot hash.

- [ ] **Step 6:** Versão inicial aceita =1.00.00.000. Sem Windows10 native PASS, SQLCipher real PASS e todos casos obrigatórios atuais PASS, estado final BLOCKED/PARTIAL, nunca COMPLETE. Chave produtiva do proprietário é requisito da assinatura final; chave de teste não prova autenticidade de release produtiva.

- [ ] **Step 7:** Atualizar PONTO_DE_PARADA.json para COMPLETE somente depois do release_gate PASS.

- [ ] **Step 8:** Implementar tools/release_gate.py --candidate Dist/Candidate --evidence-dir Evidence; conferir candidato/hash/evidência/perfil e casos obrigatórios. Exit não zero se caso ausente/NAO_EXECUTADO/FAIL/BLOCKED/INVALIDATED ou prova de outra revisão/build.


**Acceptance cases:** T18-C01, T18-C02, T18-C03, T18-C04, T18-C05, T18-C06, T18-C07, T18-C08, T18-C09, T18-C10

**Gate proof:** Evidence/T18 deve provar cada caso obrigatório listado em acceptance_cases, com command/stdout/stderr/exit_code/UTC/environment/build/hashes. Casos adicionais de compatibilidade têm relatório separado.

**Required command pattern:**
```powershell
& .\.venv\Scripts\python.exe tools\verify.py --task T18 --native --profile win10_22h2 --evidence-dir Evidence
if ($LASTEXITCODE -ne 0) { throw 'T18 gate failed' }
```

**Checkpoint:** atualizar Estado/PONTO_DE_PARADA.json e Evidence/ na engenharia, mantendo semente e catálogo do plano imutáveis. Invalidar evidências afetadas por mudança; só avançar com casos obrigatórios PASS.
