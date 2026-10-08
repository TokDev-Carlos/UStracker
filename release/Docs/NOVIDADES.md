# UStracker 2.5.0

- **Começo limpo em qualquer versão** (2.2 a 2.4.1): na primeira abertura da 2.5 o sistema faz uma cópia completa dos dados antigos em `Documentos\UStracker_Backups\Pre-2.5_<data>` (conferida por SHA-256) e começa zerado, só com o Adm Global. Se a cópia não conferir, nada é apagado. Corrige os dados da 2.2 que ficavam travados (sem editar nem excluir) depois de atualizar.
- **Nuvem zerada uma vez**: a primeira ativação 2.5 do Adm Global move tudo o que havia na nuvem para a `_lixeira` (apagada sozinha depois de 14 dias) e começa a empresa nova. Computadores ainda em versão antiga não gravam mais na nuvem nova.
- **Banco novo**: estrutura única e limpa (sem colunas e tabelas antigas).
- **Usuários globais**: login e senha valem em todos os computadores e não se repetem. Na nuvem fica só texto cifrado. Criar ou alterar usuário precisa de internet; sem internet o computador entra com a última senha conhecida por até 1 dia.
- **Gerente cria usuários** (Operador, Gerente e pacotes sem administração). Senha criada por outra pessoa é provisória e é trocada no primeiro acesso.
- Excluir usuário (o login fica reservado).
- Botões ▾ do filtro das tabelas mais baixos.

# UStracker 2.4.1

- **Atualização**: o atualizador terminava com erro mesmo tendo instalado a versão nova (o Aplicador mostrava "não aplicado"). Corrigido; o Aplicador agora confere a versão instalada.
- Mensagens do Aplicador e dos scripts sem caracteres trocados (acentos).

# UStracker 2.4.0

- **Filtro em todas as tabelas** (estilo planilha): botão ▾ em cada coluna para ordenar (A→Z, menor→maior, datas e valores), buscar e marcar só os valores que quer ver. Vale em todas as páginas; a tabela de Clientes filtra em todas as páginas da lista.
- **Cliente empresa (CNPJ)**: novo tipo de documento CNPJ (com conferência dos dígitos). Cliente com CNPJ já vira a própria empresa principal.
- **Motos**: nova categoria Motos (com ícone). Aeronaves passam para Outros.
- **Assinatura por frota**: a Quantidade passa a ser automática = total de veículos marcados (frota de 10 + 2 avulsos = 12), com prévia da conta ("12 veículos × R$ 50,00 = R$ 600,00/mês") e aviso quando um veículo já está em outra assinatura ativa (evita cobrar 2×). A quantidade continua editável.
- **Pagamento mostra o que está sendo pago**: frota(s), placas, número de veículos e valor por veículo de cada assinatura.
- **Histórico na ficha do veículo/frota**: no número de assinaturas, a lista de cobranças por mês com situação, data do pagamento e valor por veículo.
- **Despesas**: Gerente edita e exclui despesas, inclusive pagas (os pagamentos vão juntos para a Lixeira e voltam juntos ao restaurar). Visão Geral mostra **Despesas Gerais** (pagas e a pagar) no período.
- **Recebimentos**: cartões **Total Recebido** e **Total Não Pago** (meses vencidos das assinaturas + compras diretas em aberto).
- Campos de valor começam vazios (o "R$ 0,00" some ao clicar) e fontes da Visão Geral maiores.

# UStracker 2.3.1

- **Ativação segura**: se a nuvem da empresa tiver dados de uma versão antiga (não validados pelo Adm Global), a ativação **para e mostra** o que existe lá (clientes, veículos, assinaturas, recebimentos e data do último salvamento). Nada é apagado.
- Caminho padrão: entrar **uma vez** com o Administrador da empresa — os dados ficam validados e o Adm Global passa a entrar direto.
- Recomeçar a empresa do zero só digitando **RECOMEÇAR**, com cópia antes em `Documentos\UStracker_backup_old`, e **bloqueado** se outro computador salvou nas últimas 24 horas.
- Primeira versão entregue pelo **Aplicador de Patch** (`.uspatch`).

# UStracker 2.3.0

- **Ativação entra direto**: num computador novo, o Adm Global ativa (acesso, PIN e pergunta de segurança) e já entra no sistema, sem nova tela de login.
- **Adm Local criado pelo Adm Global**: em **Sistema › Adm Global**, o Adm Global cria o Administrador local daquela instalação (com Chave de Recuperação).
- **Instalador com varredura**: dados validados pelo Adm Global são mantidos; um sistema antigo não validado é descartado e os dados dele vão antes para `Documentos\UStracker_backup_old\<data>`. A pasta antiga `C:\UStracker` é removida depois da cópia.
- Mensagem clara quando a instalação não foi ativada pelo Adm Global (antes aparecia "senha inválida" mesmo com o PIN certo).

# UStracker 2.2.0

- **Ativação pelo Adm Global**: a primeira entrada em qualquer computador é do Adm Global. Com a nuvem já usada, os dados chegam sozinhos; na primeira instalação, o Adm Global cria o Administrador da empresa (guardado na nuvem na hora).
- Corrigido o **"Internal Server Error"** na primeira entrada de um computador novo (acessos antigos vindos da nuvem). Erros inesperados agora aparecem em português e ficam em `UserData/Logs/erros.log`.
- **Segurança**: a chave da empresa saiu do instalador (chega na ativação, cifrada para o Adm Global); só endereços locais exatos são aceitos; custos/margens nunca saem do servidor para quem não tem a permissão; cancelar/encerrar assinatura e cancelar cliente pedem a permissão de excluir; ajuste de cobrança pede a de estornar; o Token Mestre novo é baixado, não fica no disco; "Encerrar" exige a sessão; o pedido interno de "zerar tudo" por arquivo foi desativado.
- **Estrutura Windows**: programa em `C:\Program Files\UStracker` (protegido) e dados em `C:\ProgramData\UStracker`. A instalação antiga em `C:\UStracker` é migrada sozinha.
- **Instalador novo**: detecta e fecha o sistema aberto, migra dados, instalação silenciosa (`/S`), registro em `UserData/Logs/instalacao.log`; desinstalação com **Manter dados** ou **Remover tudo** (cópia automática em Documentos antes de apagar).
- Atualizações pela nuvem pedem a permissão do Windows (UAC) quando o programa está protegido.
- "Encerrar" envia as últimas alterações para a nuvem antes de fechar.

# UStracker 2.1.1

- Primeira atualização entregue pela nuvem (validação do canal de atualização). Sem mudança no banco de dados.

# UStracker 2.1.0

- **Atualizações pela nuvem**: o sistema confere ao abrir e a cada 3 horas (canal `updates/` do repositório, assinado). Normal = instala ao fechar; obrigatória = bloqueia até atualizar. "Atualizar agora" para Administrador, Gerente ou quem tiver a permissão **Atualizar o sistema**. Volta sozinho para a versão anterior se a nova não abrir.

# UStracker 2.0.2

- **Um Administrador por instalação** (Adm Local) com **Chave de Recuperação** (Esqueci a senha).
- **Adm Global** (suporte/dono): login + PIN, pergunta de segurança, validado pelo Token Mestre no Git (ou passe de 1 dia sem internet). Bloqueio de 30 minutos após 5 erros.
- Funções técnicas reservadas ao Adm Global: conexão da nuvem, placa, restaurar nuvem/backup, recuperação, assumir gravação, auditoria e integrações.

# UStracker 2.0.1

- Login sem escolha de ambiente: todos entram no Real.
- **Banco de Teste só do Administrador**, pelo Sistema (entra e volta sem digitar a senha), com faixa de aviso. Local, nunca vai para a nuvem, nunca aparece no Real; Gerentes e Operadores não têm acesso (o servidor recusa).

# UStracker 2.0.0 — Release 2 (entrega oficial)

Data: 2026-10-04 · Schema do banco: **14** · Windows 10/11 x64 · Instalador: `UStracker_install_x64.exe`

## O que muda para quem usa
- **Um arquivo só**: `UStracker_install_x64.exe` leva o programa, o Microsoft WebView2 e o endereço da nuvem da empresa. Nada de pasta de kit nem arquivo ao lado.
- **Computador novo**: instalar e entrar com usuário e senha. Os dados vêm sozinhos da nuvem. Sem internet na primeira abertura, a tela espera e tenta de novo (não cria um Administrador separado por engano).
- **"Restaurar da nuvem" saiu das telas de entrada**: agora é ferramenta interna do Administrador (Sistema › Nuvem › Avançado).
- Login pede **Usuário** (vale para Administradores, Gerentes e Operadores).
- Base zerada para o início oficial; administradores, marca e nuvem mantidos.

## Técnico
- Versão semântica a partir daqui (2.0.0, 2.0.1, 2.1.0…); instalações 1.xxx continuam reconhecidas.
- `POST /cloud/restore` exige sessão de Administrador.
- G-02: rotina interna de "zerar tudo" (pedido em `UserData\State\factory-reset.json`, executado uma vez no login do Administrador; limpa também a nuvem).
- Instalador falha na compilação se faltar `-DWV2` ou `-DPLACA`; ao atualizar remove as sobras `Redist\` e `Instalador\` das versões antigas.
- Herdado da 1.007: usuários e pacotes, Servidores com vez de gravar, placa de direção assinada, Lixeira de 14 dias.
