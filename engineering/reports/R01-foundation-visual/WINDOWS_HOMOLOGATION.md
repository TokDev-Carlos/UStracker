# R01 — Gate Windows e homologação visual

Este roteiro valida o **PONTO-DE-PARADA-1**. Ele não autoriza R02 e não deve ser executado dentro da instalação ativa `C:\UStracker`.

## 1. Workspace seguro

Extraia/clone este pacote em uma pasta de trabalho, por exemplo:

```powershell
C:\UStracker-Work\R01
```

Não copie `UserData` da instalação ativa para o workspace.

## 2. Preflight

No Windows PowerShell 5.1 ou superior:

```powershell
Set-Location 'C:\UStracker-Work\R01'
powershell -ExecutionPolicy Bypass -File .\engineering\tools\Invoke-Preflight.ps1 -RepoRoot $PWD
```

Esperado: `PREFLIGHT=PASS`.

## 3. Verificação automatizada

```powershell
powershell -ExecutionPolicy Bypass -File .\engineering\tools\Invoke-Verification.ps1 `
  -ChangesetId R01-foundation-visual `
  -RepoRoot $PWD
```

Para R01, o resultado correto após todos os checks automáticos é:

```text
VERIFICATION=PASS_AUTOMATED_AWAITING_MANUAL
```

O processo encerra com código `3` de propósito. O changeset **não** é alterado para `VERIFIED`, porque ainda faltam os gates humanos abaixo.

Se houver `FAIL`, não prossiga para homologação visual. Consulte o `verification.json` e os logs em `engineering\reports\runtime\...`.

## 4. Pacote somente para homologação

Depois de `PASS_AUTOMATED_AWAITING_MANUAL`, monte uma cópia separada:

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\package.ps1 `
  -RepoRoot $PWD `
  -OutDir (Join-Path $PWD 'test-output')
```

Extraia o ZIP gerado para uma pasta descartável, nunca sobre `C:\UStracker`.

## 5. Smoke de ícone e atalho

O Bootstrap cria/atualiza `UStracker.lnk` na Área de Trabalho. Para não redirecionar o atalho de uma instalação real durante a homologação, faça este smoke em **usuário Windows de teste, VM ou máquina de homologação**.

Verifique em duas inicializações consecutivas:

- existe exatamente um `UStracker.lnk`;
- o target aponta para o `UStracker.exe` da cópia de homologação;
- não surge atalho duplicado;
- o executável Bootstrap tem ícone UStracker;
- a janela WebView2/Shell tem ícone UStracker;
- favicon/logo padrão aparecem antes de branding customizado.

## 6. Homologação visual no ambiente Teste

Na aplicação, selecione o ambiente **Teste** e confirme:

- cabeçalho superior permanece fixo ao rolar;
- logo UStracker à esquerda;
- Ajuda, usuário/função, Sair e Encerrar à direita;
- `PRODUÇÃO · ESCRITORA` não aparece no cabeçalho;
- menu lateral rola independentemente abaixo do cabeçalho;
- foco, hover, bordas e sombras permanecem suaves e legíveis;
- valores monetários aparecem como `R$ 0,00` / `R$ 1.234,56`;
- campos monetários são texto digitável, sem setas de incremento;
- digitação de moeda não reposiciona o cursor a cada tecla;
- datas seguem `dd/mm/aaaa` e data-hora o padrão definido no R01;
- telas existentes de Dashboard, Compras Diretas, Assinaturas e Ficha do Cliente continuam funcionais;
- em janela estreita, o layout não perde acesso ao menu/conteúdo.

## 7. Aprovação

Somente depois dos itens 2–6 aprovados, registre o resultado e retorne ao fluxo de engenharia para promoção do changeset de `IN_PROGRESS` para `VERIFIED`. O candidate gate deve continuar bloqueando antes dessa promoção.
