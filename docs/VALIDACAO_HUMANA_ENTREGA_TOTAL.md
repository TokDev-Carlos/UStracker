# Validação — Entrega total (AJ-01..AJ-07 + R13..R22)

Estado: **IMPLEMENTADO COM TESTES LEVES**. Versão oficial `1.003`; schema do banco **11**.
Candidato: `Dist/UStracker_1.003-FINAL_win-x64` (cópia isolada com cópia do UserData da homologação 1.003).
Roteiros anteriores continuam válidos: `VALIDACAO_HUMANA_AJ04.md`, `VALIDACAO_HUMANA_AJ01_AJ04.md`.

## Roteiro rápido por menu
1. **Visão Geral** — Receita Geral × Previsão do Mês; bloco de veículos por categoria; período no topo dos indicadores; "Ver detalhamento" (por mês/ano e por categoria de despesa; soma = cartões).
2. **Clientes / Ficha** — cabeçalho com foto (clique troca, × remove com confirmação), chips de resumo, jornada fina só enquanto incompleta, abas: Resumo · Dados Básicos (Editar/Salvar/Cancelar) · Empresas (+ Empresa) · Veículos e Frotas (+ Veículo, + Frota com Grupo, foto por veículo) · Assinaturas e Compras · Financeiro · Arquivos.
3. **Frotas/Veículos** — aba "Por Empresa" (Cliente › Empresa › Frota › Grupo com totais), filtros Empresa e Grupo; nova frota exige Grupo (ou Misto); veículo de tipo diferente é recusado com mensagem clara; coluna Assinaturas mostra só o número — clique abre o detalhe com valores; Esc fecha.
4. **Comercial** — códigos curtos; "Abrir no Comercial" destaca a linha certa.
5. **Financeiro / Planos / Relatórios** — abas com destaque da aba ativa; mensagens de erro em português.
6. **Fotos/Arquivos** — 1) escolha cliente e registro, 2) foto, 3) anexo/link; botões ficam desabilitados até escolher o registro.
7. **Sistema** — abre em Administração; Recuperação, Integrações, Laboratório, Estações e Auditoria ficam em Desenvolvimento; "Limpar testes" e "Redefinir posição" pedem confirmação.

## Pendências para a fase de testes pesados (R23)
- Matriz 12 critérios × 9 menus; backup/restore com schema 11; restauração de backup antigo (schema 9/10).
- Smoke físico no Windows (WebView2, atalho, ícones, encerramento) e atualização real `.usup` com rollback.
- Teste com SQLCipher real (no Linux o teste específico é pulado).
- Promover `version.md` para 1.004 somente após aprovação.
