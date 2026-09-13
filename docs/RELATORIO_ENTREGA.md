# Relatório de entrega — 1.00.01.000

A branch `main` contém a implementação executável e o pipeline de geração do pacote Windows x64. A branch `Dev` preserva o baseline PECSUS 1.2.1.

Esta revisão fecha as lacunas funcionais identificadas após a primeira Release: recovery passa a carregar os datasets reais Production/Test; escrita Production é vinculada à estação escritora; frotas e transferência de veículo estão operáveis; créditos/estornos, ajustes, desembolsos, recorrência, fotos, restore, branding, Recovery, estações e auditoria estão expostos na UI; backups automáticos/retenção, idempotência, revisão otimista, correlation ID e verificação da cadeia de auditoria foram adicionados; o updater registra o protocolo completo de estados e valida o switch por hash.

O GitHub Actions valida código/testes/build/pacote em runner Windows. Homologação física específica em Windows 10 22H2 build 19045 deve ser registrada na máquina de homologação, porque Windows Server do runner não deve ser rotulado como essa evidência física.
