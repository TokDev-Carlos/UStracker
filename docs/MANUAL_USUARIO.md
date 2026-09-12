# Manual do Usuário — UStracker 1.00.00.000

## Instalação portátil
Extraia `UStracker_1.00.00.000_win-x64.zip` em uma pasta local do Windows 10/11 x64 e
execute `UStracker.exe`. Não execute o produto de pasta de rede, OneDrive sincronizado
ou compartilhamento SMB. O conteúdo de `UserData` é o estado da instalação.

## Primeiro acesso
Na instalação vazia, informe nome e senha do Administrador 1. O sistema exibirá dois
tickets de uso único com validade de 15 minutos. Use-os para cadastrar os Administradores
2 e 3. A produção é considerada administrativamente completa com os três slots inscritos.

## Ambientes
- **Production:** dados operacionais reais.
- **Test:** laboratório com banco/mídia próprios. O comando `LIMPAR TESTES` recria apenas
  o ambiente Test e não apaga os administradores nem Production.

## Fluxo operacional
Cadastre Clientes → Veículos → Planos/Itens → Assinaturas. Gere competências/cobranças,
registre recebimentos e alocações; valores excedentes só viram crédito quando isso for
explicitamente escolhido. Cadastre despesas/desembolsos e, quando necessário, referências
fiscais manuais. Use Dashboard/Busca/Relatórios para consulta.

## Backups
Use **Sistema → Criar backup**. O arquivo `.usbk` é cifrado. A restauração exige uma
sessão administrativa e substitui o dataset do ambiente correspondente após validação.
Mantenha cópias externas em mídia controlada pela organização.

## Encerramento
Fechar a janela revoga a sessão do Shell. O backend local pode permanecer disponível
para reabertura rápida; o comando **Encerrar sistema** finaliza o backend cooperativamente.
