# Manual do Usuário — UStracker 2.3.1

## Instalar
1. Execute **UStracker_install_x64.exe** (o Windows pede permissão de administrador) e siga as telas. Ele já leva tudo: programa, WebView2 e o endereço da nuvem da empresa.
   - Programa: `C:\Program Files\UStracker` (protegido; só administradores do Windows alteram).
   - Dados: `C:\ProgramData\UStracker\UserData` (clientes, finanças, fotos, backups).
   - Varredura: dados já validados pelo Adm Global são mantidos. Um sistema antigo **não validado** (ex.: `C:\UStracker` de versões antigas) é descartado; antes, os dados dele vão para `Documentos\UStracker_backup_old\<data>`.
2. Abra pelo atalho **UStracker** na Área de Trabalho ou no Menu Iniciar.
3. **Primeira abertura em qualquer computador: Ativar este computador.** Quem ativa é sempre o **Adm Global** (acesso do dono + PIN + pergunta de segurança).
   - A empresa já usa o UStracker: os dados chegam da nuvem e o computador vira mais um **Servidor**.
   - Dados de versão antiga na nuvem: a tela mostra o que existe; entre uma vez com o **Administrador da empresa** para validar (recomendado) ou digite **RECOMEÇAR** para começar do zero (com cópia antes; bloqueado se outro computador salvou nas últimas 24 h).
   - Dados de versão antiga na nuvem: a tela mostra o que existe; entre uma vez com o **Administrador da empresa** para validar (recomendado) ou digite **RECOMEÇAR** para começar do zero (com cópia antes; bloqueado se outro computador salvou nas últimas 24 h).
   - Primeiro computador da empresa: o Adm Global entra direto no sistema e, em **Sistema › Adm Global**, cria o **Administrador local** (guardado na nuvem, vale em todos os computadores).
4. Depois de criado o Administrador local, cada pessoa entra com o próprio usuário e senha.

## Desinstalar
Painel de Controle › Programas (ou Menu Iniciar › UStracker › Desinstalar):
- **Manter dados** (padrão): remove só o programa. Os dados ficam em `C:\ProgramData\UStracker` para uma reinstalação.
- **Remover tudo**: digite `REMOVER` para confirmar. Antes de apagar, uma cópia dos dados vai para `Documentos\UStracker_Backups\Desinstalacao_<data>`. A nuvem da empresa não é apagada.

**Atualizações chegam sozinhas** (o sistema confere ao abrir e a cada 3 horas):
- **Normal**: aparece uma faixa azul "Versão X disponível". Ela é instalada quando o sistema for fechado (Encerrar, Sair ou X) e já vale na próxima abertura. Administrador e Gerente também podem clicar em **Atualizar agora** (o sistema fecha e reabre sozinho).
- **Obrigatória** (correção importante): o sistema mostra a tela "Atualização obrigatória"; clique em **Atualizar agora**.
- Como o programa fica protegido em *Arquivos de Programas*, o Windows pede a permissão de administrador (UAC) para instalar a versão nova. Se não houver permissão agora, ela fica guardada e é instalada na próxima vez.
- Se a versão nova não abrir, o sistema volta sozinho para a anterior. Seus dados (`UserData`) nunca são tocados.

## Administrador e Chave de Recuperação
- Cada instalação tem **um Administrador** (Adm Local). Ao configurar o sistema aparece a **Chave de Recuperação**: guarde fora do computador.
- Esqueceu a senha? Na tela de entrada: **Esqueci a senha** → Chave de Recuperação + senha nova.
- Algumas funções técnicas (conexão da nuvem, placa, restaurar backups, assumir gravação, auditoria) são reservadas ao suporte do sistema.

## Usuários e pacotes
- Administrador cria pessoas em **Sistema › Usuários** (nome de acesso, senha inicial e pacote).
- **Operador**: cria e atualiza clientes, veículos, planos e registra pagamentos. Não exclui, não estorna, não vê despesas nem custos.
- **Gerente**: tudo do Operador + excluir, estornar, despesas, fiscal, custos, relatórios e Lixeira. Sem o menu Sistema.
- Pacotes próprios: **+ Novo pacote** e marque o que pode.
- Cada um troca a própria senha clicando no nome, no topo.

## Entrar
- Todos entram direto nos dados **Reais** com usuário e senha.
- **Banco de Teste** (só Administrador): Sistema › Administração › *Entrar no banco de Teste*. Fica só neste computador, nunca vai para a nuvem e não aparece no Real. Uma faixa vermelha avisa enquanto estiver nele; *Voltar ao Real* no mesmo lugar.
- **Sair** encerra a sessão. **Encerrar** fecha o sistema todo (use antes de desligar ou atualizar).

## O dia a dia, na ordem
1. **Clientes → Novo cliente.** Nome, documento e um contato.
2. **Na ficha do cliente → Veículos e Frotas → + Veículo** (ou + Frota, se o cliente tem empresa).
   Se a placa já existir, o sistema mostra de quem é antes de salvar.
3. **Assinar plano:** escolha o plano mensal e marque os veículos que ele cobre.
4. **Registrar pagamento:** na ficha ou em Financeiro. Escolha quantos meses; atrasados são pagos primeiro.
5. **Despesas:** Financeiro → Despesas. Mensal, anual ou única; "Pagar" em um clique.

## Onde fica cada coisa
| Menu | Para quê |
|---|---|
| Visão geral | Receita, previsão do mês, despesas, resultado, clientes e veículos |
| Clientes | Cadastro e ficha completa (clique na linha para abrir) |
| Frotas/Veículos | Todos os veículos e frotas; **Mover** e **Excluir** |
| Planos/Produtos | Planos mensais e produtos avulsos, preço e custo |
| Comercial | Assinaturas (menu **Ações**), compras diretas e créditos |
| Financeiro | Recebimentos, despesas e fiscal |
| Fotos/Arquivos | Fotos e documentos anexados |
| Relatórios | Planilhas para baixar |
| Sistema | Administradores, backup, **Nuvem** e **Lixeira** |

## O que é uma assinatura
É o **plano mensal** do cliente. Todo mês gera uma cobrança no dia do vencimento para os veículos ou frotas marcados. Paga, vira receita. O contrato assinado pode ser anexado na aba **Arquivos** da ficha.

## Fotos
- Clique na foto (cliente ou veículo) para **adicionar ou trocar**.
- O **×** no canto remove. Apareceu sem querer? Clique em **Desfazer** no aviso.
- A foto do veículo aparece inteira, sem cortes. Clique em um veículo da lista para ver a dele.

## Excluir e a Lixeira (14 dias)
- Tudo que é excluído vai para **Sistema → Lixeira** e pode voltar com **Restaurar** por 14 dias.
- Excluir um **cliente** leva junto as frotas e os veículos dele.
- Excluir uma **frota**: você escolhe se os veículos ficam como Particular ou se vão junto.
- Itens com assinatura ativa não podem ser excluídos: encerre a assinatura antes.
- O histórico financeiro é sempre mantido.

## Nuvem (Google Drive)
Configurada uma vez pelo Adm Global (`NUVEM_GOOGLE_DRIVE.md`). Depois o sistema envia tudo sozinho, cifrado, segundos depois de cada alteração e ao clicar em **Encerrar**. Usuários e senhas também ficam na nuvem: quem é criado num computador entra em todos. Computador novo: instalar e ativar com o Adm Global.

## Problemas comuns
- **"Nuvem: o Google pediu login…"** → no Apps Script, a implantação precisa estar como *Qualquer pessoa*.
- **"Outra máquina enviou dados mais novos"** → um Servidor salvou sem internet enquanto outro gravava; o Administrador escolhe qual fica valendo em Sistema → Nuvem.
- **"Sem internet: a ativação precisa de internet uma vez"** → conecte e tente de novo.
- **"Erro interno"** → tente de novo; se repetir, envie `C:\ProgramData\UStracker\UserData\Logs\erros.log` ao suporte.
- **Algo sumiu?** Veja a Lixeira. Passou de 14 dias? Use um ponto de restauração em Sistema → Nuvem.
