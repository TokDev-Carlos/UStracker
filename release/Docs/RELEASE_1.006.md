# UStracker 1.006 — versão oficial

Data: 2026-10-04 · Schema do banco: **14** · Windows 10/11 x64 · Instalador: `install_UStracker.exe`

## Novidades
- **Instalador** `install_UStracker.exe`: instala ou atualiza (mantém `UserData`), cria atalhos, desinstalação pelo Windows. Em computador novo, "restaurar da nuvem" traz tudo.
- **Excluir veículo e frota** (Frotas/Veículos, ficha do cliente e ficha da frota), com Lixeira de 14 dias e "Desfazer".
- **Sem órfãos:** excluir cliente leva junto as frotas e veículos dele; os que já tinham ficado sem dono foram limpos na atualização.
- **Placa já cadastrada:** aviso ao digitar e janela com foto, veículo, cliente e frota.
- **Fotos de veículo** inteiras (sem corte), cartão lateral com **×** para remover, igual à foto do cliente.
- **Área de veículos** da ficha alinhada: Placa · Marca/Modelo · Tipo · Empresa › Frota · Assinaturas · Ações.
- **Janelas próprias** no lugar das caixas do navegador; remover foto tem "Desfazer".
- **Nova assinatura** mostra os veículos em cartões com miniatura e explica o que é uma assinatura.
- **Nuvem:** mensagens de erro dizem a causa (URL errada, implantação não pública, antivírus/proxy, sem internet).
- **Usabilidade:** clicar na linha do cliente abre a ficha; abas cabem no celular; tamanhos de backup legíveis; textos revisados.
- **Correção:** menu "Ações" das assinaturas fechava sozinho ao rolar a página.

## Atualização dos dados
No primeiro login o banco vai do schema 13 para o 14 (só limpeza de frotas/veículos de clientes já excluídos; nada de financeiro muda). O backup automático do login roda antes.

## Verificação
101 testes Python + 71 testes de interface, jornada completa 27/27 sem erros, matriz de telas em 3 tamanhos, varredura da API sem erro 500, nuvem pesada (9 MB em partes, 60 fotos, 12 envios, retenção de 14 dias e restauração em computador novo).
