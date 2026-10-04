# Manual do Usuário — UStracker 1.007

## Instalar
1. Execute **install_UStracker.exe** e siga as telas (pasta sugerida: `C:\UStracker`).
2. Abra pelo atalho **UStracker** na Área de Trabalho ou no Menu Iniciar.
3. **Primeiro computador da empresa:** cadastre o Administrador 1.
   **Outros computadores:** a tela já pede **usuário e senha** — os dados da empresa chegam sozinhos e o computador vira o próximo **Servidor**.

Atualizar é igual: execute o instalador novo por cima. Seus dados (`UserData`) não são tocados.

## Usuários e pacotes
- Administrador cria pessoas em **Sistema › Usuários** (nome de acesso, senha inicial e pacote).
- **Operador**: cria e atualiza clientes, veículos, planos e registra pagamentos. Não exclui, não estorna, não vê despesas nem custos.
- **Gerente**: tudo do Operador + excluir, estornar, despesas, fiscal, custos, relatórios e Lixeira. Sem o menu Sistema.
- Pacotes próprios: **+ Novo pacote** e marque o que pode.
- Cada um troca a própria senha clicando no nome, no topo.

## Entrar
- **Real** = dados de verdade. **Teste** = área de treino, separada (pode apagar à vontade).
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
Configure uma vez seguindo `NUVEM_GOOGLE_DRIVE.md`. Depois o sistema envia tudo sozinho, cifrado, segundos depois de cada alteração e ao fechar. Guarde a **URL** e o **Código de conexão** fora do computador.

## Problemas comuns
- **"Nuvem: o Google pediu login…"** → no Apps Script, a implantação precisa estar como *Qualquer pessoa*.
- **"Outra máquina enviou dados mais novos"** → um Servidor salvou sem internet enquanto outro gravava; escolha qual fica valendo em Sistema → Nuvem.
- **Algo sumiu?** Veja a Lixeira. Passou de 14 dias? Use um ponto de restauração em Sistema → Nuvem.
