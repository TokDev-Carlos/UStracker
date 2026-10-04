# Validação humana — candidato acelerado R13–R23

Estado: **IMPLEMENTADO, NÃO VALIDADO**. A versão oficial permanece `1.003` até a aprovação.

## Roteiro básico

1. Abrir o sistema em ambiente **Test**.
2. Confirmar que todos os menus abrem sem recarregar a aplicação.
3. Cadastrar um cliente, empresa, frota ou veículo e uma assinatura mensal.
4. Registrar um recebimento e uma despesa; conferir os seis indicadores da Visão Geral.
5. Alternar o período entre `Geral` e um ano disponível.
6. Enviar e remover uma foto; confirmar que a seleção do arquivo já inicia o envio.
7. Abrir `Sistema`: a aba `Administração` deve ser a inicial e `Desenvolvimento` deve conter runtime, auditoria, estações e diagnósticos.
8. Conferir visualmente ícones, alinhamento, nomes longos e tabelas.
9. Encerrar e abrir novamente; confirmar persistência dos dados de Test.

## Limites deste checkpoint

- Nenhuma suíte de testes foi executada após a implementação, por decisão explícita de aceleração.
- Nenhum arquivo foi promovido para `C:\UStracker\System` e nenhum dado real foi alterado.
- `version.md`, `VERSION.json` e `current.json` não foram promovidos.
- Atualização transacional, backup/restore e operação Production devem voltar ao fluxo normal de verificação depois desta validação básica.

## Ajustes já identificados durante a validação

Os requisitos de Receita Geral/Previsão do Mês, detalhamento de veículos, integração completa
Cliente–Comercial e identificadores lógicos compactos foram adicionados ao fluxo oficial em
`docs/FLUXO_AJUSTES_POS_VALIDACAO.md`. Eles não fazem parte do binário deste candidato.
