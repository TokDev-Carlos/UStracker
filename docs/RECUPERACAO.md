# Recuperação e continuidade

1. Preserve `UserData` antes de qualquer intervenção manual.
2. Para restauração normal use um backup `.usbk` criado pelo próprio ambiente.
3. Recovery export (`.usre`) é separado de backup normal e é cifrado por passphrase
   externa; não armazene a passphrase junto do pacote.
4. Nunca copie um banco aberto para outra máquina como mecanismo de sincronização.
5. Em transferência de estação, somente uma estação deve permanecer escritora para um
   dataset/generation.
6. Em falha de atualização, o Updater mantém rollback dos arquivos substituídos; `UserData`
   e `Trust` são proibidos dentro de patches.
