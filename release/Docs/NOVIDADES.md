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
