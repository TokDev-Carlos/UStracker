# DECISÕES HUMANAS CAPTURADAS

Este arquivo preserva decisões fornecidas pelo usuário para que outra IA não dependa do histórico
da conversa. Em caso de nova solicitação humana explícita, a solicitação mais recente prevalece.

## Versionamento

- `version.md`, na raiz, é o único local de registro e referência da versão.
- O padrão é `1.000`, com três casas após o ponto.
- Metadados derivados devem ser sincronizados a partir de `version.md`.

## Produto e execução

- Preservar o padrão visual e funcional aprovado.
- Melhorias de organização e processo são permitidas dentro do escopo.
- Entender regras de negócio e handoff antes de alterar o produto.
- Trabalhar isoladamente; não tocar a instalação ativa ou dados reais sem autorização específica.
- O checkpoint acelerado foi solicitado sem testes funcionais, seguido de validação humana básica.
- Por isso R13–R23 não podem ser tratados como aprovados apesar de haver código implementado.

## Ajustes mais recentes

- Dividir Receita Geral visualmente com Previsão do Mês; previsão não entra no Resultado.
- Detalhar veículos por Carros, Caminhões, Embarcações, Aeronaves e Outros, com ícones e totais.
- Integrar cadastro de cliente, veículo/frota, plano, assinatura/compra e projeções em tempo real.
- Corrigir o caso de assinatura existente no Comercial e valor enganoso `R$ 0,00` na Visão Geral.
- Ocultar IDs técnicos longos nas tabelas e criar códigos lógicos curtos vinculados ao cliente.
- Nas colunas de veículo, mostrar como valor principal o tipo, não UUID, nome ou placa.

As definições completas e critérios de aceite estão em `docs/FLUXO_AJUSTES_POS_VALIDACAO.md`.

## Palavras de coordenação fornecidas

Foram fornecidas as seguintes palavras, sem semântica adicional definida no repositório:

- `keyWord`
- `BrainMain`
- `RecapLine`
- `CloneMemory`
- `InputAndOutput`
- `DB_Dynamics`
- `ShutDown`
- `TakeOwn_And_RecapClone`

Não invente comportamentos para essas palavras. Preserve-as como contexto até que o usuário defina
seu significado operacional.
