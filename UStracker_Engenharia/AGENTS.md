# UStracker — regras permanentes de engenharia

Autoridade: PECSUS 1.2.1 em Authority/PECSUS_1_2_1, proveniente do ZIP
original, seguido pelo Script Mestre, Prompt Mestre e orientação de execução.
Não modificar o plano, catálogo ou manifesto para obter aprovação de código.
Ler Estado/PONTO_DE_PARADA.json, tarefa/casos/contratos associados, última
evidência, git status e git log antes de retomar. Não reiniciar esta engenharia.

Produto 1.00.00.000. Windows 10 22H2 build 19045 x64 é o perfil formal;
Windows 11 x64 é compatibilidade adicional, sem PASS por inferência.
Host net48 x64/WPF/WebView2; PowerShell 5.1; Python 3.13.15 embeddable x64;
SQLCipher real sqlcipher3 0.6.2. Preservar copyright CRJ.

T01 precede T02 e assim até T18. Nenhum caso obrigatório FAIL/BLOCKED/
NAO_EXECUTADO autoriza avanço. Testes unitários não homologam o produto.
Aplicar RED → GREEN → REFACTOR → VERIFY, revisão por função e integração.
Não copiar implementação, locks, feeds, runtime, PASS ou Evidence históricos.
Não executar scripts antigos. Preservar o arquivo histórico e alterações do dono.

Primeiro erro: causa-raiz; segundo no componente: revisar componente inteiro;
terceiro correlacionado: reconstruir pelo contrato, sem cascata de remendos.
Edite arquivos completos/patches revisáveis; não peça ao dono para editar no console.
Parsear scripts no PowerShell 5.1 antes de executá-los. Paths com espaços/Unicode
são requisitos. Staging/locks idempotentes e transacionais; erro impede promoção.

Evidence registra comando, cwd, UTC, stdout, stderr, exit code, ambiente e hashes.
Evidência nativa deve identificar exatamente o candidato e perfil testados.
Checkpoint atômico, preservando o anterior. Git local, branch de engenharia;
commits por unidade consistente. Nenhum remoto/publicação é necessário.
Fechar sessões de forma recuperável próximo do limite operacional de contexto,
sem inventar percentuais de consumo. Registrar próxima ação e comando exatos.

Invariantes futuros: PUBLIC allowlist; autorização no backend; 3 ADMIN;
Production/Test isolados; dinheiro cents/Decimal; escrita única; backup/update
transacionais; sem segredos em logs/release; integrações futuras disabled/501.
Clean host C08 é distinto do build host. Chave produtiva pertence ao proprietário.
Intervir com o usuário somente para bloqueio real não resolvível no escopo autorizado.

Palavras fornecidas pelo proprietário: keyWord, BrainMain, RecapLine,
CloneMemory, InputAndOutput, DB_Dynamics, ShutDown, TakeOwn_And_RecapClone.
Não inventar ações ou semântica operacional para essas palavras sem definição.
