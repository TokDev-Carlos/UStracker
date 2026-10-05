# src/ustracker — backend

API local (FastAPI) e todas as regras de negócio. Ponto de entrada: `python -m ustracker` (`__main__.py`).

| Módulo | Papel |
|---|---|
| `server.py` | Rotas `/api/v1/*`, CSRF, sessão, permissões, vez de gravar |
| `auth.py` · `access.py` · `crypto.py` | Administradores, usuários, pacotes, chaves |
| `db.py` · `repository.py` | SQLCipher, schema, migrações |
| `services.py` · `clients.py` · `mobility*.py` · `catalog.py` · `commercial.py` · `billing.py` · `finance.py` · `expenses.py` | Domínio |
| `trash.py` | Lixeira de 14 dias |
| `cloud.py` · `station.py` · `placa.py` | Nuvem, Servidores, placa de direção |
| `adm_global.py` | Adm Global (Token Mestre, passe de 1 dia, pergunta de segurança) |
| `factory_reset.py` | "Zerar tudo" interno (uma vez) |
| `backup.py` · `recovery.py` · `update.py` · `apply_update.py` | Backup, recuperação, atualização assinada |
| `reports.py` · `public_projection.py` | Relatórios e vitrine pública da tela de login |
| `versioning.py` | Versão (`version.md` → `VERSION.json`) |
