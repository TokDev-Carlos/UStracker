# UStracker

Sistema de controle de **clientes, frotas e veículos, planos e assinaturas, financeiro, despesas e fiscal** para Windows 10/11 (x64).
Funciona no computador (local-first), guarda tudo cifrado e sincroniza entre vários computadores pela nuvem da empresa (Google Drive).

**Versão atual: 2.2.0**: veja [CHANGELOG.md](CHANGELOG.md) e [docs/NOVIDADES.md](docs/NOVIDADES.md).

## Instalar
1. Baixe **`UStracker_install_x64.exe`** na página [Releases](../../releases/latest).
2. Execute (pede permissão de administrador). Programa em `C:\Program Files\UStracker` (protegido), dados em `C:\ProgramData\UStracker\UserData`. O instalador já leva o programa, o Microsoft WebView2 e o endereço da nuvem da empresa; uma instalação antiga em `C:\UStracker` é migrada sozinha (os dados são copiados, nunca apagados).
3. Abra o UStracker e **ative o computador com o Adm Global**:
   - empresa que já usa: os dados chegam da nuvem;
   - primeiro computador: o Adm Global cria o **Administrador da empresa** (guardado na nuvem).
   Depois, cada pessoa entra com o próprio usuário.

Atualizações chegam pela nuvem (`updates/`). Desinstalar: **Manter dados** ou **Remover tudo** (com cópia antes em Documentos).

## Como é feito
```
UStracker.exe (Shell .NET + WebView2)
   └─ tela: frontend/ (HTML + módulos ES)
        └─ API local FastAPI em 127.0.0.1 (src/ustracker)
             ├─ banco SQLCipher (Real e Teste) + fotos/anexos AES-GCM
             ├─ acesso: Adm Global (ativação) + Administrador da empresa + usuários com pacotes (na nuvem)
             └─ nuvem: Apps Script + Google Drive (cloud/Code.gs)
                   └─ placa de direção assinada: placa.json (este repositório)
```
Detalhes em [docs/ARQUITETURA.md](docs/ARQUITETURA.md).

## Pastas
| Pasta | Conteúdo |
|---|---|
| [`src/`](src) | Backend Python (API, regras de negócio, banco, nuvem, acesso) |
| [`frontend/`](frontend) | Telas (sem framework, módulos ES) |
| [`host/`](host) | Executáveis Windows (.NET): Shell com WebView2, Bootstrap e Updater |
| [`cloud/`](cloud) | Script da nuvem (Google Apps Script) e simulador para testes |
| [`installer/`](installer) | Instalador NSIS (Program Files + ProgramData, migração, desinstalação) |
| [`docs/`](docs) | Manual, nuvem, recuperação, arquitetura e notas da versão |
| [`tests/`](tests) | Testes Python (unittest) e de tela (node:test) |
| [`tools/`](tools) | Publicar atualização, SBOM, empacotamento e versão |
| [`updates/`](updates) | Canal de atualização pela nuvem (assinado) |
| [`Trust/`](Trust) | Chave pública de atualização |
| `placa.json` | **Placa de direção** (onde estão os bancos na nuvem). Assinada; publicada pelo sistema. Não editar à mão. |

## Desenvolver
Requisitos: Python 3.13, Node 20+.
```bash
pip install -r requirements-package.txt
export PYTHONPATH=src:. USTRACKER_DEV_PLAINTEXT=1   # sem SQLCipher em desenvolvimento
python -m unittest discover -s tests -p 'test_*.py'
node --test tests/*.test.mjs
python -m ustracker                                  # sobe a API local
```
Regras do projeto: testes RED→GREEN antes de qualquer mudança, operações multi-tabela em transação única, nada é apagado sem Lixeira/backup.

## Branches
- **`main`**: versão oficial e estável. Só entra o que está testado.
- **`Dev`**: arquivo histórico completo (versões 1.x, rascunhos, ramos antigos) e área de trabalho. Veja `HISTORICO.md` no `Dev`.

## Licença
Proprietário: © 2026 CRJ. Veja [LICENSE.txt](LICENSE.txt) e [NOTICE.txt](NOTICE.txt).
