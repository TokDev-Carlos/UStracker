# T01 — plano de execução da engenharia limpa

Executar no contexto atual conforme autorização do proprietário, com checkpoint
recuperável entre sessões. O desenho arquitetural já aprovado é o PECSUS 1.2.1;
este documento detalha a implementação sem substituir contratos ou casos.

## Autoridade e resultados necessários

Authority/PECSUS_1_2_1/TAREFAS.json T01 e CASOS_ACEITE.json T01-C01..C09;
02_CONTRATOS.md seções 3 (RootPaths/DatabaseKeyProvider), 12 e 15;
01_ESPECIFICACAO.md R01/R17/R18/R19/R24/R30/R33/R35;
04_VERIFICACAO_E_ENTREGA.md e 05_OPERACAO_E_CONTINUIDADE.md.
H237/H238 vinculam identidade/versão/plataforma.

## Unidades e ordem

- [x] Preservar engenharia anterior integralmente e verificar cada SHA-256.
- [x] Extrair fontes originais isoladas; executar G0 documental e registrar ambiente.
- [ ] Versionar regras permanentes, autoridade, checkpoint e plano inicial.
- [ ] Paths/versões: RED em tests/unit/test_paths_version.py; implementar
  src/ustracker/core/paths.py; testar raiz movida/Unicode, versões numéricas,
  JSON duplicado, traversal, release/runtime ausente e versão divergente.
- [ ] Chaves: RED para consumidor injetado; implementar apenas
  DatabaseKeyProvider em src/ustracker/security/key_provider.py;
  StaticTestKeyProvider somente em tests/support, sem Vault/T03 antecipados.
- [ ] Harness: RED para casos vazios/ausentes/duplicados/desconhecidos, evidência
  faltante/adulterada, perfil/candidato diferentes; implementar fail-closed.
- [ ] Dependências: fonte oficial → staging temporário → hash/licença/origem de
  todos os artefatos/transitivos → lock validado → promoção atômica. Testar
  falhas de download/hash e ALREADY_IN_PLACE em PowerShell 5.1 antes do uso.
- [ ] Runtime Python local e SQLCipher real: cipher_version, DB cifrado, chave
  incorreta e sqlite3 comum recusados. Nenhum pip/PATH global no cliente.
- [ ] Protocolo Python/C#: length-prefix uint32 big-endian + UTF-8 JSON,
  wire port/nonce/pid/product, identidade/PID/nonce exatos, leituras parciais
  e limites; pipe ACL usuário atual. Backend mantém o socket reservado.
- [ ] Bootstrap/Shell/Updater net48 x64, WebView2 fixo, splash/health público,
  profile novo e detach distinto de shutdown. Revisar por função e integrar.
- [ ] Construir Dist/Candidate e VerificationBundle separado com hashes;
  manifestos, SBOM/licenças, Trust público e chave TEST_ONLY segregada.
- [ ] Executar C01 nos dois paths reais; C02/C03/C04 no Runtime candidato;
  C08 em Windows 10 limpo; C05 relatório adicional conforme disponibilidade.
- [ ] Gate completo T01 → Evidence → checkpoint → commit. T02 somente após PASS.

## Decisões de representação a testar

Detalhes não literalizados no PECSUS: VERSION.json contém `version`; current.json
contém `release` (Releases/<versão>), `dataset` (UUID) e `sequence` (inteiro >=1).
Não contém outra cópia da versão. A raiz vem do caminho absoluto do executável,
nunca do cwd; validação não cria diretórios. IDs de datasets são UUID canônicos.
O parser rejeita chaves JSON duplicadas e referências ambíguas/absolutas/traversal.
Release deve ter VERSION.json coerente, Runtime/pythonw.exe e WebView2Runtime.
Essas decisões materializam as relações exigidas e serão compartilhadas por
Python/C#; não mudam contratos financeiros ou funcionais.

## Retomada / evidência

Executar primeiro `git status --short` e ler Estado/PONTO_DE_PARADA.json.
Executar os testes dirigidos via `.venv/Scripts/python.exe -m pytest`.
Cada RED/GREEN gera Evidence/T01/<unidade>_<fase>.json com comando literal,
cwd, UTC, exit code, stdout/stderr, ambiente e SHA-256 dos arquivos exercitados.
Os testes dessa unidade não aprovam C01/C04/C08 nem o gate T01.
G0 aprovou somente documentos: 36 requisitos, 18 tarefas, 145 casos,
144 obrigatórios e 250 itens históricos. Nenhum PASS antigo foi promovido.
