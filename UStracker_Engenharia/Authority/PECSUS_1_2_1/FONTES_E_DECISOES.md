# Correção de plataforma 1.2.1

Decisão vigente do proprietário: Windows10 é base de homologação; funcionamento em Windows10/11. Esta correção altera exclusivamente perfis de plataforma e referências derivadas da revisão 1.2. Evidências de publicação das dependências abaixo foram herdadas, sem mudança nos artefatos fixados.

# Fontes e decisões — PECSUS 1.2.1

## Origem e autoridade
Revisão solicitada pelo proprietário em 12/09/2026: alinhar integralmente o plano, arquivar versões substituídas e preparar roteiro de execução por outra IA. A revisão parte do ZIP PECSUS_UStracker_1_1_PRONTO_PARA_EXECUCAO.zip e conserva os 36 requisitos, 18 tarefas e 250 itens históricos; casos adicionais fecham lacunas observadas.

Autoridade: instrução atual do proprietário → especificação/contratos/matriz histórica 1.2 → tarefas/casos/matriz de requisitos 1.2 → documentos gerados → histórico somente para consulta. Não misturar contratos 1.0/1.1 com a execução vigente. Contratos incompletos encontrados durante implementação são resolvidos com revisão rastreável, sem improvisar silenciosamente a regra de negócio.

## Dependências verificadas em páginas primárias nesta revisão
- Python 3.13.15 embeddable x64: publicação e SHA-256 esperado d1f04d990aee1253d8569e8e5104e30fa9f5fa830899f14843448872d936a2cf conferidos na página oficial: https://www.python.org/downloads/release/python-31315/
- sqlcipher3-0.6.2-cp313-cp313-win_amd64.whl: arquivo e SHA-256 esperado 9dc959ff792228c6df836cfd3667c713ae13e6e18dc2905c9d5666558606e832 conferidos na página do publicador: https://pypi.org/project/sqlcipher3/0.6.2/
- Microsoft.Web.WebView2 1.0.4191.47: SDK e compatibilidade net48 declarada no pacote: https://www.nuget.org/packages/Microsoft.Web.WebView2/1.0.4191.47
- API ArgumentList documentada para .NET moderno: https://learn.microsoft.com/en-us/dotnet/api/system.diagnostics.processstartinfo.argumentlist?view=net-10.0 . O contrato net48 escolhe Arguments com quoting e teste nativo; nenhuma compatibilidade é inferida apenas pela semelhança de nomes.

Essas conferências são de metadados publicados. Binários não foram executados nem homologados nesta revisão. T01 baixa artefatos das origens canônicas, confere hash e proveniência disponível (não inventa assinatura ausente), registra licenças/DLLs e executa PRAGMA cipher_version e Host real. Hash publicado de wheel prova correspondência ao artefato do publicador, não segurança absoluta da supply chain.

## Reaproveitamento arquitetural já consolidado
- Automação de Artes: RootPaths portátil, staging/commit, checkpoint de jobs, backup e diagnóstico. Criar implementação própria e testada do UStracker. Não copiar Corel/PDF/COD/bairros ou painel monolítico.
- ASCALPI: separação domínio/API/Host, UnitOfWork/repository/file journal/audit, autoridade de versão, separação Sistema/UserData, update/rollback. Não copiar domínio logístico/SMB/Tailscale/RemoteAdmin.
- Nenhum snapshot antigo é dependência de build. Se a executora optar por reusar código real de uma referência, recuperar arquivo específico do histórico, registrar origem/hash/licença e adaptar com testes; não executar instaladores/scripts legados para inspecionar.

## Arquivo rastreável
Na pasta Projeto UStracker/UStracker/plano/ARQUIVO_HISTORICO_ATE_1_1:
- PECSUS_UStracker_1_0.zip — plano substituído.
- PECSUS_COMPLETO_1_0.txt — cópia agregada substituída.
- PECSUS_UStracker_1_1_PRONTO_PARA_EXECUCAO.zip — revisão anterior integral, incluindo fontes/, auditoria/, historico/ e docs/superpowers/plans duplicado.

A matriz de 250 itens e o contrato consolidado continuam no pacote ativo. As pastas documentos e snapshots do projeto não foram removidas, pois são fontes arquiteturais de consulta e estão fora da limpeza da pasta plano.
