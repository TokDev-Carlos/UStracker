# UStracker 1.00.01.000

UStracker é um sistema Windows local-first para controle administrativo e financeiro de clientes de rastreamento, veículos/frotas, planos e itens, assinaturas, cobranças, recebimentos/créditos, despesas, acompanhamento fiscal manual, mídia, dashboard, relatórios, backup, recovery e administração.

## Download e instalação

Abra **Releases** e baixe `UStracker_1.00.01.000_win-x64.zip`.

1. Extraia o ZIP inteiro para uma pasta local, por exemplo `C:\UStracker`.
2. Execute `UStracker.exe`.
3. No primeiro acesso, crie o Administrador 1 e conclua os Administradores 2 e 3 com os tickets de uso único.
4. Use **Production** para dados reais e **Test** para laboratório isolado.

O pacote leva CPython 3.13.15 x64 embeddable, SQLCipher, dependências Python, WPF/.NET Framework 4.8 e o Evergreen Standalone Installer x64 do WebView2 para instalação offline. Não exige Python, Node, Visual Studio ou SDK no computador final.

**Plataforma-alvo:** Windows 10 22H2 x64 como base do projeto e Windows 11 x64 pela mesma arquitetura. x86/ARM/Linux/macOS não são clientes V1.

## Segurança e continuidade

- exatamente três slots administrativos individualizados;
- senha com scrypt N=131072/r=8/p=1 e VRK envelopada por administrador;
- chaves independentes para banco/mídia em Production e Test;
- SQLCipher obrigatório no runtime distribuído;
- sessões em memória com expiração por inatividade e tempo absoluto;
- backend somente em `127.0.0.1`, com Host/Origin/CSRF e correlation ID;
- mutações administrativas usam `X-Operation-ID` para bloqueio de repetição;
- audit trail encadeado por SHA-256 e verificável pela interface;
- dinheiro persistido em centavos inteiros e cálculos com Decimal;
- fotos reencodadas/normalizadas e cifradas com AES-GCM;
- backup `.usbk` cifrado, manual/automático diário, retenção configurável e restore validado;
- recovery `.usre` cifrado por passphrase externa contendo Auth, Production, Test, mídia e projeção pública;
- até três estações por dataset e somente a estação escritora pode alterar Production;
- transferência explícita desarma a escritora de origem antes da exportação do pacote;
- patches `.usup` assinados Ed25519, com validação de manifesto, hashes, staging, journal e rollback de arquivos.

## Módulos disponíveis

Dashboard; Clientes; Frotas; Veículos; histórico/transferência de propriedade; Catálogo; histórico de preço; Assinaturas; Cobranças; ajustes manuais; Recebimentos; Créditos; Estornos; Despesas; Desembolsos; Recorrência; Fiscal manual; Busca global; Fotos; Branding; CSV/XLSX; Backups; Recovery; Estações; Auditoria; ambiente Test e Updater assinado.

Google Drive, emissão fiscal oficial, rastreamento externo, WhatsApp/e-mail automático e hospedagem permanecem explicitamente desativados nesta V1. Tentativas de ação nessas integrações retornam HTTP 501; o sistema não simula integração inexistente.

## Branches

- `main`: produto e pipeline de distribuição.
- `Dev`: baseline documental PECSUS 1.2.1 preservado.

## Desenvolvimento

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
$env:PYTHONPATH = "$PWD\src"
$env:USTRACKER_DEV_PLAINTEXT = "1"
.\.venv\Scripts\python.exe -m pytest -q
```

O workflow `build-release.yml` roda testes, compileall, sintaxe do frontend, builds .NET Framework 4.8 x64, smoke do runtime com SQLCipher, release gate, snapshot do fonte e publicação da Release.
