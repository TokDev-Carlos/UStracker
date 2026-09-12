# ORIENTAÇÃO DE EXECUÇÃO — CODEX / USTRACKER

**Projeto:** UStracker  
**Autoridade:** PECSUS 1.2.1  
**Produto-alvo:** UStracker 1.00.00.000  
**Ambiente formal atual de homologação:** Windows 10 22H2 x64  
**Compatibilidade adicional:** Windows 11 x64  
**Objetivo deste arquivo:** orientar o Codex a executar o projeto em múltiplas sessões controladas, sem consumir contexto de forma desnecessária e sem perder continuidade.

---

# 1. CONFIGURAÇÃO RECOMENDADA DO CODEX

## Modelo

Usar preferencialmente:

```text
GPT-6 Astra
```

quando disponível no Codex.

Fallback:

```text
GPT-5.6 Sol
```

## Esforço de raciocínio

Padrão:

```text
Medium
```

Subir temporariamente para:

```text
High
```

somente quando houver:

- causa-raiz difícil;
- falha recorrente no mesmo componente;
- decisão arquitetural;
- segurança;
- persistência;
- regras financeiras;
- backup/restore;
- updater/rollback;
- integração completa;
- release gate;
- conflito entre contrato, código e evidência.

Não usar esforço máximo continuamente.

O projeto é longo, procedural e auditável. O objetivo é preservar capacidade para concluir T01→T18, e não gastar raciocínio máximo em operações mecânicas.

---

# 2. POLÍTICA DE USO DE CONTEXTO

O projeto NÃO deve ser executado em uma única sessão.

Usar a seguinte política:

```text
0%–50%
Executar normalmente.

50%–55%
Não iniciar uma nova tarefa grande.
Concluir a unidade lógica em andamento.

55%–60%
Fechar testes da unidade atual.
Atualizar evidências.
Atualizar checkpoint.
Registrar git status/diff.
Criar commit quando aplicável.
Registrar próxima ação exata.

~60%
ENCERRAR A SESSÃO DE EXECUÇÃO.
Não continuar consumindo contexto para iniciar outro módulo.
Retomar em nova sessão usando o checkpoint.
```

O limite de 60% é uma regra operacional aproximada, não uma medição matemática exata.

Nunca sacrificar:

- testes;
- segurança;
- evidências;
- validação;
- revisão;
- integridade do checkpoint;

apenas para economizar contexto.

---

# 3. O QUE LER EM CADA NOVA SESSÃO

Não reler o projeto inteiro em toda sessão.

## Leitura obrigatória

```text
AGENTS.md
Estado/PONTO_DE_PARADA.json
tarefa atual do TAREFAS.json
casos associados no CASOS_ACEITE.json
contratos associados
última evidência válida
git status
git log recente
```

## Ler somente quando necessário

```text
01_ESPECIFICACAO.md
02_CONTRATOS.md
03_EXECUCAO_LINEAR.md
04_VERIFICACAO_E_ENTREGA.md
05_OPERACAO_E_CONTINUIDADE.md
MATRIZ_REQUISITOS.csv
MATRIZ_ESCOPO_HISTORICO.csv
```

Não reler logs históricos completos se o checkpoint atual já resumir o que importa.

---

# 4. DIVISÃO RECOMENDADA DE SESSÕES

Esta divisão é orientativa.

```text
Sessão 1
Auditoria inicial + engenharia limpa + T01

Sessão 2
Fechamento/homologação T01 + T02/T03

Sessão 3
T04/T05

Sessão 4
T06/T07

Sessão 5
T08/T09

Sessão 6
T10/T11

Sessão 7
T12/T13

Sessão 8
T14/T15

Sessão 9
T16

Sessão 10
T17

Sessão 11
T18 + integração completa

Sessão 12
Correções finais + release gate + entrega
```

Isso NÃO significa que 12 sessões sejam obrigatórias.

Se houver contexto e segurança suficientes:

- juntar tarefas pequenas;
- separar tarefas grandes;
- criar sessão adicional quando necessário.

T01, T16 e T18 podem consumir uma sessão inteira ou mais.

---

# 5. AUTORIDADE DO PROJETO

A ordem de autoridade é:

```text
1. PECSUS_UStracker_1_2_1_EXECUCAO.zip
2. SCRIPT_MESTRE_EXECUCAO_IA_1_2_1.txt
3. Prompt Mestre — Reinício Integral e Execução do UStracker.md
4. USTRACKER_CODEX_HANDOFF_20260912.zip
5. AGENTS.md da nova engenharia
6. Estado/PONTO_DE_PARADA.json
```

Em caso de conflito:

```text
PECSUS 1.2.1 prevalece.
```

Não usar como autoridade:

```text
PECSUS 1.2
PECSUS 1.3
engenharias antigas
locks antigos
Evidence antiga
candidates parciais
patches manuais históricos
```

---

# 6. COMANDO / PROMPT INICIAL PARA O CODEX

Usar o texto abaixo como comando inicial da primeira sessão.

```text
Use o pacote USTRACKER_CODEX_HANDOFF_20260912.zip como contexto de transição e o PECSUS 1.2.1 como autoridade absoluta.

Leia primeiro:

1. 00_COMECE_AQUI.md
2. AUTORIDADE/Prompt Mestre — Reinício Integral e Execução do UStracker.md
3. AUTORIDADE/SCRIPT_MESTRE_EXECUCAO_IA_1_2_1.txt
4. PECSUS 1.2.1: somente os documentos necessários para T01 e seus contratos/casos associados.

Não continue a engenharia antiga.

Arquive qualquer UStracker_Engenharia existente como histórico de diagnóstico e crie uma nova UStracker_Engenharia limpa.

Inicialize Git limpo.

Antes de escrever código:

- valide documentalmente o PECSUS 1.2.1;
- confirme Windows 10 22H2 x64;
- leia T01 completa;
- leia todos os contratos e casos associados a T01;
- transforme os defeitos históricos do handoff em testes de regressão;
- crie AGENTS.md com as regras permanentes do projeto;
- crie Estado/PONTO_DE_PARADA.json inicial.

Depois execute T01 por TDD:

RED → GREEN → REFACTOR → VERIFY.

Não aplique patches fragmentados no console.
Edite os arquivos diretamente.
Não declare PASS sem evidência real.
Não reutilize locks, evidências ou candidate anteriores como aprovação.

Windows 10 22H2 x64 é a base formal de homologação atual.
Windows 11 x64 é suportado, mas sua ausência não bloqueia a homologação no Windows 10.

Use GPT-6 Astra com esforço Medium por padrão, se disponível.
Use High somente para problemas críticos ou difíceis.

Política de contexto:
- até ~50%: executar normalmente;
- 50–55%: terminar a unidade lógica atual;
- 55–60%: atualizar evidências, checkpoint e Git;
- ~60%: não iniciar nova tarefa grande; encerrar a sessão de forma recuperável.

Se T01 não estiver integralmente PASS, NÃO iniciar T02.

Comece agora.

Antes de alterar código, mostre somente:

AUTORIDADE ENCONTRADA
AMBIENTE CONFIRMADO
ARQUIVO HISTÓRICO CRIADO
NOVA ENGENHARIA CRIADA
STATUS DO PECSUS
TAREFA ATUAL
PRÓXIMA AÇÃO EXATA

Depois prossiga autonomamente.
```

---

# 7. OBJETIVO DA PRIMEIRA SESSÃO

Objetivo mínimo:

```text
Criar uma engenharia limpa, auditável e reproduzível.
```

Objetivo ideal:

```text
Fechar T01 integralmente em Windows 10 22H2 x64.
```

A primeira sessão deve tentar produzir:

```text
UStracker_Engenharia/
AGENTS.md
Estado/PONTO_DE_PARADA.json
Git inicializado
testes de regressão
estrutura T01
locks válidos
Dist/Candidate
Evidence/T01
```

Se houver tempo/contexto e T01 ficar PASS, iniciar T02 somente após checkpoint.

---

# 8. OBJETIVO DE CADA TAREFA T01→T18

Para cada tarefa:

```text
1. Ler tarefa.
2. Ler contratos.
3. Ler casos.
4. Confirmar PASS da anterior.
5. Criar teste RED.
6. Implementar.
7. Obter GREEN.
8. Refatorar.
9. Revisar funções públicas.
10. Rodar testes afetados.
11. Rodar gate da tarefa.
12. Registrar Evidence.
13. Atualizar checkpoint.
14. Commit.
15. Só então avançar.
```

---

# 9. REGRA ANTI-CASCATA DE ERROS

Se aparecer erro:

```text
Erro 1:
investigar causa-raiz.

Erro 2 no mesmo componente:
revisar o componente inteiro.

Erro 3 correlacionado:
PARAR patches incrementais.
Reconstruir o componente a partir do contrato.
```

Não acumular correções manuais.

Não continuar apenas porque “falta pouco”.

---

# 10. CRITÉRIO DE PARADA DA SESSÃO

Encerrar a sessão imediatamente de forma controlada quando ocorrer qualquer condição abaixo:

## Contexto

```text
aproximadamente 60% do contexto útil
```

## Bloqueio técnico real

Exemplos:

```text
dependência externa indisponível
clean host não disponível
chave produtiva necessária
acesso administrativo necessário
contradição documental real
falha repetida que exige revisão arquitetural
```

## Antes do encerramento

Obrigatoriamente registrar:

```text
Estado/PONTO_DE_PARADA.json
```

com:

```text
última tarefa aprovada
tarefa atual
casos PASS
casos FAIL
casos BLOCKED
arquivos alterados
commits
hashes
dependências
blockers
próxima ação exata
comando exato de retomada
```

Também executar:

```text
git status
git diff
git log -n 5
```

Criar commit/checkpoint quando o estado for consistente.

---

# 11. COMANDO DE RETOMADA DE NOVA SESSÃO

Usar como prompt inicial das sessões seguintes:

```text
Retome o projeto UStracker usando o PECSUS 1.2.1 como autoridade.

Não reinicie o projeto.

Leia primeiro:

1. AGENTS.md
2. Estado/PONTO_DE_PARADA.json
3. última Evidence válida da tarefa atual
4. tarefa atual em TAREFAS.json
5. contratos e casos associados
6. git status
7. git log recente

Confirme que o workspace corresponde ao checkpoint.

Não reexecute tarefas já aprovadas, exceto quando uma mudança posterior tiver invalidado suas evidências.

Continue exatamente da próxima ação registrada no checkpoint.

Use esforço Medium por padrão.
Use High somente se a próxima ação envolver causa-raiz difícil, segurança, persistência, updater/rollback, integração ou release gate.

Política de contexto:
encerre novamente em aproximadamente 60%, após atualizar checkpoint e evidências.

Não avance para a próxima tarefa enquanto o gate atual não estiver PASS.
```

---

# 12. CRITÉRIO DE TÉRMINO DE UMA TAREFA

Uma tarefa só termina quando:

```text
todos os casos obrigatórios aplicáveis = PASS
gate = exit code 0
evidências = válidas
checkpoint = atualizado
git = consistente
nenhum blocker obrigatório permanece
```

Se qualquer item estiver:

```text
FAIL
BLOCKED
NAO_EXECUTADO
```

quando obrigatório, a tarefa NÃO terminou.

---

# 13. CRITÉRIO DE TÉRMINO DA T01

T01 somente pode ser declarada concluída quando no Windows 10 formal:

```text
T01-C01 PASS
T01-C02 PASS
T01-C03 PASS
T01-C04 PASS
T01-C06 PASS
T01-C07 PASS
T01-C08 PASS
T01-C09 PASS

required_pass = true
exit_code = 0
```

C05 / Windows 11 não bloqueia a homologação atual em Windows 10.

---

# 14. CRITÉRIO DE TÉRMINO DO PROJETO

O projeto somente termina quando:

```text
T01 PASS
T02 PASS
T03 PASS
...
T18 PASS
```

e também:

```text
verify.py --integration = PASS
release_gate.py = PASS
```

Além disso:

- candidate final congelado;
- Windows 10 homologado;
- compatibilidade Windows 11 tratada conforme PECSUS;
- nenhum blocker obrigatório;
- Source.zip;
- build reproduzível;
- Runtime empacotado;
- WebView2 empacotado;
- SQLCipher validado;
- SBOM;
- licenças;
- hashes;
- manifestos;
- documentação operacional;
- backup/recovery/update/rollback;
- matriz de rastreabilidade;
- Evidence completa;
- checkpoint `COMPLETE`.

---

# 15. OBJETIVO FINAL

O resultado esperado é:

```text
UStracker 1.00.00.000
```

funcional, portátil, reproduzível, auditável e homologado.

Não basta:

```text
compilar
abrir janela
passar teste unitário
gerar EXE
```

É necessário comprovar o produto integralmente.

---

# 16. DEFINIÇÃO DE 100%

Considerar:

```text
0%   = somente plano
~5%  = estado atual de preparação/histórico
10%+ = T01 homologada
...
100% = T18 + integração + release gate + entrega final
```

Nunca aumentar artificialmente a porcentagem porque documentação ou testes isolados passaram.

O progresso deve refletir produto funcional comprovado.

---

# 17. REGRA FINAL DE EXECUÇÃO

```text
AUTORIDADE
→ TAREFA
→ TESTE RED
→ IMPLEMENTAÇÃO
→ GREEN
→ INTEGRAÇÃO
→ GATE
→ EVIDÊNCIA
→ CHECKPOINT
→ COMMIT
→ PRÓXIMA TAREFA
```

Sempre.

Se houver dúvida entre:

```text
continuar rápido
```

e:

```text
preservar integridade
```

preservar integridade.

O Codex deve terminar cada sessão deixando o projeto em um estado que outra sessão consiga retomar sem depender da memória da sessão anterior.
