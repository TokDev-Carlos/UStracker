# UStracker 1.00.01.000 — Manual resumido da reestruturação schema 8

## Navegação final
- Visão Geral
- Clientes
- Frotas/Veículos
- Planos/Produtos
- Comercial
- Financeiro
- Fotos/Arquivos
- Relatórios
- Sistema

## Visão Geral
Indicadores operacionais ficam no topo. A busca contextual aceita Enter, Pesquisar e Limpar. A tabela de clientes mostra atividade, veículos, compras e Valor Gerado. Valor Gerado considera apenas recebimentos realizados e compras pagas.

## Clientes
O cadastro exige nome, ao menos um documento (CPF, RG ou CNH) e ao menos um contato (e-mail ou telefone). Empresas podem ser múltiplas. A exclusão é lógica/arquivamento. A ficha reúne dados básicos, empresas, documentos, contatos, foto, mobilidade, assinaturas/arquivos e compras.

## Frotas/Veículos
Veículo sem frota é Particular. Frota precisa estar vinculada a uma empresa do cliente e começa com limite de 100 veículos ativos. Transferências ficam PENDING antes de alterar a propriedade; COMPLETED efetiva a mudança e CANCELLED preserva a propriedade vigente.

## Planos/Produtos
O código é automático no padrão PRD001, PRD002... A categoria é Avulsa ou Mensal. O custo é calculado exclusivamente pelos componentes cadastrados e o histórico de preços/custos é preservado.

## Comercial
Abas: Assinaturas, Compras Diretas e Créditos/Tempo Ativo. Compras Diretas aceitam apenas produtos Avulsa. Crédito financeiro e cobertura temporal são conceitos separados. Cobertura é calculada por meses de calendário.

## Financeiro
Abas: Recebimentos, Despesas e Fiscal. O módulo mantém o livro-razão existente. Uma obrigação Fiscal com valor cria/vincula uma única despesa, de forma idempotente.

## Fotos/Arquivos
Fotos operacionais permanecem no repositório de mídia. Anexos aceitam JPG, JPEG, PNG, WebP, PDF ou link HTTP/HTTPS. Arquivos locais são cifrados; assinatura real do arquivo e MIME são validados. Conteúdo executável não é aceito. O armazenamento Google Drive permanece desativado até integração futura.

## Formatos
Valores monetários são armazenados em centavos inteiros e apresentados em padrão brasileiro, por exemplo `R$ 1.234,56`. Campos monetários são texto, sem setas de incremento. Datas aparecem em formato brasileiro na interface.

## Homologação segura
Nunca extraia um pacote de homologação sobre `C:\UStracker`. O homologador cria uma cópia isolada em `%LOCALAPPDATA%\UStracker-Homologacao\R10\current`, aplica o overlay cumulativo e executa apenas essa cópia.
