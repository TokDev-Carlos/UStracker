# UStracker 1.00.00.000

Sistema Windows local-first para controle de clientes de rastreamento, veículos/frotas,
planos e itens, assinaturas, cobranças, recebimentos/créditos, despesas, acompanhamento
fiscal manual, mídia, dashboard, relatórios, backup e administração.

## Download para uso

Abra **Releases** deste repositório e baixe:

`UStracker_1.00.00.000_win-x64.zip`

1. Extraia o ZIP inteiro em uma pasta local, por exemplo `C:\UStracker`.
2. Execute `UStracker.exe`.
3. No primeiro acesso, crie o Administrador 1 e use os dois tickets de enrollment para
   cadastrar os Administradores 2 e 3.
4. Use `Production` para dados reais e `Test` para laboratório isolado.

O pacote de usuário inclui CPython 3.13.15 x64 embeddable e dependências. Não exige
Python, Node, Visual Studio ou SDK no computador final. Quando o WebView2 Runtime não
estiver instalado, o Shell usa o bootstrapper Microsoft incluído em `Redist`.

**Plataforma:** Windows 10 22H2 x64 como base do projeto; Windows 11 x64 suportado pela
mesma arquitetura. x86/ARM/Linux/macOS não são clientes V1.

## Segurança e dados

- Exatamente três slots administrativos individualizados.
- Senhas derivam KEK por scrypt; a VRK é envelopada por administrador.
- Production e Test usam chaves de banco e mídia distintas.
- O runtime de produção exige SQLCipher real; SQLite plaintext só é permitido quando a
  variável de engenharia `USTRACKER_DEV_PLAINTEXT=1` é definida explicitamente.
- Sessões ficam em memória e expiram por inatividade/tempo absoluto.
- API escuta somente em `127.0.0.1` e aplica Host/Origin/CSRF.
- Dados públicos vêm de projeção allowlist; a página pública não abre o banco privado.
- Dinheiro é persistido em centavos inteiros e calculado sem `float` monetário.
- Fotos operacionais são reencodadas sem metadados e cifradas em AES-GCM.
- Backups locais são cifrados e validados antes de uso.
- Patches usam manifesto assinado Ed25519; a chave privada de assinatura não faz parte
  do repositório nem do pacote distribuído.

## Módulos V1

Dashboard; Clientes; Veículos/Frotas; Catálogo; Assinaturas; Cobranças; Recebimentos e
Créditos; Despesas; Fiscal manual; Busca global; CSV/XLSX; Fotos; Branding; Test;
Backups; Estações; Updater assinado; integrações futuras explicitamente desativadas.

Drive, emissão fiscal oficial, rastreamento externo, WhatsApp/e-mail automático,
hospedagem e PDF oficial permanecem `PREPARED_DISABLED`/HTTP 501 nesta V1.

## Desenvolvimento

A linha documental/engenharia anterior foi preservada na branch `Dev`. A branch `main`
contém o produto reconstruído e é a origem do build distribuível.

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
$env:PYTHONPATH = "$PWD\src"
$env:USTRACKER_DEV_PLAINTEXT = "1"
.\.venv\Scripts\python.exe -m pytest -q
```

O workflow `build-release.yml` compila os hosts .NET Framework 4.8 x64, monta o runtime
embeddable, verifica os hashes normativos do CPython/sqlcipher3, executa o release gate
e publica o ZIP em GitHub Releases.
