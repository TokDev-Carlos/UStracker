# Revisão documental — PECSUS 1.2.1

Alteração exclusiva solicitada pelo proprietário: Windows 10 como base de homologação; funcionamento em Windows 10 e 11 x64.

- Perfil obrigatório/padrão de homologação: win10_22h2, em T01/T16/T18 e nos comandos do script mestre.
- Windows11 é plataforma de funcionamento do mesmo produto, com testes adicionais quando disponível. Sua ausência não bloqueia avanço nem entrega homologada no Windows10; falha funcional conhecida deve ser corrigida.
- Sem bloqueio de inicialização por ser Windows10 ou Windows11. Sem PASS fictício para plataforma não testada.
- Especificação, contratos, etapas, casos, matrizes, gerador, validador, checkpoint e script mestre alinhados à mesma política.
- Preservados os 36 requisitos, 18 tarefas, 145 casos (144 obrigatórios e 1 ensaio adicional agora Windows11) e 250 itens históricos. IDs preservados.
- Sem mudança em tecnologia, versões de dependências, arquitetura, regras de domínio, segurança, financeiro, backup, atualização ou ordem das tarefas.
- Documentos derivados e manifesto regenerados. VALIDACAO_DOCUMENTAL.json contém a evidência desta correção; testes do produto não executados aqui.

Ao retomar implementação existente, conservar evidências não afetadas e ajustar somente política de plataforma. Bloqueio anterior por falta de Windows11 não apaga o trabalho feito; a prova nativa pendente passa a ser executada no Windows10 do proprietário.
