# updates — canal de atualização

Lido por todas as instalações do UStracker (ao abrir e a cada 3 horas).

- `update.json`: versão, nível (`normal` = instala ao fechar; `critical` = obrigatória), notas, SHA-256 e tamanho do pacote. Assinado (Ed25519); a chave pública está em `Trust/update_public_key.pem`.
- `UStracker-<versão>.usup`: pacote assinado com o programa inteiro (nunca `UserData` nem `Trust`).

Publicar: `python tools/publish_update.py --version X --level normal|critical --notes "..." --key <update_signing_key.pem>` (chave privada só no cofre `Chaves-Tokens/UStracker/`). Mantém só a versão mais recente; as anteriores ficam no histórico do Git.
