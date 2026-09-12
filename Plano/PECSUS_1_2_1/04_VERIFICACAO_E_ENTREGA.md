# Verificação, homologação e entrega — PECSUS 1.2.1

## 1. Regra de evidência
`PASS` só existe quando o caso foi realmente executado no ambiente aplicável e possui evidência: command, stdout/stderr, exit_code, timestamp, environment, build/version e hashes relevantes. Code review/linters não substituem casos nativos.

Estados: `NAO_EXECUTADO`, `PASS`, `FAIL`, `BLOCKED`, `INVALIDATED`. Alteração posterior em função/contrato invalida somente casos dependentes registrados.

## 2. Camadas
1. **Function review:** cada função pública da task, inputs/outputs/exceptions/invariantes.
2. **Module integration:** serviço + repo/API/UI correspondente.
3. **Gate task:** todos casos Txx.
4. **Complete integration T18:** jornada end-to-end candidato congelado.
5. **Native:** T01/T16/T18 em Windows; Windows 10 22H2 obrigatório para release.

## 3. G0 fechado nesta revisão
P0-01 plataforma: resolvido por net48/WebView2 + matriz formal/compat.  
P0-02 Vault cycle: resolvido por DatabaseKeyProvider em T01 + StaticTestKeyProvider em T03 + VaultKeyProvider T04.  
P0-03 contratos duplicados: resolvido; `02_CONTRATOS.md` é canônico único.  
P0-04 histórico: resolvido por `MATRIZ_ESCOPO_HISTORICO.csv`.  
P0-05 prova nativa: incorporada a T01/G1 e T16/T18.

P1 lifecycle, Auth Production/Test, reset de admin, formato backup, cobertura funcional e SQLCipher supply chain foram incorporados aos contratos/casos.

## 4. Release gate T18
Todos devem ser verdadeiros:
- R01–R36 com tarefas/casos existentes.
- Todo H-item MANTER/SUBSTITUIR/RESOLVIDO/ADICIONAR possui task e caso; ADIAR/EXCLUIR possui motivo/versão e não aparece como implementado.
- Todo case obrigatório está PASS, com evidência válida do candidato; NAO_EXECUTADO também bloqueia entrega. Casos adicionais de compatibilidade têm required=false e relatório separado, sem claim de aprovação quando falham.
- Windows 10 22H2 native PASS; Win11 compatibility report anexado.
- SQLCipher real PASS e plaintext SQLite FAIL como esperado.
- Public privacy scan PASS.
- Backup restore/recovery/update/rollback PASS.
- Performance P1 PASS ou revisão de perfil assinada antes do candidato (não pós-hoc para esconder falha).
- Source snapshot/SBOM/licenças e runtime hashes conferem.
- `AJUSTES_FUTUROS.log` sem blocker.

## 5. Jornada integrada mínima
1. Clean root, primeiro start, G1 health/UI.
2. Enrollment dos 3 admins.
3. Cliente completo + veículo completo + frota + foto.
4. Catálogo + preço histórico + assinatura/itens.
5. Geração competência + ajustes/due change.
6. Pagamento parcial + crédito + aplicação + reversão.
7. Despesa recorrente/parcial + fiscal vinculado.
8. Dashboard cash/accrual + busca global + CSV/XLSX.
9. Branding + Test reset + anonimização elegível.
10. X/reopen público sem sessão.
11. Backup/restore/recovery export.
12. Station transfer A->B.
13. Update signed + rollback scenario.
14. Shutdown completo.
15. Reabrir e executar integrity/reconciliation.

## 6. Classificação de defeitos
**Blocking:** segurança, autenticação, key isolation, SQLCipher, perda/corrupção, dupla contagem, idempotência, writer isolation, backup/restore, update/rollback, privacidade PUBLIC, start/shutdown, requisito obrigatório ausente.  
**Nonblocking:** cosmética sem ocultar informação/ação, copy textual não enganosa, alinhamento sem quebrar acessibilidade.  
Somente nonblocking pode ir a `AJUSTES_FUTUROS.log`.

## 7. Comandos
```powershell
# Gate unit/integration específico
& .\.venv\Scripts\python.exe tools\verify.py --task T06 --evidence-dir Evidence
if ($LASTEXITCODE -ne 0) { throw 'Gate failed' }

# Integração completa
& .\.venv\Scripts\python.exe tools\verify.py --integration --evidence-dir Evidence
if ($LASTEXITCODE -ne 0) { throw 'Integration failed' }

# Nativo no candidato empacotado
& .\Runtime\python.exe -m ustracker_verification --native --profile win10_22h2 --evidence-dir Evidence
if ($LASTEXITCODE -ne 0) { throw 'Native gate failed' }
```

O módulo ustracker_verification pertence ao VerificationBundle de engenharia, criado em T01/T16 e referenciado no python313._pth de homologação do candidato; não é presumido instalado no cliente. tools/verify.py prepara esse bundle e invoca o Runtime do candidato sem alterar binários/dataset de produção.

## 8. Retomada
Toda sessão de execução começa lendo: `00_LEIA_PRIMEIRO.md`, `PONTO_DE_PARADA.json`, `01_ESPECIFICACAO.md`, `02_CONTRATOS.md`, task atual em `03_EXECUCAO_LINEAR.md` e casos correspondentes. Não reler snapshots inteiros salvo investigação específica.

## 9. Gate documental e fontes únicas
- `TAREFAS.json` é fonte dos passos e interfaces; `03_EXECUCAO_LINEAR.md` é gerado exatamente por tools/gerar_derivados.py.
- `PECSUS_COMPLETO_1_2_1.txt` é leitura agregada gerada dos documentos/matrizes/casos; não editar diretamente.
- Rodar `python tools/validar_plano.py --root .` para JSON/IDs/dependências/matrizes/derivados/manifesto e invariantes documentais. Isso não executa casos do software.
- Rodar `python tools/gerar_derivados.py` somente depois de mudança documental intencional; registrar revisão e invalidar evidências dependentes antes de atualizar manifesto. Hash sozinho não é assinatura/autorização da alteração.
- CASOS_ACEITE.json é catálogo imutável do pacote aprovado. Resultados reais ficam em Evidence/<task>/result.json e Estado/; não converter o catálogo do plano em evidência nem alterar manifesto para encobrir edição.
- PONTO_DE_PARADA.json e REGISTRO_EXECUCAO_MODELO.json do pacote são sementes. Copiar para Estado/ na raiz de engenharia; todos os checkpoints posteriores são gravados ali atomicamente, preservando plano e hashes originais.
- Windows10 é perfil formal. windows11 adicional: T01-C05 não bloqueia o perfil formal; relatório obrigatório declara NAO_EXECUTADO/BLOCKED/FAIL quando aplicável. Não marcar compatibilidade aprovada por inferência de net48.
