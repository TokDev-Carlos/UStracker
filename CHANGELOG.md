# Changelog

Formato: versão semântica a partir da 2.0.0 (2.0.1 = correção, 2.1.0 = novidade compatível).

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
