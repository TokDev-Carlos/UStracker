# PECSUS 1.2.1 — plano vigente para criação do UStracker

Estado: revisão documental consolidada; produto não implementado/homologado neste pacote.
Próxima ação: T01/G1 no perfil formal Windows 10 22H2 x64. T02 só inicia após T01 PASS.

## Usar com outra IA
1. Anexar PECSUS_UStracker_1_2_1_EXECUCAO.zip e extrair uma única vez.
2. Enviar o conteúdo integral de SCRIPT_MESTRE_EXECUCAO_IA.txt como instrução à IA.
3. A IA valida o pacote, prepara raiz de engenharia separada e executa T01→T18 com evidências.
4. Sem ambiente nativo necessário, a IA registra o bloqueio e o ponto de retomada; não converte testes não executados em aprovação.

## Autoridade e leitura
- 01_ESPECIFICACAO.md: requisitos/escopo.
- 02_CONTRATOS.md: nomes, formatos, regras e interfaces canônicos; se houver novo conflito real, corrigir sua causa e propagar matrizes/casos antes de implementar.
- MATRIZ_ESCOPO_HISTORICO.csv: decisões dos 250 itens históricos.
- TAREFAS.json: fonte única dos passos e arquivos de T01–T18.
- CASOS_ACEITE.json: catálogo de cenários; resultados reais ficam na engenharia.
- 03_EXECUCAO_LINEAR.md: visualização gerada de TAREFAS.json; não editar isoladamente.
- 04_VERIFICACAO_E_ENTREGA.md e 05_OPERACAO_E_CONTINUIDADE.md: gates/execução/recuperação.
- PONTO_DE_PARADA.json: semente de retomada; copiar para Estado/ na engenharia.
- FONTES_E_DECISOES.md: origens verificáveis e consulta histórica opcional.
- REVISAO_DOCUMENTAL.md e VALIDACAO_DOCUMENTAL.json: evidências somente documentais.
- PECSUS_COMPLETO_1_2_1.txt: agregação gerada para leitura contínua, não segunda autoridade.

Primeira leitura: este arquivo, checkpoint, especificação, contratos, matriz histórica e T01/casos. Depois ler integralmente verificação/operação e executar por etapa. Fontes históricas não precisam ser relidas a cada ciclo.

## Verificação local do pacote
Em Python 3.10 ou superior, a partir da raiz extraída:

```text
python tools/validar_plano.py --root .
```

Exit code 0 significa integridade e coerência documental conferidas; não significa produto testado. Falha exige resolver o motivo sem regenerar hash para mascarar corrupção.

## Arquivo histórico
As revisões 1.0/1.1 e seu conteúdo redundante ficam em ARQUIVO_HISTORICO_ATE_1_1, na mesma pasta plano do Drive. Os ZIPs originais preservam fontes, auditorias anteriores e cópias duplicadas. Não há exclusão permanente. O pacote 1.2 contém somente o material vigente necessário à execução; referências arquiteturais consolidadas estão em FONTES_E_DECISOES.md.
