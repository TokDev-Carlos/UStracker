# Validação humana — AJ-04 Códigos lógicos

Estado: **IMPLEMENTADO, AGUARDANDO VALIDAÇÃO HUMANA**. Versão oficial permanece `1.003`; schema `10`.
Candidato: `Dist/UStracker_1.003-AJ04_win-x64` (cópia isolada; não é instalação ativa).

## O que mudou
- Cliente recebe `CLI-0001`; veículo `CLI-0001-V01`; frota `-F01`; assinatura `-A01`; compra direta `-C01`; recebimento `-R01`.
- Cobrança aparece como `CLI-0001-A01/2026-10`.
- UUID continua interno (rotas, API, banco); deixa de aparecer nas tabelas.
- Coluna "Veículo" mostra a categoria (Carro, Caminhão, Embarcação, Aeronave, Outro); código, marca, modelo e placa ficam no tooltip/secundário.
- Busca aceita código (`CLI-0001` ou `CLI-0001-V02`). Em Fotos/Arquivos, o campo de entidade aceita o código.
- Transferência de veículo: novo código no cliente destino; o antigo fica registrado como retirado e nunca é reutilizado.

## Roteiro
1. Abrir o candidato em **Test**. Registros já existentes devem aparecer com códigos (migração 9→10).
2. Clientes: coluna "Código" pequena e monoespaçada; Ficha do Cliente mostra o código no subtítulo.
3. Cadastrar cliente novo → próximo `CLI-000N`.
4. Cadastrar dois veículos e uma frota → `-V01`, `-V02`, `-F01`.
5. Frotas/Veículos: primeira coluna mostra categoria + código; passar o mouse mostra marca/modelo/placa.
6. Criar assinatura → `-A01` no Comercial; seleção de alvos mostra "Categoria · código · marca modelo · placa".
7. Registrar compra direta e recebimento → `-C01`, `-R01`; select de cobrança mostra `-A01/AAAA-MM`.
8. Arquivar um veículo e cadastrar outro → número não é reaproveitado.
9. Transferir veículo para outro cliente → recebe código do destino.
10. Pesquisa global e autocomplete por `CLI-0001`.
11. Conferir que nenhuma tabela operacional exibe UUID longo.

## Limites
- Testes leves apenas (focados AJ-04 + regressão Python/Node no Linux). Sem smoke Windows automatizado.
- Normalização de categoria é apenas de exibição até o AJ-02.
- Um banco aberto por este candidato fica no schema 10 e não abre mais na 1.003 (comportamento existente de proteção).
