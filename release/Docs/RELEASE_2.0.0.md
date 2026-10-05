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
