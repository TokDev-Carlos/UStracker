# Contratos canônicos — PECSUS 1.2.1

Este arquivo é a **única autoridade de nomes de DTOs, entidades, segurança, estados e interfaces**. Não existem “complementos normativos” posteriores que alterem silenciosamente estes contratos. Se uma implementação precisar mudar assinatura/campo, atualizar primeiro este arquivo + matrizes + casos afetados e invalidar evidências correspondentes.

## 1. Convenções
- Python: PEP 8, type hints, Pydantic/dataclasses, snake_case.
- JSON: snake_case. Datas `YYYY-MM-DD`, competência `YYYY-MM`, timestamps RFC3339 UTC.
- Money API: string decimal 2 casas; DB: INTEGER cents; quantidade: Decimal serializado como string.
- IDs internos: UUID textual. Nenhum ID operacional no PUBLIC.
- Agregados mutáveis: `created_at`, `updated_at`, `revision>=1`. Eventos append-only têm `id`, `created_at` e sequência quando aplicável; nunca update/delete lógico do evento original.
- Mutações operacionais: ADMIN + CSRF + `Idempotency-Key`; agregados existentes também `If-Match`/revision. Exceções de autenticação/setup e repetição estão fechadas na seção 12; não exigir sessão ADMIN para login/enrollment.

## 2. Enums canônicos
```text
Environment = production | test
ClientStatus = ACTIVE | INACTIVE | BLOCKED | CANCELLED
TrackingStatus = ACTIVE | INACTIVE | SUSPENDED | REMOVED | UNKNOWN
CatalogKind = PLAN | ITEM
RenewalMode = NONE | MANUAL | AUTO
SubscriptionLifecycle = ACTIVE | PAUSED | CANCELLED | ENDED
ChargeState = ISSUED | VOID
AdjustmentKind = DISCOUNT | SURCHARGE | PENALTY | INTEREST | OTHER
CreditState = OPEN | CONSUMED | REVERSED
ExpenseState = ACTIVE | VOID
JobState = QUEUED | RUNNING | WAITING | SUCCEEDED | FAILED | CANCELLED | RECOVERY_REQUIRED
DatasetState = ACTIVE | TRANSFERRED | RECOVERY
AdminSlotState = EMPTY | PENDING_ENROLLMENT | ENROLLED
```

## 3. DTOs canônicos
```python
from datetime import date, datetime
from decimal import Decimal
from typing import BinaryIO, Literal, Protocol
from uuid import UUID

Money = str

class Address:
    postcode: str | None
    street: str
    number: str
    complement: str
    neighborhood: str
    city: str
    state: str

class Context:
    admin_id: UUID
    station_id: UUID
    dataset_id: UUID
    environment: Literal["production", "test"]
    request_id: UUID

class ClientInput:
    legal_name: str
    trade_name: str | None
    public_name: str | None
    document_type: Literal["CPF", "CNPJ"] | None
    document: str | None
    email: str | None
    phones: list[str]
    address: Address
    notes: str
    status: Literal["ACTIVE", "INACTIVE", "BLOCKED", "CANCELLED"]

class FleetInput:
    client_id: UUID
    name: str
    sector_or_unit: str | None
    notes: str

class VehicleInput:
    plate: str
    client_id: UUID
    fleet_id: UUID | None
    brand: str
    model: str
    year: int | None
    color: str
    vehicle_type: str
    renavam: str | None
    tracker_ref: str | None
    tracker_serial_imei: str | None
    installed_on: date | None
    tracking_status: Literal["ACTIVE","INACTIVE","SUSPENDED","REMOVED","UNKNOWN"]
    notes: str

class CatalogInput:
    code: str
    name: str
    description: str
    category: str
    kind: Literal["PLAN", "ITEM"]
    billing_interval_months: int | None
    price: Money
    estimated_cost: Money
    notes: str
    public: bool
    active: bool
    effective_on: date

class ChargeItem:
    logical_item_id: UUID | None
    description: str
    quantity: Decimal
    unit_price: Money
    vehicle_id: UUID | None
    catalog_id: UUID | None

class SubscriptionInput:
    client_id: UUID
    signed_on: date
    start_on: date
    end_on: date | None
    due_day: int
    billing_interval_months: int
    renewal_mode: Literal["NONE","MANUAL","AUTO"]
    lifecycle_status: Literal["ACTIVE","PAUSED","CANCELLED","ENDED"]
    effective_month: str | None
    items: list[ChargeItem]
    note: str

class ChargeInput:
    subscription_id: UUID
    competence: str
    due_on: date
    items: list[ChargeItem]
    reason: str | None

class AdjustmentInput:
    kind: Literal["DISCOUNT","SURCHARGE","PENALTY","INTEREST","OTHER"]
    amount: Money
    reason: str
    competence: str
    effective_on: date

class PaymentInput:
    client_id: UUID
    amount: Money
    paid_on: date
    method: str
    allocations: list["Allocation"]
    create_credit: bool
    external_ref: str | None
    notes: str
    duplicate_confirmation: str | None

class Allocation:
    charge_id: UUID
    amount: Money

class CreditAllocationInput:
    credit_id: UUID
    charge_id: UUID
    amount: Money
    applied_on: date

class ExpenseInput:
    category_id: UUID
    fleet_id: UUID | None
    description: str
    competence: str
    due_on: date
    expected_amount: Money
    supplier: str | None
    client_id: UUID | None
    vehicle_id: UUID | None
    subscription_id: UUID | None
    catalog_id: UUID | None
    notes: str

class ObligationInput:
    kind: str
    reference: str | None
    competence: str
    due_on: date
    amount: Money
    expense_id: UUID | None
    external_key: str | None
    notes: str

class PhotoInput:
    owner_kind: Literal["client", "vehicle"]
    owner_id: UUID
    stream: BinaryIO
    retain_original: bool
    caption: str

class ReportFilter:
    start: date
    end: date
    basis: Literal["cash", "accrual"]
    client_id: UUID | None
    plan_id: UUID | None
    vehicle_id: UUID | None
    fleet_id: UUID | None
    catalog_id: UUID | None
    as_of: date

class StationInput:
    label: str
    encryption_public_key: str
    signing_public_key: str

class DatabaseKeyProvider(Protocol):
    def get_key(self, environment: str, dataset_id: UUID, purpose: str = "database") -> bytes: ...
```

## 4. Serviços normativos
```text
RootPaths.resolve(executable: Path) -> RootPaths
StorageFactory.open(ctx_or_dataset, key_provider, readonly=False) -> Database
UnitOfWork.write(ctx, operation_id, method, route, payload) -> context manager
AuthService.login(login,password,environment) -> Session
AuthService.enroll(slot,ticket,name,password) -> None
AuthService.issue_enrollment_ticket(target_slot,reason) -> str
AuthService.reset_slot(target_slot,reason) -> str          # retorna ticket UMA VEZ
AuthService.change_password(current_password,new_password) -> None
AuthService.logout(session_cookie) -> None
VaultService.unlock(slot,password) -> VaultSession
VaultKeyProvider.get_key(environment,dataset_id,purpose) -> bytes
ClientService.create/update/archive(...)
VehicleService.create/update/archive/transfer(...)
FleetService.create/update/archive(...)
CatalogService.save/archive(...)
SubscriptionService.save/set_status(...)
ChargeService.generate_month/issue/adjust/reschedule_due/void(...)
PaymentService.record/reverse(...)
CreditService.apply/reverse(...)
ExpenseService.create/adjust/pay/reverse/archive(...)
FiscalService.record/update/archive(...)
MediaService.attach/replace/update_caption/download(...)
DashboardService.summary(ctx,filters) -> Summary
SearchService.search(ctx,query,kinds,page,page_size,sort) -> Page[SearchResult]
ReportService.csv/xlsx(ctx,filters) -> bytes
BrandingService.replace/reset(...)
SandboxService.reset(ctx,expected_dataset_id,confirmation) -> UUID
BackupService.create/restore/list/verify(...)
RecoveryExportService.create/import(...)
StationService.register/transfer/import_package(...)
UpdateService.inspect/apply/rollback(...)
LifecycleService.detach_shell/shutdown(...)
```

## 5. Modelo relacional 0001
| Tabela | Campos específicos | Invariantes |
|---|---|---|
| datasets | name,environment,schema_version,writer_station_id,generation,state | env imutável; uma writer |
| stations | dataset_id,label,encryption_public_key,signing_public_key,enabled | máx.3 habilitadas |
| clients | legal_name,trade_name,public_name,normalized_*,document_type,document,email,phones_json,address_json,notes,status,archived | documento único quando presente |
| fleets | client_id,name,sector_or_unit,notes,active | nome único por cliente |
| vehicles | plate,brand,model,year,color,vehicle_type,renavam,tracker_ref,tracker_serial_imei,installed_on,tracking_status,notes,active | plate normalized único ativo |
| ownerships | vehicle_id,client_id,fleet_id,valid_from,valid_to | intervalos sem sobreposição |
| catalog_categories | name,active | nome normalizado único; independente de categories |
| catalog | code,name,description,category,kind,billing_interval_months,notes,public,active | code único; interval 1..120 ou null one-time |
| catalog_prices | catalog_id,price_cents,estimated_cost_cents,valid_from,valid_to | histórico imutável após uso |
| subscriptions | client_id,signed_on,start_on,end_on,due_day,billing_interval_months,renewal_mode,lifecycle_status | lifecycle não guarda overdue |
| subscription_versions | subscription_id,effective_month,signed_on,start_on,end_on,due_day,billing_interval_months,renewal_mode,note | unique subscription/month |
| subscription_items | version_id,logical_item_id,catalog_id,vehicle_id,description,quantity_text,unit_cents,billing_interval_months | congelado |
| subscription_status_events | subscription_id,status,effective_month,reason | append-only |
| charges | subscription_id,client_id,competence,due_on,gross_cents,net_cents,policy_id,state,voided_on | unique subscription/competence |
| charge_items | charge_id,logical_item_id,one_time,vehicle_id,catalog_id,fleet_id,description,quantity_text,unit_cents,line_cents | soma gross |
| charge_adjustments | charge_id,kind,signed_cents,reason,competence,effective_on | append-only; net>=0 |
| charge_due_events | charge_id,old_due_on,new_due_on,reason | append-only |
| payments | client_id,amount_cents,paid_on,method,external_ref,notes,operation_id | amount>0 |
| allocations | payment_id,charge_id,amount_cents | mesmo cliente; <= saldo |
| client_credits | client_id,source_payment_id,amount_cents,state | valor = resto explícito |
| credit_allocations | credit_id,charge_id,amount_cents,applied_on,operation_id | não exceder crédito/saldo |
| credit_allocation_reversals | credit_allocation_id,reversed_on,reason,operation_id | integral única; append-only |
| payment_reversals | payment_id,reversed_on,reason,amount_cents | integral única V1 |
| categories | name,active | despesa; referenciada não delete físico |
| expenses | category_id,recurrence_id,fleet_id,description,competence,due_on,expected_cents,supplier,client_id,vehicle_id,subscription_id,catalog_id,notes,state,voided_on | links coerentes |
| expense_adjustments | expense_id,signed_cents,reason,competence,effective_on | append-only |
| disbursements | expense_id,amount_cents,paid_on,method,operation_id | soma líquida<=effective |
| disbursement_reversals | disbursement_id,reversed_on,reason,amount_cents | integral única |
| expense_recurrences | category_id,description,amount_cents,day,start_month,end_month,active | expenses UNIQUE(recurrence_id,competence); recurrence_id null para avulsa |
| fiscal_obligations | kind,reference,competence,due_on,amount_cents,expense_id,external_key,notes,state | expense_id unique quando 1:1 |
| photos | owner_kind,owner_id,media_id,caption,retained_original,active | owner validado no service |
| media | encrypted_path,thumb_path,original_path,sha256,mime,width,height,bytes,key_id,state | path relativo UUID |
| audit_events | actor_id,station_id,entity_kind,entity_id,action,before_json,after_json,origin,previous_hash,event_hash | append-only/sanitizado |
| operations | environment,dataset_id,operation_id,method,route,payload_hash,response_json,actor_id | unique env/dataset/op |
| file_journal | operation_id,target_relpath,stage_relpath,sha256,state | roots validadas |
| financial_dimensions | source_kind,source_id,event_kind,event_on,charge_item_id,client_id,vehicle_id,fleet_id,catalog_id,amount_cents,operation_id | append-only; regras de classificação da seção14 |
| settings | key,value_json | allowlist + revision |
| jobs | kind,state,progress_json,checkpoint_json | sem cloud V1 |
| integration_config | kind,provider,enabled,config_json | enabled=false; sem secret |
| external_refs | entity_kind,entity_id,provider,external_id | gancho futuro |

`overdue` e `awaiting_payment` são derivados. VOID sai de previstos. Valores efetivos = base + adjustments uma única vez.

## 6. AuthStore/VaultStore
`AuthStore` é separado do SQLCipher operacional e contém somente slots, salts/verifiers KDF, envelopes VRK e enrollment-ticket hashes. `VaultStore` contém env/dataset key envelopes e media keyrings cifrados pela VRK.

- KDF admin: scrypt N=131072,r=8,p=1; salt aleatório >=16 bytes; password 12..128.
- Envelope: AES-256-GCM, nonce aleatório 96-bit, AAD inclui product/store_version/slot/key_id.
- Nunca usar palavra `admin` como senha definitiva.
- VRK/key material só em memória durante sessão admin; zeroização em Python é best-effort e não é garantia criptográfica de RAM.
- PUBLIC funciona sem VRK/DB privado.

## 7. API /api/v1
PUBLIC allowlist: `/health`, `/public/view`, `/public/assets/{slot}`, `/auth/csrf`, `/auth/login`, `/auth/session` (sanitizada), enrollment apenas em setup autorizado. Todo o restante é ADMIN.

Principais grupos: clients, vehicles, fleets, catalog, subscriptions, charges, payments, credits, expenses, fiscal, media, dashboard, search, reports, settings, branding, sandbox, backups, stations, update, system, integrations.

Mutação existente exige `If-Match`; conflito=409. Validação=422. Não autenticado=401. Autenticado sem condição/CSRF=403. Writer inactive/maintenance=423. Integração futura=501.

## 8. Summary canônico
`Summary` contém: revenue_expected, revenue_received, outstanding, overdue, expenses_expected, expenses_paid, result, margin|null, client_count, vehicle_count, subscription_count, next_due[], delinquent_clients[], plan_distribution[], monthly_series[], integration_status[], revision.

## 9. Formatos canônicos de backup e transferência
### Framing comum BINARY_CONTAINER_V1
- Bytes: magic ASCII `USTBKP01` (8 bytes), header_length uint32 big-endian, header JSON UTF-8 canônico, seguido dos chunks. Header: no máximo 65536 bytes; rejeitar chaves duplicadas, campos desconhecidos e números fora dos limites.
- JSON canônico: chaves ordenadas, separators=(",",":"), ensure_ascii=False, allow_nan=False, sem floats; UUIDs e timestamps em strings normalizadas. Hashes hex minúsculo; bytes em Base64 padrão.
- Header contém format, backup_id, dataset_id, generation, schema_version, created_at, salt32, nonce_prefix8, chunk_size=4194304, compressed_size, total_chunks, expanded_size, manifest_sha256. Campos extras por formato somente os listados abaixo.
- Payload: TAR lógico de arquivos regulares, paths relativos POSIX ordenados, seguido de compressão gzip (mtime=0). Manifest interno lista path/size/sha256; manifest_sha256 é o hash dos bytes canônicos desse manifest; o manifest não lista a si mesmo.
- total_chunks=ceil(compressed_size/chunk_size), 1..2^32-1. Cada chunk é AES-256-GCM e ocupa plaintext_length+16 bytes; todos completos salvo o último. Não há padding ou dados após o último chunk. Rejeitar falta, repetição, reordenação, truncamento e bytes extras.
- Nonce: nonce_prefix8 || uint32_be(chunk_index), índice começando em zero. Salt32 e prefix8 novos por pacote; nunca reutilizar key/nonce.
- AAD: SHA256(header_bytes) || uint32_be(chunk_index) || uint32_be(total_chunks). Mesma fórmula em criação/import/local/recovery/transfer.
- Limites V1: expanded_size <=100 GiB, no máximo 1.000.000 arquivos e nenhum path >1024 bytes UTF-8. Antes de alocar/extrair, exigir espaço para conjunto atual+candidato+rollback. TAR só permite arquivos regulares/diretórios declarados; rejeitar traversal, absolute/UNC, ADS, links, reparse points, paths reservados Windows e colisão case-insensitive. Nunca usar extractall sem validação.
- Staging somente cifrado ou dentro do armazenamento operacional cifrado; não materializar DB/mídia privada em plaintext no disco. Leitura/decompressão em streaming com limite de bytes efetivos.

### LOCAL_BACKUP_V1
- Key: HKDF-SHA256(VRK,salt32,info=UTF8("UStracker Local Backup V1") || UUID(backup_id).bytes), 32 bytes.
- Contém cópia consistente de DB/media/public/journals/settings do ambiente escolhido e envelopes das suas chaves. AuthStore não é revertido por restore local; o administrador atual fornece VRK. Local backup não substitui recovery export na perda do cofre.
- Snapshot: adquirir manutenção/lock de escrita do dataset, drenar jobs, finalizar journal, capturar DB e conjunto referenciado de mídia/envelopes; liberar lock só após cópia cifrada completa. Compactação/validação podem continuar fora do lock com a cópia congelada.
- Restore local exige mesma linhagem de cofre e ambiente; merge aditivo dos key_ids necessários sem remover chaves ainda referenciadas. Recusar key_id conflitante. Nunca restaurar senha antiga, AuthStore ou envelope de administrador revogado.
- VALID somente após restauração em sandbox isolada e cipher_integrity_check/integrity_check/FK/hash de todos os arquivos referenciados.

### RECOVERY_EXPORT_V1
- Passphrase externa escolhida localmente, 16..256 caracteres Unicode UTF-8, sem normalização silenciosa; não persistida.
- Key scrypt N=262144,r=8,p=1,salt32, length32. Header acrescenta kdf com esses parâmetros fixos; validar parâmetros antes de invocar KDF para impedir alocação arbitrária.
- Mesmo framing/AAD. Contém AuthStore/VaultStore completos e datasets selecionados/public/media; seleção e keyrings correspondem ao manifest autenticado.
- Import somente em raiz isolada, validação completa, confirmação administrativa e promoção explícita. Um recovery antigo restaura as credenciais daquele snapshot: re-enrollment/troca de senhas antes de liberar produção. Não sobrescrever credenciais atuais silenciosamente.

### STATION_TRANSFER_V1
- Cadastro administrativo vincula fingerprint das chaves X25519 (cifra) e Ed25519 (assinatura) da estação; cada privada é gerada localmente e protegida por DPAPI CurrentUser. A identidade de estação fica fora do ZIP portátil de release e de backups exportáveis. Mover diretório no mesmo computador preserva identidade; outra máquina deve cadastrar nova estação.
- Header comum acrescenta source_station, target_station, from_generation, to_generation=from_generation+1, ephemeral_public_key, source_signature e sender_signing_key_id. `generation` é to_generation. Outros campos são os mesmos do framing comum.
- Key: X25519 efêmera do emissor × pública X25519 do destino; derivar key32 com HKDF-SHA256(shared_secret,salt32,info=UTF8("UStracker Station Transfer V1") || UUID(backup_id).bytes). Rejeitar shared_secret nulo.
- source_signature = Ed25519(header canônico sem o próprio campo source_signature). Verificar por chave de origem já confiada no cadastro, antes de decifrar. AAD usa o header final completo assinado; payload/manifest estão vinculados a ele.
- Payload inclui dataset e keyrings/envelopes da mesma linhagem de VRK, não inclui privadas de estação. Destino precisa AuthStore/Vault compatível: provisionar previamente via recovery export explícito se estiver vazio; outra linhagem recusa, sem mesclar AuthStores.
- Criar stage cifrado e transfer journal persistente; origem grava TRANSFERRED e fsync antes de tornar pacote final disponível. Crash antes da marcação descarta stage; após marcação reentrega os mesmos bytes/package_id, nunca volta a ACTIVE automaticamente.
- Destino confirma target/fingerprint/generation/hash/assinatura, importa em staging e registra package_id consumido + nova geração ao promover. Replay responde já importado sem substituir dataset atual. Target/generation incorretos recusam sem mutação.
- Registrar maior geração conhecida localmente fora do conjunto restaurável. Recovery aumenta acima dela e da importada; operador deve confirmar retirada de clones/cópias antigas. Não existe revogação remota de cópia totalmente desconectada.

## 10. Update protocol
```text
RECEIVED -> VALIDATED -> QUIESCED -> BACKED_UP -> STAGED -> MIGRATED -> SWITCHED -> VERIFIED -> ACCEPTED
```
Rollback automático só antes de ACCEPTED ou sem writes posteriores. Após writes, downgrade só se schema/release declarar compatibilidade com dataset atual; caso contrário bloquear. Nunca restaurar DB antigo para “voltar executável”.

## 11. Public projection
`UserData/Public/production/view.json` guarda apenas branding público, catálogo/preços com `public=true` e `public_name` explicitamente preenchido. Sem IDs operacionais. `public_dirty` impede servir cópia antiga após revogação até rebuild seguro.

## 12. Autenticação, sessão e exceções de API
- Context operacional é construído no servidor a partir de sessão, estação e dataset; nunca aceitar admin_id/environment arbitrários do corpo.
- Login e pré-CSRF são PUBLIC; não passam por UnitOfWork do DB privado. Setup/enrollment exigem CSRF + capacidade de setup/enrollment válida. Logout/detach/heartbeat são idempotentes no SessionStore, sem depender de DB desbloqueado.
- Bootstrap literal admin só abre wizard após capacidade aleatória 256-bit emitida no pipe ACL do usuário atual, expiração 5 minutos e uso único; nunca autentica ADMIN operacional. Guardar estado do setup no AuthStore com escrita atômica. Interromper e retomar enrollment não recria slots nem reativa senha inicial.
- Enrollment de slots 2/3 é permitido com tickets válidos quando produção ainda está fechada. Somente três slots ENROLLED liberam operações de produção. Reset posterior de um slot restringe novas operações de domínio até concluir enrollment; setup, logout, recuperação e diagnóstico permanecem acessíveis aos admins válidos.
- AuthStore mutations (enroll/reset/change_password) usam journal/replace atômico próprio e audit sanitizado local; não podem depender do DB privado fechado. Auditoria de auth não guarda senhas/tickets/envelopes. Deduplicação de emissão de ticket não revela novamente um segredo consumido: novo pedido revoga ticket anterior e emite outro.
- Scrypt admin usa parâmetros da seção 6, com verificador e KEK derivados por HKDF com info distintos a partir do resultado scrypt. Runtime define maxmem compatível (admin 256 MiB, recovery 512 MiB) e limita a uma KDF concorrente; indisponibilidade resulta erro controlado, sem reduzir custo.
- Throttle: 5 falhas por slot em janela de 5 minutos causam espera de 60 s; teto global 20 tentativas/minuto por instalação. Resposta genérica; clock monotônico para espera, sem logs com credenciais. Não bloquear permanentemente enrollment por terceiros.
- HTTP é somente 127.0.0.1:porta negociada. Cookie exclusivo da instalação, HttpOnly/SameSite=Strict/Path=/; Secure=false apenas neste transporte loopback HTTP. Futura hospedagem exige revisão HTTPS/Secure=true. Validar Host e Origin exatos; rejeitar Origin null/externa em mutações; sem CORS amplo. Vincular sessão a shell_id e capacidade secreta de Shell enviada por canal autenticado, não URL/query.
- Backend aloca e mantém o socket 127.0.0.1:0; publica a porta efetivamente reservada via pipe. Bootstrap não escolhe porta por sondagem e posterior fechamento.
- shell detach ou perda do pipe/heartbeat por 15 s revoga sessão e interrompe seu acesso; heartbeat não renova atividade humana. Ao terminar última sessão, jobs privados entram WAITING após checkpoint, handles fecham e VRK/keys saem dos caches. Jobs e processo podem persistir bloqueados; novo login autorizado os retoma.
- Fechamento normal aguarda confirmação de detach, encerra WebView2 e remove profile quando handles forem liberados. Falha de remoção entra em fila de limpeza; profile nunca é reutilizado. Não prometer apagamento forense de RAM/disco; validar ausência de dados privados em persistência normal e no profile reaberto.
- Token de sessão, CSRF, capacidades e respostas privadas: no-store, nunca localStorage ou log. Cada Shell tem profile único; encerramento/crash não reabre sessão.

## 13. Invariantes financeiras e histórico
- Money API é string decimal canônica com duas casas na saída; entrada aceita uma ou duas casas (ou inteiro decimal), nunca separador de milhar/float/NaN. `OTHER` aceita valor com sinal; demais ajustes usam magnitude >0, DISCOUNT negativo e os demais positivos. net/effective nunca negativos nem menores que recebimento/desembolso líquido já aplicado; violação 409 sem alteração parcial.
- `CreditService.reverse` significa desfazer integralmente uma aplicação de crédito (credit_allocation_id), registrando credit_allocation_reversal e liberando crédito; não apaga saldo em dinheiro. Anular crédito de origem exige estornar o payment original.
- Estorno de payment é integral, único e transacional: invalida suas allocations, reverte aplicações ainda ativas do crédito originado e marca crédito REVERSED. Cobranças consumidoras reabrem no mesmo commit. Não cria segundo evento de caixa para crédito/aplicação. Concorrência com apply é serializada pelo mesmo lock/UoW.
- Eventos têm data civil própria: paid_on, applied_on, reversed_on/effective_on, created_at UTC. Reversão não antecede o evento original nem aplicações dependentes. Data futura não é recebimento efetivado. Recalcular relatórios por datas dos eventos, preservando visão histórica com as_of; não usar estado atual REVERSED para apagar receita de mês anterior.
- Duplicate warning: tentativa original que precisa confirmação retorna 409 DUPLICATE_CONFIRMATION_REQUIRED, sem gravar payment nem resposta definitiva de idempotência. Token de confirmação aleatório de uso único/5min vinculado a admin/dataset/cliente/valor/data; reenvio com mesma operation_id e token válido efetiva uma vez. Após sucesso, payload de negócio é comparado sem o token transitório e replay autorizado retorna resposta sanitizada original.
- Billing interval da assinatura 1..120 meses; âncora start_on, vencimento clamp no mês de competência. Catalog ITEM com intervalo null é cobrança única; itens recorrentes devem ter intervalo igual ao da assinatura, caso contrário dividir em assinaturas. Item one-time é emitido na primeira competência ativa da versão que o introduziu; edição de versão não o reemite se o item lógico não mudou. Persistir logical_item_id estável em subscription_items, fornecido pelo cliente em edição e gerado pelo servidor na inclusão; charge_items tem one_time bool. Índice UNIQUE(logical_item_id) WHERE one_time=1 impede reemissão de item único; itens recorrentes não entram nesse índice. Valores de itens únicos cancelados/estornados não causam reemissão automática: novo serviço é novo logical_item_id.
- Renovação NONE encerra em end_on; MANUAL exige nova versão com novo end_on; AUTO mantém continuidade por períodos de renewal_period_months = (end_on.year-start_on.year)*12 + end_on.month-start_on.month + 1 (meses civis inclusivos; mínimo 1), com novo end_on no último dia do mês final do período renovado, registrando evento idempotente sem alterar charges emitidas. end_on null significa vigência indeterminada. PAUSED pula competências, sem catch-up automático; CANCELLED/ENDED não voltam ACTIVE, novo contrato é outra assinatura. Transições futuras usam effective_month; alterações retroativas em competência já emitida recusam com 409 e orientam adjustment.
- Versionamento guarda signed_on/start_on/end_on/due_day/billing_interval_months/renewal_mode/note efetivos em subscription_versions, além dos itens; subscriptions conserva identidade e projeção atual. Status_events append-only é fonte do lifecycle por mês.
- RecurrenceService gera expenses.recurrence_id+competence único. Mudança/encerramento da recorrência só afeta emissões futuras; despesa emitida usa adjustments/reversals.
- categories são de despesas; categorias de catálogo têm tabela catalog_categories(id,name,active), CatalogInput.category passa a referenciar o nome normalizado único dessa tabela e catalog.category armazena esse mesmo nome canônico. Renomeação transacional e auditada; sem renomear categoria de despesa por engano.

## 14. Relatórios, dimensões e campos preservados
- Endereço usa somente postcode/street/number/complement/neighborhood/city/state; não criar sinônimos JSON em português. Telefones são list[str], primeiro é principal. ClientService.archive marca archived=true preservando status e histórico; cliente com vínculos ativos recusa.
- DTOs desta seção 3 são contratos de campos, a materializar como modelos Pydantic/dataclasses com validação; não copiar classes vazias como implementação. Tipos de retorno: entidade com id/revision, Page(items,total,page,page_size,revision), MutationResult(id,revision,operation_id) ou job_id para operação longa. Error: code,message,request_id,details sanitizados.
- ReportFilter: start/end inclusive, basis, as_of (default end), filtros opcionais client_id/plan_id/catalog_id/vehicle_id/fleet_id; filtros combinados por AND e validados quanto a propriedade. SearchResult: kind,id,label,detail sanitizado,route local. Ordenação allowlist server-side.
- Charge_items congelam fleet_id e dimensões válidas na emissão; expenses congelam fleet_id quando vínculo a veículo estiver presente. Transferência posterior não reatribui o passado.
- Relatórios por plano/item/veículo/frota distribuem centavos de adjustment e recebimentos alocados entre charge_items proporcionalmente aos line_cents, com resto estável por item_id e soma exata; se base total zero, recebimento positivo é impossível. Unallocated credit fica em grupo crédito não atribuído; aplicar crédito apenas reclassifica dimensão na data de aplicação, sem nova receita total. Reversão desfaz essas dimensões na data do evento.
- Gravar movimentos de classificação em financial_dimensions(source_kind,source_id,event_kind,event_on,charge_item_id,client_id,vehicle_id,fleet_id,catalog_id,amount_cents,operation_id); append-only, unicidade por fonte/evento/item. Grupo não atribuído usa dimensões nulas. Sem dupla contagem ao filtrar/grupar; atribuição por plano jamais inventa rateio de despesas gerais.
- Summary mantém campos da seção 8 e acrescenta recurring_revenue, by_client[], by_vehicle[], by_fleet[], by_catalog[], unassigned_revenue, general_expenses. recurring_revenue é soma mensal equivalente dos itens recorrentes vigentes, preço contratual/intervalo pela política de arredondamento; não soma equipamentos one-time nem representa caixa realizado.
- Resultado caixa = payments - payment_reversals - disbursements + disbursement_reversals nas datas do período; competência = soma gross_cents de charges emitidas + adjustments pelas respectivas competências - soma expected_cents de expenses + seus adjustments pelas respectivas competências, excluindo registros VOID na data de corte. Não somar ajustes novamente a net_cents/valor efetivo. VOID registra voided_on, permitindo reconhecer a existência anterior no corte histórico; voided_on não antecede emissão nem recebimentos/desembolsos revertidos. Saldos aberto/vencido são as_of, excluindo eventos posteriores. Margem = resultado/receita da base; receita zero retorna null.
- Mídia deduplica somente no mesmo dataset por SHA-256 do operacional reencodado + flags/versão da transformação; nunca deduplica através de Production/Test. Duas photos podem referenciar media; limpeza só remove arquivo sem referências ativas e fora de retenção/backup. Sanitização aplica a conteúdo operacional; original opt-in pode conter metadados e continua cifrado/admin-only, com indicação explícita.
- Audit before/after de cadastro usa allowlist de campos não sensíveis e hashes de campos pessoais; não conserva CPF, telefone, endereço ou nome bruto depois de anonimização. Histórico financeiro mantém IDs e valores. UI/audit export deve mostrar campo alterado, sem prometer recuperar PII apagada.
- PUBLIC publica nomes apenas ao salvar public_name com confirmação explícita na UI; vazio revoga. Dirty marker reside fora do DB privado, é durável antes do commit e fail-closed até rebuild da projeção. Falha pré-commit pode deixar dirty=true e 503 até login/rebuild; nunca servir cópia velha para evitar indisponibilidade.

## 15. Contratos nativos e release
- Host net48 usa APIs disponíveis nesse target. Explorer: ProcessStartInfo com FileName absoluto para explorer.exe do Windows, UseShellExecute=false e Arguments construído por helper único de quoting Windows; nunca cmd.exe/powershell.exe nem entrada shell arbitrária. Destinos enum Backups/Exports/Logs sob RootPaths, root local válida. Testar espaços, acentos, º e barra final. O contrato não usa ProcessStartInfo.ArgumentList.
- Runtime Python embeddable tem python313._pth preparado para app/Lib/site-packages locais; dependências instaladas em staging na engenharia, não pip em tempo de uso. Dependências transitivas, DLLs, UCRT/VC Runtime necessárias devem constar do lock/SBOM e ser comprovadas em Windows limpo, sem PATH da máquina de desenvolvimento.
- WebView2 SDK e Runtime são artefatos distintos: SDK pinado; Runtime mínimo compatível registrado e redistribuível offline provisionado após verificação de licença/hash. Ausência gera diagnóstico, não browser externo como aprovação.
- Portabilidade significa mover a raiz local; não rodar DB em UNC/SMB/pasta sincronizada. Names de environment/paths são lowercase production/test, inclusive UserData/Public/production/view.json.
- Versão 1.00.00.000 é lida de VERSION.json da release; current.json só aponta release + dataset ativo e sequência compatível. Ordenação por tupla de inteiros BA/ES/IN/SE; não comparação lexical.
- Update: adquirir maintenance e drenar writes/jobs, depois backup VALID do mesmo checkpoint, staging/migração, switch único de current.json para par release+dataset, verificação e ACCEPTED. Qualquer crash entre passos tem update journal persistente; nenhuma janela permite writes no candidato antes de ACCEPTED. Rollback pré-aceite não reverte AuthStore.
- Chave privada Ed25519 de release pertence à engenharia e nunca ao cliente. T01 define trust store público e chave de teste segregada; T15 exige assinatura real e pin de key_id, verificável também por Updater net48. Não usar API de .NET moderno inexistente sem biblioteca compatível pinada/testada. Chave produtiva deve ser gerada/controlada pelo proprietário antes da assinatura final; ausência bloqueia release final, não testes com chave de teste.
- Evidence/VerificationBundle de engenharia é separado do pacote de usuário final. Comandos native usam o Runtime do candidato com harness importável por caminhos locais explícitos e dependências de teste em pacote separado hashado. Testes não dependem de SDK/pytest instalados no cliente final para iniciar o produto.

## 16. Idempotência, gates e chamadas de serviço
- Ordem de mutação: autenticação/capacidade, ambiente e autorização atual, CSRF/Origin, procura de operation_id no escopo dataset/actor, comparação do payload de negócio, replay sanitizado; somente operação inédita verifica If-Match e executa UoW. Replay válido não falha só porque sua própria primeira gravação elevou revision. Outro actor não obtém resultado privado pela mesma chave.
- response_json de operations guarda apenas MutationResult(id,revision,operation_id) e metadados não pessoais; telas consultam estado atual por GET autorizado. Não persistir respostas antigas com PII que sobreviveriam à anonimização. Tickets/tokens transitórios não entram no log de replay.
- Métodos create/save(ctx,input,operation_id) retornam MutationResult; update/save de agregado existente incluem entity_id,expected_revision; archive/transfer/set_status/adjust/void/reverse incluem target_id,reason,expected_revision,operation_id e DTO/dataclass com campos específicos da seção correspondente. Métodos get/list/search/report são ctx + filtros. Login/session seguem seção12; não inventar actor/env no frontend.
- DTOs auxiliares a definir em src/ustracker/contracts.py antes do serviço consumidor: StatusChange(status,effective_month,reason), OwnershipTransfer(target_client_id,target_fleet_id,effective_on,reason), DueChange(due_on,reason), Reversal(reversed_on,reason), Disbursement(amount,paid_on,method), ExpenseAdjustment(amount_signed,competence,effective_on,reason), Recurrence(category_id,description,amount,day,start_month,end_month,active). Campos monetários usam Money e datas usam date. Todos processos longos retornam JobRef(job_id,state); leitura retorna JobProgress(job_id,state,completed,total,unit,message).
- Se o chamador de backup já possui maintenance (updater), passar um SnapshotContext validado para reutilizar o freeze; não readquirir lock incompatível nem liberar o lock do updater ao terminar a cópia. Mesmo checkpoint permanece congelado até ACCEPTED/rollback.
- Apenas Windows10 possui release_gate formal; a evidência de Windows11 adicional não é requisito de T02. A inexistência de ambiente para um teste nativo obrigatório do perfil formal é BLOCKED, independentemente da flag de linha de comando.
