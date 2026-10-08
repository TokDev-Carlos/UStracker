# Regras de negócio — UStracker

- **Cliente:** nome + 1 documento ativo (CPF, CNPJ, RG ou CNH) + ao menos um contato. Com CNPJ, vira a própria empresa principal.
- **Empresa / Frota / Veículo:** frota pertence a uma empresa do cliente; veículo pode estar numa frota ou ser particular; placa única entre ativos; categorias Carros, Motos, Caminhões, Embarcações, Outros.
- **Plano (Mensal) / Produto (Avulsa):** catálogo com preço e custo; custo só aparece para quem tem a permissão.
- **Assinatura:** plano mensal para veículos e/ou frotas marcados; quantidade automática = total de veículos (editável); gera cobrança por competência no dia do vencimento.
  - Pendente do Carlos: veículo que entra/sai da frota depois do contrato muda a cobrança sozinho?
- **Pagamento:** escolhe assinatura e meses; atrasados pagos primeiro; vira receita na data do pagamento; sobra vira crédito.
- **Despesas:** mensal, anual ou única; Gerente edita/exclui (pagamentos vão juntos para a Lixeira).
- **Lixeira:** exclusões ficam 14 dias recuperáveis.
- **Senhas/PIN:** mínimo 4 caracteres. 2.5: login único global (nuvem), offline até 1 dia.
- **Ativação:** cada computador é ativado pelo Adm Global; dados chegam da nuvem da empresa.
