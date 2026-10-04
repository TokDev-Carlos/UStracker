# Auditoria do baseline e do handoff

Data da auditoria: 28/09/2026  
Instalação ativa: `C:\UStracker`  
Fonte canônica: `C:\UStracker\.Arquivado\R2_source_20260915\UStracker`

## Veredito

A fonte canônica é a base adequada para outra IA editar o UStracker. Ela contém backend, frontend, hosts .NET, testes, ferramentas e documentação. Não é um repositório Git e deve ser copiada para um diretório isolado antes da implementação.

O ZIP de instalação fornecido é válido como fotografia histórica dos binários, mas não é adequado como fonte nem como backup atual de dados. Por isso ele não foi incorporado ao handoff.

## Conferências executadas

- ZIP de instalação auditado: `UStracker_1.00.01.000_instalacao_20260915_2337.zip`.
- SHA-256 do ZIP de instalação: `D7E6AE841C794D5704F9F4455B5D70EA144663AB8BD41FD2119C79B3033C025F`.
- Tamanho: `307278376` bytes.
- Estrutura: `2137` entradas, `1838` arquivos, sem caminhos inseguros e sem duplicatas.
- Fora de `UserData`, os `1508` arquivos do ZIP correspondem byte a byte à instalação ativa.
- Em `UserData`, `272` arquivos correspondem, `54` diferem e `4` do ZIP não existem mais na instalação ativa; a instalação ativa possui ainda `32` arquivos adicionais, principalmente caches e backups.
- Diferenças críticas incluem `Auth/auth.db`, `Production/ustracker.db`, projeção pública, estado de backup automático e caches WebView2.
- Fonte versus instalação ativa: `18/18` arquivos do backend e `51/51` arquivos do frontend correspondem byte a byte.
- Os executáveis publicados de Bootstrap (`UStracker.exe`), Shell e Updater também correspondem à fonte arquivada auditada.

## Plano revisado

O plano incluído em `docs/handoff/2026-09-28-ustracker-reestruturacao-incremental.md` foi ajustado para a realidade desta base. Ele parte da versão `1.00.01.000`, schema `3`, preserva a instalação ativa, define migrações até o schema `8`, checkpoints, critérios de aceite, arquivos afetados e comandos reais de teste/empacotamento.

SHA-256 do plano revisado antes da inclusão no handoff: `40C9E9CB94A543489E1B8E6B8069B98187C4B057E427F85736B915E9718846F5`.

## Resultado dos testes do baseline

| Verificação | Resultado |
|---|---:|
| Backend `test_r2_*.py` | 11 aprovados |
| Frontend `r2_ui.test.mjs` | 8 aprovados |
| `node --check frontend/app.js` | aprovado |
| `compileall` de fonte e testes | aprovado |
| Build Bootstrap | aprovado |
| Build Shell | aprovado |
| Build Updater | aprovado |

Foram observados somente `ResourceWarning` conhecidos nos testes Python e `NU1900` nos builds .NET quando o índice remoto de vulnerabilidades do NuGet não pôde ser consultado.

## Limites desta auditoria

Nenhum dado real foi aberto ou sanitizado para inclusão. Nenhuma Release foi publicada. Nenhuma alteração foi aplicada à instalação ativa. A validação funcional final de qualquer mudança futura continua exigindo smoke test do executável empacotado em Windows.
