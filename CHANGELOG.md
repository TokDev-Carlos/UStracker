# Changelog

Formato: versão semântica a partir da 2.0.0 (2.0.1 = correção, 2.1.0 = novidade compatível).

## 2.1.0 — 2026-10-05
- Atualização pela nuvem: canal assinado em `updates/`; checagem ao abrir e a cada 3 h; normal instala ao fechar; crítica é obrigatória; "Atualizar agora" (Administrador, Gerente ou permissão *Atualizar o sistema*); volta sozinho se a versão nova não abrir.
- Nova chave de atualização (`Trust/update_public_key.pem`) e ferramenta `tools/publish_update.py`.

## 2.0.2 — 2026-10-05
- Um Administrador por instalação (Adm Local) com Chave de Recuperação ("Esqueci a senha").
- Adm Global: login + PIN + pergunta de segurança com pistas; validado pelo Token Mestre no repositório privado `acesso-UStracker` ou passe de 1 dia sem internet; bloqueio de 30 minutos.
- Funções técnicas reservadas ao Adm Global (nuvem, placa, restaurações, recuperação, assumir gravação, auditoria, integrações).

## 2.0.1 — 2026-10-04
- Login sem escolha de ambiente: todos entram no Real.
- Banco de Teste só do Administrador (Sistema › Administração), com faixa de aviso; local, nunca vai para a nuvem; Gerentes e Operadores sem acesso.

## 2.0.0 — 2026-10-04 · Release 2 (entrega oficial)
- Instalador único `UStracker_install_x64.exe` com programa, WebView2 e endereço da nuvem embutidos.
- Computador novo: instalar e entrar; os dados vêm sozinhos da nuvem. Sem internet, a tela espera a nuvem (não cria Administrador separado).
- "Restaurar da nuvem" virou ferramenta interna do Administrador (Sistema › Nuvem › Avançado).
- Login pede **Usuário** (Administradores, Gerentes e Operadores).
- Rotina interna de "zerar tudo" (uma vez, no login do Administrador), incluindo a nuvem.
- Base de dados zerada para o início oficial.

## 1.007 — Servidores, usuários e nuvem da empresa
- Usuários com pacotes (Operador, Gerente, personalizados); Servidores com vez de gravar automática; placa de direção assinada (Banco 1 principal, Banco 2+ espelhos).

## 1.006 — Ajustes de frota e instalador
- Exclusão de veículos/frotas com Lixeira, placa única com aviso de dono, primeiro instalador NSIS.

## 1.005 — Nuvem e Lixeira
- Cópia cifrada no Google Drive, pontos de restauração e Lixeira de 14 dias.

## 1.004 e anteriores
- Base do sistema (clientes, frotas, planos, assinaturas, financeiro, despesas, fiscal, relatórios). Histórico completo no branch `Dev`.
