# Manual do Usuário — UStracker 1.00.01.000

## Instalação e primeiro acesso

Extraia o pacote em uma pasta local do Windows 10/11 x64 e execute `UStracker.exe`. Não opere a partir de rede, SMB ou pasta sincronizada. No primeiro acesso, cadastre o Administrador 1 e use os dois tickets temporários para criar os Administradores 2 e 3.

## Sessão e ambientes

Produção contém dados reais e aceita alterações somente na estação escritora. Testes é um ambiente isolado; **LIMPAR TESTES** não afeta Produção. Atualizar a tela preserva a sessão. **Sair** encerra somente a sessão; **Encerrar** e o botão **X** solicitam o desligamento coordenado da aplicação e do backend.

## Áreas operacionais

- **Dashboard:** indicadores operacionais e financeiros.
- **Clientes:** pessoas ou empresas atendidas.
- **Frotas:** agrupamentos de veículos por cliente, setor ou unidade.
- **Veículos:** ativos rastreados e seu histórico de propriedade.
- **Planos e Itens:** catálogo comercial. Preço é valor de venda; custo é interno. **Exibir no catálogo público** inclui o item na projeção pública, mas não publica o aplicativo na internet.
- **Assinaturas:** vínculo recorrente entre cliente e itens do catálogo.
- **Cobranças:** valores por competência e respectivos ajustes.
- **Recebimentos:** pagamentos e suas alocações; sobra só vira crédito quando escolhida.
- **Créditos:** saldo favorável aplicável a cobranças futuras.
- **Despesas:** obrigações previstas, desembolsos e recorrências.
- **Fiscal:** acompanhamento manual; não transmite nem emite documento fiscal oficial.
- **Fotos:** mídias vinculadas a registros operacionais.
- **Relatórios:** exportações CSV/XLSX, sem alteração dos dados.

Cada listagem usa a Tabela Central: filtro textual, ordenação pelos cabeçalhos, paginação e ações contextuais. A barra superior mantém Busca, Ambiente, Ajuda, Usuário, Sair e Encerrar disponíveis em toda a sessão.

## Backup, recovery e transferência

Backups `.usbk` são cifrados e validados. O login em Produção cria backup automático quando necessário, respeitando a retenção configurada. O restore valida ambiente e integridade e cria proteção pré-restore.

Recovery `.usre` inclui autenticação, bancos, mídia e projeção pública, protegido por passphrase externa de ao menos 12 caracteres. Para transferir a estação escritora, gere o recovery com a opção de transferência, encerre o sistema e importe o pacote na nova instalação. Não copie banco aberto manualmente.

## Segurança de acesso

O login aceita PIN numérico de quatro ou mais dígitos ou senha longa, conforme a política configurada. Falhas repetidas recebem atraso progressivo. Credenciais não são registradas em logs.

## Atualização e encerramento

Encerre o sistema antes de executar `UStracker.Updater.exe pacote.usup`. O atualizador valida assinatura e hashes, prepara rollback e só então troca os arquivos. O encerramento normal sempre deve terminar o backend local cooperativamente.
