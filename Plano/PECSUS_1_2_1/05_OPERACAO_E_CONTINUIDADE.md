# Operação, continuidade, recovery e atualização — PECSUS 1.2.1

## 1. Launcher/lifecycle
```text
BOOTSTRAP -> CHECK_ROOT -> CHECK_RELEASE -> CHECK_RUNTIME -> LOCK_INSTANCE
-> START/REUSE_BACKEND -> PIPE_HANDSHAKE -> PUBLIC_UI
```
- Segundo launch reutiliza supervisor/backend identificado por mutex+pipe+nonce; abre Shell pública.
- Minimize mantém Shell/sessão.
- X = `DETACH_SHELL`: revoga sessão daquela Shell, fecha WebView/profile; limpeza após liberação dos handles. Backend continua; após última sessão, jobs privados pausam WAITING e chaves/DBs são fechados. Crash de Shell é detectado por pipe/heartbeat conforme contrato.
- Encerrar Sistema = ADMIN_REQUEST -> DRAINING -> CHECKPOINT_JOBS -> FLUSH_JOURNALS -> CLOSE_PRIVATE_DB -> STOP_BACKEND -> STOP_SHELL -> EXIT.
- Recovery/startup reconcilia file_journal/maintenance/update antes de liberar writes.

## 2. Dataset/writer
`datasets.generation` aumenta em transfer/recovery; guardar maior geração local fora do dataset restaurável. Escrita exige station_id == writer_station_id e dataset ACTIVE. TRANSFERRED retorna 423. Nenhum timer concede writer. Clone offline não pode ser revogado remotamente; recovery exige retirada administrativa de cópias antigas.

## 3. DB + arquivos
DB commit e rename de arquivo não são uma única transação nativa; `file_journal` é o protocolo de ponte. FINALIZED só existe depois de target hash confirmado. Stage e target ficam em roots allowlist do ambiente.

## 4. Backup
Formato, captura consistente, framing/AAD e restauração sem regressão de AuthStore estão em `02_CONTRATOS.md`, seção 9. Backup automático é disparado no primeiro acesso ADMIN do dia quando houve mudança desde último VALID. Manual disponível sempre que não houver operação crítica concorrente.

Retenção default: 7 daily + 4 weekly + 3 monthly; pré-update válido não é removido até existir sucessor aceito. Nunca remover o último VALID.

## 5. Recovery export
Não é backup automático. Admin escolhe passphrase forte localmente; aplicação não grava/passa ao log/chat. Import testa em root isolada. Sem passphrase correta, recuperação é impossível por desenho.

## 6. Update
```text
RECEIVED
-> VALIDATED      assinatura/manifest/paths/limits
-> QUIESCED       writes bloqueadas/jobs checkpoint
-> BACKED_UP      backup VALID
-> STAGED         release candidata isolada
-> MIGRATED       cópia dataset migrada
-> SWITCHED       current.json atômico
-> VERIFIED       health/db/auth/public smoke
-> ACCEPTED       liberar writes
```
Falha pré-ACCEPTED usa checkpoint inteiro. Depois de ACCEPTED, rollback binário não pode rebaixar schema de modo destrutivo nem apagar lançamentos novos.

## 7. PUBLIC projection
PUBLIC lê apenas `UserData/Public/production/view.json`/Assets. `public_dirty`=true -> 503 até rebuild. Restore/update que altere dados publicados marca dirty e reconstrói antes de servir.

## 8. Ajustes futuros
`AJUSTES_FUTUROS.log` começa vazio. Registro mínimo: id, versão, arquivo/função, reprodução, esperado/observado, impacto, workaround, blocking=false, evidência, target_version. Se blocking=true, o release gate rejeita.

## 9. Dados e LGPD operacional
O produto implementa minimização, PUBLIC allowlist, anonimização, soft-delete financeiro e retenção configurável. Antes de dados reais, o controlador configura política organizacional de retenção/consentimento/incidente. O sistema não declara conformidade jurídica automática.

## 10. Ponto de parada
Após cada task: atualizar Estado/PONTO_DE_PARADA.json na raiz de engenharia com status, evidence, artifact hashes, next_task, blockers, invalidated_cases. A semente do pacote documental fica imutável. Se ambiente indisponível, deixar BLOCKED com comando/resultado e continuar somente em trabalhos independentes que não finjam aprovação do gate.
