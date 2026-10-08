# Manual do Usuário — UStracker 2.6.0

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
- Administrador ou Gerente cria pessoas em **Sistema › Usuários** (login, senha provisória e pacote). Gerente não cria nem altera administradores.
- **O login vale em todos os computadores da empresa** e é único: "Carlos", "carlos" e "Cárlos" são o mesmo login. Login: letras, números, ponto, hífen ou sublinhado (3 a 32, sem espaço).
- Criar, alterar, trocar senha ou excluir usuário **precisa de internet**. Login excluído fica reservado (não pode ser criado de novo).
- Sem internet, o computador ainda entra com a última senha conhecida por **até 1 dia**. Quando a internet volta, senha trocada em outro computador passa a valer e quem estava com a senha antiga é desconectado (o que já foi lançado fica salvo).
- **Operador**: cria e atualiza clientes, veículos, planos e registra pagamentos. Não exclui, não estorna, não vê despesas nem custos.
- **Gerente**: tudo do Operador + excluir, estornar, despesas, fiscal, custos, relatórios, Lixeira e usuários. Sem as funções de administração.
- Pacotes próprios (só Administrador): **+ Novo pacote** e marque o que pode.
- Senha criada ou redefinida por outra pessoa é provisória: ao entrar, o sistema pede a troca. Cada um troca a própria senha clicando no nome, no topo.

## Entrar
- Todos entram direto nos dados **Reais** com usuário e senha.
- **Banco de Teste** (só Administrador): Sistema › Administração › *Entrar no banco de Teste*. Fica só neste computador, nunca vai para a nuvem e não aparece no Real. Uma faixa vermelha avisa enquanto estiver nele; *Voltar ao Real* no mesmo lugar.
- **Sair** encerra a sessão. **Encerrar** fecha o sistema todo (use antes de desligar ou atualizar).

## O dia a dia, na ordem
1. **Clientes → Novo cliente.** Nome, documento (CPF, CNPJ, RG ou CNH) e um contato. Com CNPJ, o cliente já é a própria empresa.
2. **Na ficha do cliente → Veículos e Frotas → + Veículo** (ou + Frota, se o cliente tem empresa).
   Se a placa já existir, o sistema mostra de quem é antes de salvar.
3. **Assinar plano:** escolha o plano mensal e marque os veículos e/ou frotas. A quantidade vira o total de veículos sozinha e aparece a prévia ("12 veículos × R$ 50,00 = R$ 600,00/mês"); se um veículo já estiver em outra assinatura, aparece um aviso.
4. **Registrar pagamento:** na ficha ou em Financeiro. Cada assinatura mostra frotas, placas e valor por veículo. Escolha quantos meses; atrasados são pagos primeiro.
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

## Filtrar tabelas
Em qualquer tabela, o botão **▾** ao lado do título da coluna ordena (A→Z, menor→maior) e filtra por valores, como numa planilha. **Limpar filtros** volta a mostrar tudo.

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
- **Prazos (LGPD)** — depois dos 14 dias:
  - cliente **sem** nada financeiro: sai de vez, com veículos, fotos e anexos;
  - cliente **com** financeiro: saem contatos, endereço, observações, fotos e anexos. Ficam nome, documento, placas e pagamentos por **5 anos** (prova de pagamento e contador);
  - depois de 5 anos: fica só o valor, sem ligação com ninguém. Os totais dos meses nunca mudam.
- **Exportar dados** (ficha do cliente, só administradores): gera um .zip com todos os dados e fotos do cliente, para entregar a ele quando pedir. O arquivo `dados.html` abre no navegador e pode ser salvo em PDF.
- Modelo de aviso de privacidade para usar com os clientes: `Docs\PRIVACIDADE.md`.

## Nuvem (Google Drive)
Configurada uma vez pelo Adm Global (`NUVEM_GOOGLE_DRIVE.md`). Depois o sistema envia tudo sozinho, cifrado, segundos depois de cada alteração e ao clicar em **Encerrar**. Não há nada para clicar.
- Dois computadores gravando ao mesmo tempo revezam sozinhos (o outro espera alguns segundos).
- Cópia de segurança diária **conferida**: o sistema abre a cópia e confere o conteúdo.
- **Avisos no topo (só administradores):** cópia que falhou, cópia com mais de 2 dias, alterações há mais de 1 dia sem ir para a nuvem e conflito.
- **Sistema › Diagnóstico:** situação da nuvem e das cópias, espaço em disco, últimos erros e o botão **Gerar pacote de suporte** (sem senhas e sem dados de clientes). Usuários e senhas também ficam na nuvem: quem é criado num computador entra em todos. Computador novo: instalar e ativar com o Adm Global.

## Problemas comuns
- **"Nuvem: o Google pediu login…"** → no Apps Script, a implantação precisa estar como *Qualquer pessoa*.
- **"Outra máquina enviou dados mais novos"** → um Servidor salvou sem internet enquanto outro gravava; o Administrador escolhe qual fica valendo em Sistema → Nuvem.
- **"Sem internet: a ativação precisa de internet uma vez"** → conecte e tente de novo.
- **"Erro interno"** → tente de novo; se repetir, envie `C:\ProgramData\UStracker\UserData\Logs\erros.log` ao suporte.
- **Algo sumiu?** Veja a Lixeira. Passou de 14 dias? Use um ponto de restauração em Sistema → Nuvem.
