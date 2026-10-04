# UStracker

Sistema de controle de **clientes, frotas e veículos, planos e assinaturas, financeiro, despesas e fiscal** para Windows 10/11 (x64).
Funciona no computador (local-first), guarda tudo cifrado e sincroniza entre vários computadores pela nuvem da empresa (Google Drive).

**Versão atual: 2.0.0 (Release 2)**: veja [CHANGELOG.md](CHANGELOG.md) e [docs/RELEASE_2.0.0.md](docs/RELEASE_2.0.0.md).

## Instalar
1. Baixe **`UStracker_install_x64.exe`** na página [Releases](../../releases/latest).
2. Execute e siga as telas (pasta sugerida `C:\UStracker`). O instalador já leva o programa, o Microsoft WebView2 e o endereço da nuvem da empresa.
3. Abra o UStracker:
   - empresa que já usa: entre com **usuário e senha**; os dados chegam sozinhos;
   - primeiro computador: cadastre o **Administrador 1**.

Atualizar = executar o instalador novo por cima. A pasta `UserData` (os dados) nunca é apagada.

## Como é feito
```
UStracker.exe (Shell .NET + WebView2)
   └─ tela: frontend/ (HTML + módulos ES)
        └─ API local FastAPI em 127.0.0.1 (src/ustracker)
             ├─ banco SQLCipher (Real e Teste) + fotos/anexos AES-GCM
             ├─ acesso: Administradores (1..3) + usuários com pacotes
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
| [`installer/`](installer) | Script NSIS do instalador único |
| [`docs/`](docs) | Manual, nuvem, recuperação, arquitetura e notas da versão |
| [`tests/`](tests) | Testes Python (unittest) e de tela (node:test) |
| [`tools/`](tools) | SBOM, empacotamento e sincronização de versão |
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
