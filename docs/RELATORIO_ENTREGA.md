# Relatório de entrega — 1.00.00.000

A branch `main` contém a implementação V1 executável e o pipeline de geração do pacote
Windows x64. A branch `Dev` preserva o baseline documental PECSUS 1.2.1 que originou o
produto.

O build de release é reproduzido pelo GitHub Actions em runner Windows e gera o ZIP
portátil, snapshot de código e hashes SHA-256. Homologação formal específica em Windows
10 22H2 build 19045 continua sendo uma propriedade do ambiente onde o pacote é executado;
um runner Windows Server não deve ser rotulado como essa homologação.
