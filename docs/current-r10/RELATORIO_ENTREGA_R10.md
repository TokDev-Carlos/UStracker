# Relatório de entrega técnica — R10

## Escopo acumulado
A linha atual consolida R01 a R09 e mantém versão do produto `1.00.01.000`, elevando o schema de 3 para 8 por migrações aditivas.

## Gates executados neste ambiente
- Python: 46 testes executados; 45 PASS e 1 SKIP (`sqlcipher3` indisponível).
- Node: 30/30 PASS.
- `python -m compileall`: PASS.
- `node --check frontend/app.js`: PASS.
- `git diff --check`: PASS.
- Migração/reabertura schema 8 e reconciliação: PASS.
- Backup/restore de anexos cifrados: PASS.

## Limitações explícitas
Este ambiente não possui SDK .NET nem PowerShell Windows. Portanto não foi gerado nem assinado um novo instalador nativo. O artefato entregue para Windows é um homologador cumulativo que copia a instalação baseline 1.00.01.000/schema 3 para uma sandbox, aplica o overlay schema 8 e executa a cópia.

## Regra de promoção
O pacote cumulativo pode ser usado sem executar R04–R09 individualmente. Ele contém todos os incrementos anteriores. A instalação ativa `C:\UStracker` permanece fonte somente de leitura durante a homologação.
