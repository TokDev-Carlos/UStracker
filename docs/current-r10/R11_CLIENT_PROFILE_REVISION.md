# R10 v2 — Revisão da Ficha do Cliente

Schema permanece 8. Correção cumulativa sobre o R10.

- Dados Básicos integra foto, nome, e-mail, telefone, situação e documento.
- Nome fantasia e Nome público deixam de aparecer na interface da ficha/cadastro novo.
- Situações novas: ATIVO, INATIVO e CANCELADO; BLOCKED legado continua legível e é normalizado para INATIVO ao editar.
- Apenas um documento ativo por cliente; RG/CPF/CNH substituem o documento anterior em vez de acumular.
- Empresas usam um único nome "Nome Fantasia ou Razão Social" e CNPJ opcional.
- Veículos são agrupados por tipo e só aparecem grupos com registros.
- Financeiro mostra Quantidade de Veículos, Valor Gerado Total, Compras Pagas e Despesas Geradas.
- Valor Gerado Total = recebimentos realizados + compras pagas - despesas geradas vinculadas ao cliente.
- Assinaturas mostra comprovantes eletrônicos vinculados a assinaturas e permite JPG/PNG/WebP/PDF.
- O pacote não cria clientes nem CPFs fictícios automaticamente.
