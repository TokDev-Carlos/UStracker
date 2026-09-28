# Checkpoint R2 — 2026-09-15

## Estado instalado

- Instalação ativa única: `C:\UStracker\UStracker.exe`, produto `1.00.01.000`, schema 3.
- Fonte isolada: `C:\UStracker\.Arquivado\R2_source_20260915\UStracker`.
- Pacote local: `C:\UStracker\.Arquivado\R2_build_20260915\UStracker_1.00.01.000_win-x64.zip`.
- SHA256 do pacote: `315D62BECA52CF1AF2DB349A34171177F25AAF8D032B26EB3CA6BF3A0A622112`.
- Backup íntegro da instalação anterior e de `UserData`: `C:\UStracker\.Arquivado\R2_active_backup_20260915`.
- Arquivo recuperável da raiz mista durante a troca: `C:\UStracker\.Arquivado\R2_active_retired_20260915`.
- Nenhuma Release publicada.

## Trabalho desta metade

- Interface de Compras Diretas, ciclo diário/mensal/anual na assinatura, oito indicadores e tabela de clientes no Dashboard, Ficha do Cliente ampliada e Login horizontal REAL/TESTE.
- Ajuda contextual e datasets para os novos campos e módulo.
- O empacotador normaliza a herança de ACL NTFS e testa import de `fastapi`, `sqlcipher3` e backend antes do ZIP. O primeiro candidato falhou nesse import; o pacote final passou.
- A raiz foi trocada uma única vez depois de backup. Na primeira tentativa, um parâmetro PowerShell inválido não criou a pasta de arquivo; arquivos do candidato foram copiados sobre a instalação antiga. A segunda operação moveu todos os componentes não-`UserData` para o arquivo recuperável e copiou apenas o candidato final. `UserData` não foi alterado.

## Evidência fresca

- Backend: 11 testes `test_r2_*.py`, 0 falhas; `ResourceWarning` de conexões de testes preexistentes.
- Frontend: 8 testes Node, 0 falhas; `node --check` e `compileall` sem erro.
- Smoke UI na fonte isolada: Login, Dashboard, Compras Diretas, periodicidade de assinatura e Ficha do Cliente. Cliente e compra descartáveis criados somente no `UserData` da fonte isolada; compra marcada PAGA e indicadores atualizados.
- Smoke do pacote final: `UStracker.exe` abriu backend e `UStracker.Shell.exe`; `/api/v1/health` retornou OK.
- Comparação ativa/candidato: 1.507 arquivos do sistema, 0 diferenças de hash. Comparação ativa/backup de `UserData`: 7 arquivos, 0 diferenças de hash.
- Smoke da instalação ativa: launcher, Shell e backend iniciados, todos `Responding=True`; `/api/v1/health` OK. Porta atual verificada: `63612`.

## Limites e contexto preservado

- A instalação existente tinha apenas Admin 1 cadastrado. Admin 2 e 3 seguem pendentes; a tela informa configuração incompleta. Credenciais não foram redefinidas.
- O clique físico no X do Shell não pôde ser automatizado pela superfície de UI disponível nesta tarefa. A fonte possui fechamento direto por `WM_CLOSE`/`Environment.Exit(0)` e o launcher encerra o backend após a saída do Shell, mas isso não substitui um teste manual do X.
- O sistema ativo foi deixado aberto para inspeção. Não interromper processos sem conferir seus caminhos, pois o backup e os candidatos estão dentro de `.Arquivado`.
