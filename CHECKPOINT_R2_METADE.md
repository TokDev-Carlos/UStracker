# Checkpoint R2 — metade funcional (2026-09-15)

Fonte isolada: `C:\UStracker\.Arquivado\R2_source_20260915\UStracker`  
ZIP de origem SHA256: `776BD25D781EAFA9F74B6691AE1453AE8C0186132290888CA7854E4258BA2E20`

## Concluído nesta metade

- Schema 3 na fonte, migração de `subscriptions.billing_cycle`, tabelas de compras diretas e metadados `VERSION.json/current.json` com versão do produto inalterada.
- Serviços de compras diretas, listagem, status com revisão otimista, perfil do cliente e Dashboard com receita/desembolso realizados, acumulado anual e visão por cliente.
- Rotas de compras diretas e ficha do cliente, autenticadas e com mutações pelo fluxo existente de CSRF, idempotência e estação escritora.
- Ciclos `DAILY/MONTHLY/ANNUAL` na criação de assinaturas, mantendo `billing_interval_months` para compatibilidade.
- Preservadas na fonte as correções ativas de credencial mínima de 4 caracteres, shutdown sem sessão nas telas de Login/configuração e traduções visuais `pt-br.js`.

## Evidência do checkpoint

- `python.exe -m unittest discover -s tests -p 'test_r2_*.py' -v`: 11 testes, 0 falhas. O runtime emite `ResourceWarning` para conexões de autenticação já existentes; não houve falha de teste.
- `node --check` em `frontend/app.js`, `frontend/ui/api.js` e `frontend/ui/pt-br.js`: sem erro.
- `python.exe -m compileall -q src/ustracker`: sem erro.
- A instalação ativa `C:\UStracker` continua com schema 2 e não foi substituída. Nenhum pacote R2 foi gerado ou publicado.

## Próxima metade — ainda não executar sem nova solicitação

1. Página Compras Diretas e escolha visível de periodicidade na interface.
2. Oito cards e tabela principal do Dashboard com ação `Abrir Ficha`.
3. Ficha do Cliente ampliada com mídia existente.
4. Login horizontal REAL/TESTE e ajustes visuais finais.
5. Testes de interface e smoke completo; proteção de `UserData`, empacotamento e troca única do sistema ativo.

## Integridade da fonte neste ponto

- `src/ustracker/db.py`: `15C1382BB7ABCBC55639B48C90CACCEE7072B27DC955D88FB76154348A717A6A`
- `src/ustracker/services.py`: `D18B326E69D0C17F2C1DA46F1F724EFE5000E76ED11CFB92ED915E36D043D86C`
- `src/ustracker/server.py`: `1CD24BBBE7BE91D9EBED206D42F425C338DF78E2EF473602AC49FC47D048A1D0`
