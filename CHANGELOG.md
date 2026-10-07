# Changelog

Formato: versão semântica a partir da 2.0.0 (2.0.1 = correção, 2.1.0 = novidade compatível).

## 2.4.1 — 2026-10-07

- Atualizador não termina mais com erro falso depois de instalar; Aplicador de Patch confere a versão instalada.
- Acentos corretos nas mensagens do Aplicador e nos scripts locais; botões de filtro mais baixos.

## 2.4.0 — 2026-10-06

- Filtro estilo planilha em todas as tabelas (ordenar, buscar, marcar valores).
- Cliente empresa com CNPJ (empresa principal automática); categoria Motos.
- Assinatura por frota: quantidade automática, prévia da conta e aviso de duplicidade.
- Pagamento mostra frota, placas e valor por veículo; histórico de cobranças na ficha do veículo/frota.
- Despesas editáveis e excluíveis (inclusive pagas); cartões Total Recebido / Total Não Pago; Despesas Gerais na Visão Geral.

## 2.3.1 — 2026-10-06

- Ativação nunca reinicia a nuvem sozinha: mostra o que existe, Administrador antigo valida; RECOMEÇAR só digitando e com bloqueio de 24 h.

## 2.3.0 — 2026-10-05

- Ativação de empresa nova: o Adm Global entra direto no sistema (sem ticket nem login).
- Sistema › Adm Global: criar o Administrador local da instalação (com Chave de Recuperação).
- Instalador com varredura: só dados validados pelo Adm Global (`State/adm-global.ok`) são mantidos; o resto vai para `Documentos\UStracker_backup_old` e o sistema antigo é removido.
- Login do Adm Global em dados antigos: mensagem clara (409 NOT_PREPARED) em vez de "senha inválida".

## 2.2.0 — 2026-10-05
- Ativação de computador novo só pelo Adm Global; na primeira instalação ele cria o Administrador da empresa (guardado na nuvem na hora).
- Corrige o "Internal Server Error" na primeira entrada (acessos antigos vindos da nuvem); erros inesperados em JSON + `UserData/Logs/erros.log`.
- Segurança: chave da empresa fora do instalador (`company-key.json` cifrado para o Adm Global em `acesso-UStracker`); host/origem exatos; custos nunca saem para quem não tem a permissão; cancelar/encerrar e ajustes de cobrança com permissões próprias; Token Mestre baixado (não fica no disco); "Encerrar" exige sessão; pedido de "zerar tudo" por arquivo desativado; `global_access` só aceita o Adm Global confiável.
- Windows: Program Files (protegido) + ProgramData (dados) com junção `UserData`; migração automática de `C:\UStracker`.
- Instalador: fecha o sistema aberto, migra, `/S`, log; desinstalar com Manter dados / Remover tudo (cópia antes).
- Atualização pela nuvem com UAC quando o programa está protegido; pacote conferido contra a versão anunciada.

## 2.1.1 — 2026-10-05
- Primeira atualização entregue pela nuvem (validação do canal). Sem mudança no banco.

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
