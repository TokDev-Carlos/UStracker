# PROMPT MESTRE — REINÍCIO LIMPO, AUDITORIA E CRIAÇÃO INTEGRAL DO USTRACKER

## AUTORIDADE

Você é a IA executora responsável por criar, testar, homologar e entregar o sistema **UStracker 1.00.00.000**.

A autoridade documental vigente é exclusivamente:

- `PECSUS_UStracker_1_2_1_EXECUCAO.zip`
- `SCRIPT_MESTRE_EXECUCAO_IA_1_2_1.txt`
- conteúdo interno `PECSUS_1_2_1`

Não use PECSUS 1.2, 1.3 ou qualquer revisão anterior/posterior criada durante tentativas intermediárias.

Não altere requisitos para fazer testes passarem.

Não declare PASS sem evidência real.

Não confunda validação documental do PECSUS com homologação funcional do produto.

---

# 1. OBJETIVO

Recomeçar a engenharia do UStracker de forma limpa e controlada e executar o PECSUS 1.2.1 de T01 até T18.

O produto deverá:

- funcionar em Windows 10 e Windows 11 x64;
- usar **Windows 10 22H2 x64 como ambiente formal de homologação atual do proprietário**;
- não exigir Windows 11 para liberar T01, T02, T16, T18 ou entrega homologada no Windows 10;
- manter compatibilidade real com Windows 11;
- usar Windows 11 posteriormente como plataforma adicional de verificação, sem travar a criação no Windows 10.

A homologação atual será feita no Windows 10.

---

# 2. AMBIENTE REAL JÁ VERIFICADO

A máquina atual do proprietário foi comprovada como:

```text
Windows 10 Pro
Version: 10.0.19045
Build: 19045
Arquitetura: x64

Windows PowerShell:
5.1.19041.6456

Python:
3.13.15
AMD64 / 64-bit

.NET Framework:
4.8.09037
Release: 533325

.NET SDK:
10.0.400
MSBuild 18.9.6
win-x64
```

O diretório de trabalho utilizado é:

```text
C:\Users\Carlos Alberto\Downloads\UStracker_Projeto_1_2_1
```

A existência de espaços em:

```text
Carlos Alberto
```

é intencional e deve ser suportada.

Não mude o projeto para um caminho artificialmente simples apenas para esconder defeitos de path handling.

---

# 3. PRIMEIRA REGRA: NÃO CONTINUAR REMENDANDO A ENGENHARIA ATUAL

A pasta atual:

```text
UStracker_Engenharia
```

foi submetida a várias alterações manuais durante diagnóstico.

Ela NÃO deve ser tratada como fonte confiável de implementação.

Primeira ação:

1. Preservar a pasta atual integralmente como arquivo histórico, por exemplo:

```text
UStracker_Engenharia_ARCHIVE_DIAGNOSTICO_<UTC>
```

2. Calcular SHA-256 do arquivo/pasta arquivada ou de um ZIP dela.

3. Não deletar esse histórico.

4. Criar uma nova:

```text
UStracker_Engenharia
```

limpa.

5. Extrair novamente ou recuperar somente as fontes documentais originais do PECSUS 1.2.1.

6. Nenhum `PASS`, checkpoint, `requirements.lock`, `native-artifacts.lock.json`, wheelhouse, NuGet feed, `Dist`, `Evidence` ou artefato de build anterior deve ser promovido automaticamente para a nova engenharia.

Tudo deve ser recriado e comprovado.

---

# 4. O QUE PODE SER APROVEITADO DAS TENTATIVAS ANTERIORES

As tentativas anteriores são apenas evidência de diagnóstico.

Elas identificaram problemas que a nova implementação deve evitar.

Não copie os patches cegamente.

Reimplemente corretamente a partir dos contratos do PECSUS.

Foram descobertos os seguintes pontos críticos:

### A. PowerShell 5.1

Os scripts:

```text
tools\resolve_python_lock.ps1
tools\finalize_native_lock.ps1
tools\build.ps1
```

tinham uma construção incompatível com PowerShell 5.1:

```powershell
[string]$Root = (Split-Path -Parent $PSScriptRoot)
```

Durante parameter binding, `$PSScriptRoot` pode ainda não estar disponível.

Na implementação limpa:

- parâmetros devem usar default neutro;
- a raiz deve ser resolvida após `param()`;
- usar `$PSScriptRoot` e fallback seguro para `$MyInvocation.MyCommand.Path`;
- validar root vazio;
- suportar caminhos com espaços e caracteres Unicode.

Todos os `.ps1` devem ser parseados explicitamente pelo parser do PowerShell antes de uso.

---

### B. Scripts devem ser idempotentes

`finalize_native_lock.ps1` anteriormente tentou:

```text
Copy-Item origem → destino
```

quando origem e destino eram o mesmo arquivo.

Resultado:

```text
Não pode substituir o item ... por ele mesmo.
```

Na implementação limpa:

- normalize os dois paths;
- compare `SourceFull` e `DestinationFull`;
- se forem iguais, não copie;
- registre `ALREADY_IN_PLACE`;
- não considere isso erro.

A mesma regra deve ser aplicada a qualquer staging/cache.

---

### C. Gate T01 deve ser fail-closed

Foi identificado que versões iniciais do harness poderiam considerar:

```text
cases=[]
```

como:

```text
required_pass=true
exit_code=0
```

Isso é proibido.

O verificador deve rejeitar:

- lista vazia de casos;
- caso obrigatório ausente;
- IDs duplicados;
- caso desconhecido;
- PASS sem evidência;
- evidência de outro candidato;
- resultado de outro perfil;
- evidência vencida após mudança de código/artefato.

Nunca usar `all([])` como base suficiente para aprovação.

---

### D. Detecção do Windows deve ser estrita

Para perfil:

```text
win10_22h2
```

exigir:

```text
Windows
10.0
build 19045
x64
```

Não aceitar como Win10 22H2:

```text
19044
Windows 7
x86
```

Windows 11 deve ser reconhecido separadamente.

Windows 11 não bloqueia homologação Windows 10.

---

### E. Bootstrap precisa resolver a release ativa corretamente

Antes de iniciar Runtime/backend:

```text
candidate root
    ↓
current.json
    ↓
Releases\<versão>
    ↓
VERSION.json
    ↓
Runtime
    ↓
WebView2Runtime
```

Validar:

- path relativo;
- sem traversal;
- release existente;
- `VERSION.json`;
- versão coerente;
- Runtime existente;
- WebView2 existente.

Não iniciar um Runtime solto na raiz.

---

### F. Handshake C# ↔ Python

O backend usa nomes de wire como:

```json
{
  "port": 0,
  "nonce": "...",
  "pid": 123,
  "product": "UStracker"
}
```

O C# deve interpretar exatamente esses campos.

Não depender de serialização implícita incompatível entre:

```text
pid
ProcessId
```

ou atributos que o serializer selecionado não respeita.

Teste o framing real:

```text
length prefix
UTF-8 JSON
wire names exatos
PID esperado
nonce esperado
produto esperado
```

---

### G. Portabilidade C01 deve ser prova real

Não basta criar objetos `Path`.

O candidato real deverá executar em:

```text
C:\Teste UStracker ç\
```

e depois ser movido para:

```text
D:\Movido\
```

e executar novamente.

Se não existir volume D:, o harness pode criar temporariamente um drive de homologação com mecanismo Windows apropriado, desde que:

- fique documentado;
- seja removido ao final;
- não masque path absoluto hardcoded.

---

### H. C08 precisa de host realmente limpo

Máquina de build pode ter:

- Python;
- .NET SDK;
- MSBuild;
- Node;
- ferramentas de engenharia.

C08 deve ser executado em outro Windows 10 22H2 x64 limpo, VM ou estação equivalente.

O host limpo não pode depender de:

```text
Python global
.NET SDK
MSBuild
Node
pip
npm
```

A evidência C08 deve conter fingerprint SHA-256 do candidato.

Uma evidência C08 só é válida se:

```text
fingerprint(candidate testado)
==
fingerprint(candidate atualmente homologado)
```

Alterar um único arquivo invalida C08.

---

### I. SQLCipher deve ser real

Fixado pelo PECSUS:

```text
sqlcipher3 0.6.2
cp313
win_amd64
```

Hash conhecido:

```text
9dc959ff792228c6df836cfd3667c713ae13e6e18dc2905c9d5666558606e832
```

Além do hash:

- importar biblioteca real;
- provar `cipher_version`;
- provar banco criptografado;
- provar que chave errada falha;
- provar que SQLite plaintext não abre o banco protegido.

Não substituir por SQLite comum.

---

### J. Python Runtime

Fixado:

```text
CPython 3.13.15 x64 embeddable
```

Hash esperado do pacote embeddable:

```text
d1f04d990aee1253d8569e8e5104e30fa9f5fa830899f14843448872d936a2cf
```

Todas as dependências transitivas destinadas ao Runtime devem ser:

- resolvidas em Windows;
- compatíveis com cp313/win_amd64;
- armazenadas em wheelhouse;
- versionadas;
- hash-locked;
- instaláveis com:

```text
--no-index
--require-hashes
```

Não reutilizar o `requirements.lock` antigo sem regenerá-lo.

A tentativa anterior gerou 17 wheels corretamente; isso é apenas referência histórica, não evidência reutilizável.

---

### K. WebView2 SDK e Runtime

SDK definido pelo projeto:

```text
Microsoft.Web.WebView2
1.0.4191.47
```

O Runtime Fixed Version disponível na máquina do proprietário é:

```text
Microsoft.WebView2.FixedVersionRuntime.153.0.4234.32.x64.cab
```

SHA-256 já observado:

```text
2cb653a74426f0aa802c2396775c6bc674fd662d5396bd677f47bfa6e12eba9c
```

NÃO aceite esse valor cegamente.

Recalcule o hash no arquivo real.

Verifique nas fontes oficiais Microsoft:

- compatibilidade SDK ↔ Runtime;
- distribuição Fixed Version;
- arquitetura x64;
- requisitos Windows 10.

Se a versão 153 for usada, piná-la explicitamente.

Não manter uma versão 152 antiga hardcoded em testes/scripts/locks.

---

### L. WebView2 Fixed Version no Windows 10

Foi identificado requisito específico de WebView2 Fixed Version recente em aplicação Win32 unpackaged.

Antes de implementar, confirme novamente na documentação oficial Microsoft.

Se aplicável, garantir permissões necessárias ao diretório do runtime para:

```text
ALL APPLICATION PACKAGES
ALL RESTRICTED APPLICATION PACKAGES
```

Implementação deve ser:

- idempotente;
- somente quando aplicável;
- sem exigir alteração desnecessária no Windows 11;
- testada;
- auditável.

Não copie automaticamente o patch anterior sem validar o desenho.

---

### M. .NET Framework Reference Assemblies

O build `net48` usando SDK-style project tentou resolver:

```text
Microsoft.NETFramework.ReferenceAssemblies
```

e falhou porque `NuGet.Config` permitia somente feed local.

Essa situação precisa ser resolvida corretamente.

IMPORTANTE:

Uma tentativa manual de baixar:

```text
Microsoft.NETFramework.ReferenceAssemblies 1.0.3
```

via URL construída manualmente falhou com:

```text
BlobNotFound
```

e, pior, o script continuou e criou:

```text
dotnet-referenceassemblies.lock.json
DOTNET_REFERENCE_PACKAGES=LOCKED
```

mesmo com `$LockItems` incompleto/vazio.

Esse arquivo é INVALIDADO.

Nunca reutilizá-lo.

Na implementação limpa:

1. identificar exatamente qual versão o SDK/projeto solicita;
2. confirmar no NuGet oficial;
3. obter o pacote pela API/CLI oficial correta;
4. obter também qualquer dependência como:

```text
Microsoft.NETFramework.ReferenceAssemblies.net48
```

quando aplicável;
5. validar integridade;
6. validar assinatura quando suportado;
7. gravar SHA-256;
8. somente gerar lock se todos os downloads/verificações tiverem concluído;
9. qualquer falha deve abortar ANTES da criação do lock;
10. nunca imprimir `LOCKED` após erro anterior.

Use comportamento transacional:

```text
download temporário
→ validar todos
→ montar lock temporário
→ validar lock
→ promover atomicamente
```

---

### N. NuGet local

A filosofia permanece:

```text
restore controlado
feed local
pacotes pinados
hashes conhecidos
```

Mas não inventar URLs.

Se uma URL falhar:

- pesquisar a fonte oficial;
- entender a API correta;
- corrigir a causa;
- não encadear patches sobre patches.

O build deve usar:

```text
NuGet.Config controlado
Artifacts\NuGetFeed
```

e posteriormente:

```text
dotnet build --no-restore
```

após restore validado.

---

### O. SBOM e trust store

T01 deve preparar:

```text
SBOM SPDX
manifestos
hashes
trust store
chave pública TEST_ONLY
```

Chave privada de assinatura não deve entrar no candidato.

Assinatura produtiva dependerá da chave controlada pelo proprietário.

---

# 5. REGRA ANTI-CASCATA DE ERROS

Este projeto já demonstrou que pequenos patches sequenciais podem gerar uma cadeia de defeitos.

Portanto adote obrigatoriamente:

```text
1º erro:
investigar causa-raiz

2º erro no mesmo componente:
revisar componente inteiro

3º erro correlacionado:
PARAR patches incrementais
reconstruir aquele componente a partir do contrato
```

Nunca continuar corrigindo sintomas indefinidamente.

Se um script PowerShell apresentar múltiplos defeitos estruturais, reescreva o script inteiro com testes em vez de acrescentar novos patches.

Se um lock ficar inconsistente, recrie-o do zero.

Se um build parcial gerar artefatos, não os trate como candidatos válidos.

---

# 6. NÃO USAR PATCHES MANUAIS FRAGMENTADOS NO CONSOLE

Evite instruções ao proprietário do tipo:

```text
cole esta metade
agora cole outro if
agora acrescente else
agora substitua outra linha
```

Isso já causou erro de parsing interativo:

```text
else : O termo 'else' não é reconhecido...
```

A IA executora deve editar os arquivos diretamente usando ferramentas de arquivos/código.

Quando necessário gerar patch:

- aplicar atomicamente;
- mostrar diff;
- executar parser;
- rodar teste dirigido;
- somente então continuar.

O proprietário não deve funcionar como editor manual do código produzido pela IA.

---

# 7. AUDITORIA ANTES DE ESCREVER CÓDIGO

Antes de implementar T01:

Leia integralmente:

```text
00_LEIA_PRIMEIRO.md
PONTO_DE_PARADA.json
01_ESPECIFICACAO.md
02_CONTRATOS.md
TAREFAS.json
CASOS_ACEITE.json
03_EXECUCAO_LINEAR.md
04_VERIFICACAO_E_ENTREGA.md
05_OPERACAO_E_CONTINUIDADE.md
MATRIZ_REQUISITOS.csv
MATRIZ_ESCOPO_HISTORICO.csv
```

Execute:

```powershell
python tools\validar_plano.py --root .
```

A referência observada anteriormente foi:

```text
PECSUS-1.2.1
36 requisitos
18 tarefas
145 casos
144 obrigatórios
250 históricos
```

Recalcule; não apenas repita esses números.

---

# 8. CRIAR GIT LIMPO

Na nova engenharia:

```text
git init
branch de engenharia
commit inicial documental
```

Não trabalhar diretamente sobre estado não versionado.

Antes de cada marco:

```text
git status
git diff
```

Depois de cada etapa aprovada:

```text
commit
tag/checkpoint quando pertinente
```

Preservar alterações do proprietário.

---

# 9. TDD OBRIGATÓRIO

Para cada comportamento novo:

```text
RED
teste falha pela razão correta

GREEN
implementação mínima

REFACTOR
melhoria sem mudança funcional

VERIFY
suíte afetada + regressão
```

Não escrever código primeiro e criar teste depois.

Testes estáticos de substring podem complementar, mas não substituir comportamento real.

---

# 10. ESTRUTURA MÍNIMA T01

A implementação limpa deve incluir, conforme o PECSUS:

```text
versionamento BA/ES/IN/SE
paths portáteis
current.json
VERSION.json
Bootstrap
Shell WPF
Updater
backend Python
health endpoint
named pipe autenticado
shutdown cooperativo
Runtime embeddable
SQLCipher
WebView2 Fixed Version
locks
SBOM
trust store
harness verify.py
Evidence
checkpoint
```

Projetos C#:

```text
.NET Framework 4.8
x64
WPF quando aplicável
```

Scripts Windows:

```text
PowerShell 5.1
```

Python:

```text
tipado
PEP8
3.13.15
```

---

# 11. TESTES T01

Os casos relevantes incluem:

```text
T01-C01
T01-C02
T01-C03
T01-C04
T01-C05
T01-C06
T01-C07
T01-C08
T01-C09
```

Para homologação Win10:

```text
C01 PASS
C02 PASS
C03 PASS
C04 PASS
C06 PASS
C07 PASS
C08 PASS
C09 PASS
```

C05 refere-se à compatibilidade Windows 11 e não bloqueia a homologação atual no Windows 10.

Nunca converter `BLOCKED` em `PASS`.

---

# 12. CANDIDATO

O build deve produzir:

```text
Dist\Candidate
```

O candidato deve conter, quando requerido:

```text
UStracker.exe
UStracker.Updater.exe
current.json
SBOM.spdx.json
Trust\
Releases\1.00.00.000\
    VERSION.json
    Runtime\
    WebView2Runtime\
    Shell/backend/assets necessários
```

O candidato deve ser portátil.

Não depender de SDK/Python/Node globais.

---

# 13. BUILD HOST ≠ CLEAN HOST

Separar formalmente:

```text
MÁQUINA DE ENGENHARIA
→ compila

MÁQUINA LIMPA
→ comprova portabilidade
```

A presença de SDK na máquina de build não é defeito.

A presença necessária de SDK na máquina limpa é defeito.

---

# 14. EVIDÊNCIAS

Para cada gate registrar:

```text
comando literal
cwd
UTC
exit code
stdout
stderr
Windows build
arquitetura
Python/runtime
hashes
candidate fingerprint
casos executados
resultado
```

Estrutura:

```text
Evidence\<Txx>\
Estado\PONTO_DE_PARADA.json
```

Checkpoint deve ser gravado atomicamente.

Não sobrescrever o último checkpoint válido sem preservar anterior.

---

# 15. LOCKS DEVEM SER TRANSACIONAIS

Nenhum script pode fazer:

```text
erro
→ continuar
→ escrever lock
→ imprimir LOCKED
```

Fluxo obrigatório:

```text
resolver
→ baixar
→ validar
→ verificar todos
→ gerar arquivo temporário
→ validar arquivo temporário
→ promover atomicamente
→ somente então declarar LOCKED
```

Se qualquer artefato falhar:

```text
exit != 0
nenhum lock novo promovido
```

---

# 16. PESQUISA DE DEPENDÊNCIAS

Sempre que:

- versão atual;
- URL de download;
- API NuGet;
- WebView2;
- .NET;
- Python;
- package metadata;
- compatibilidade;

puder ter mudado, consulte fonte oficial atual antes de implementar.

Prioridade:

```text
Microsoft
Python.org
PyPI
NuGet oficial
documentação do fornecedor
```

Não construir URLs por suposição se uma API oficial puder fornecer a informação.

---

# 17. NÃO MODIFICAR O PECSUS PARA FAZER O CÓDIGO CABER

O PECSUS 1.2.1 é autoridade.

Se encontrar contradição verdadeira:

1. registrar;
2. apontar exatamente arquivos/casos afetados;
3. não alterar silenciosamente;
4. manter versão original;
5. somente criar errata/revisão se indispensável e claramente separada.

Não misturar autoridade documental com artefatos de engenharia.

---

# 18. SCRIPT MESTRE

O `SCRIPT_MESTRE_EXECUCAO_IA_1_2_1.txt` também é autoridade operacional.

Existe um resíduo conhecido:

```text
PECSUS_1_2
```

onde a pasta física atual é:

```text
PECSUS_1_2_1
```

Trate isso como errata operacional de path, não como mudança de arquitetura.

Preserve o documento original.

---

# 19. EXECUÇÃO AUTÔNOMA

Não peça autorização ao proprietário para cada arquivo.

Execute autonomamente:

```text
auditoria
TDD
implementação
testes
build
gates
evidências
checkpoint
```

Solicite intervenção somente quando houver:

- privilégio administrativo;
- acesso externo que a IA não possa realizar;
- download manual inevitável;
- máquina limpa/VM;
- chave produtiva;
- decisão funcional realmente não definida no PECSUS.

Não transforme o proprietário em operador de comandos que você mesmo poderia executar.

---

# 20. PONTO DE PARADA

Se T01 não passar:

```text
não iniciar T02
```

Entregar:

```text
estado real
blocker
causa
evidência
arquivos modificados
hashes
próximo comando/ação
```

Se T01 passar integralmente:

```text
checkpoint T01 PASS
→ iniciar T02
```

Depois seguir linearmente até T18.

---

# 21. T01 → T18

Depois da fundação:

seguir integralmente:

```text
T01
↓
T02
↓
...
↓
T18
```

Para cada tarefa:

```text
ler contratos/casos
→ RED
→ implementação
→ revisão function-by-function
→ testes
→ integração do módulo
→ gate
→ evidência
→ checkpoint
→ próxima tarefa
```

Ao final:

```text
verify.py --integration
release_gate.py
```

Não declarar produto pronto enquanto qualquer gate obrigatório estiver:

```text
FAIL
BLOCKED
NAO_EXECUTADO
```

quando aplicável ao perfil formal.

---

# 22. INVARIANTES DO PRODUTO

Preservar integralmente os invariantes do PECSUS, incluindo:

```text
PUBLIC allowlist
backend authorization
dados privados nunca enviados para blur
CSRF/Origin
dirty marker fail-closed

3 ADMIN individuais
bootstrap controlado
reset = enrollment

Production/Test isolados
AuthStore compartilhado conforme contrato

dinheiro em centavos/Decimal
nunca float
pagamentos/créditos/estornos transacionais

uma estação escritora
transferência autenticada
sem falsa promessa de revogação offline

backup autenticado
AAD/framing corretos
restore/recovery separados

update:
QUIESCED
BACKED_UP
STAGED
MIGRATED
SWITCHED
VERIFIED
ACCEPTED

rollback sem apagar lançamentos posteriores

integrações adiadas = disabled/501
sem rede falsa

sem chaves reais em logs/release
```

---

# 23. ENTREGA FINAL

Somente depois de T18 e gates completos entregar:

```text
UStracker 1.00.00.000 portátil
Source.zip
hashes
build reproduzível
Runtime
WebView2
SBOM
licenças
manifestos
documentação
backup/recovery/update/rollback
matriz de rastreabilidade
Evidence
checkpoint COMPLETE
AJUSTES_FUTUROS.log somente para não bloqueantes
```

---

# 24. SUA PRIMEIRA AÇÃO AGORA

NÃO continue o build atual.

NÃO continue corrigindo os scripts manualmente existentes.

NÃO confie nos locks criados durante as tentativas.

Faça:

```text
1. Inventário do diretório atual.
2. Hashes.
3. Arquivar UStracker_Engenharia atual.
4. Localizar PECSUS 1.2.1 e Script Mestre originais.
5. Validar documentalmente.
6. Criar UStracker_Engenharia limpa.
7. Criar Git limpo.
8. Ler T01 completa.
9. Auditar os scripts/contratos antes de implementar.
10. Criar testes dirigidos para todos os defeitos históricos listados neste prompt.
11. Implementar T01 limpa.
12. Rodar suíte unitária.
13. Resolver dependências e locks transacionalmente.
14. Build.
15. Candidate.
16. Gate nativo Win10.
17. C08 em host limpo.
18. Fechar T01 somente após PASS real.
19. Prosseguir T02→T18.
```

Antes de escrever código, apresente ao proprietário apenas um resumo curto contendo:

```text
AUTORIDADE ENCONTRADA
AMBIENTE CONFIRMADO
ARQUIVO HISTÓRICO CRIADO
NOVA ENGENHARIA
STATUS PECSUS
T01 INICIADA
```

Depois execute autonomamente.

## REGRA FINAL

O objetivo não é “fazer o teste ficar verde”.

O objetivo é produzir um **UStracker funcional, reproduzível, auditável e realmente homologado no Windows 10 22H2 x64**, mantendo compatibilidade com Windows 11 x64.

Quando um erro aparecer:

```text
pare
identifique causa-raiz
corrija a origem
teste a correção
teste regressão
continue
```

Não acumule remendos.

Não esconda falhas.

Não invente evidências.

Não declare conclusão prematura.

**COMECE AGORA PELO ARQUIVAMENTO CONTROLADO DO AMBIENTE ATUAL E PELA RECRIAÇÃO LIMPA DA ENGENHARIA A PARTIR DO PECSUS 1.2.1.**