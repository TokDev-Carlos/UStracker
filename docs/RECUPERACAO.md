# Recuperação e continuidade — UStracker 1.00.01.000

1. Backups normais `.usbk` são por ambiente e cifrados pela VRK.
2. Recovery `.usre` inclui `UserData/Auth`, `UserData/Production`, `UserData/Test`, `UserData/Media` e `UserData/Public`.
3. `UserData/State` não é transferido: cada computador recebe identidade de estação própria.
4. A importação de recovery substitui somente os grupos recuperáveis de `UserData`; não remove binários do produto nem a pasta de backups local.
5. Nunca copie banco aberto para outra máquina como sincronização.
6. Production permite somente uma estação escritora por dataset/generation.
7. Para transferir, a origem deve preparar a transferência: ela perde `is_writer` antes do `.usre` ser exportado. O pacote leva `transfer_generation`; a nova estação assume essa geração após a importação.
8. Se a exportação de transferência falhar, a estação de origem recupera a função escritora.
9. Patches nunca podem substituir `UserData` nem `Trust`.
10. O updater registra os estados RECEIVED → VALIDATED → QUIESCED → BACKED_UP → STAGED → MIGRATED → SWITCHED → VERIFIED → ACCEPTED.
11. Se a estação escritora for perdida, o administrador pode usar takeover de emergência com confirmação explícita e motivo; todas as cópias antigas devem ser retiradas de operação antes de continuar.
