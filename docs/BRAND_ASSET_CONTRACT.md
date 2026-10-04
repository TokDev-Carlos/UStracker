# Contrato de ativos da marca

| Uso | Slot | Proporção e comportamento |
|---|---|---|
| Cabeçalho e login | `brand.logo` | Logo horizontal ou compacto, `object-fit: contain`, sem corte |
| Janela e executável | `brand.icon` | Ícone quadrado, preferencialmente 256×256, centralizado |
| Navegador | `brand.favicon` | Ícone quadrado, preservando transparência e proporção |

Os ativos rasterizados nunca devem ser esticados. O diretório `frontend/icons/default` é a
fonte visual padrão; substituições feitas pela administração são armazenadas fora do código e
expostas por `/public-assets`. Menus usam `nav.*` e comandos usam `action.*`, sempre via registro.

## Dimensões verificadas (R17)

| Slot | Arquivo padrão | Tamanho | Regra de exibição |
|---|---|---|---|
| `brand.logo` | `brand/logo.png` | 1024×1024 | `.brand-logo` 32–44 px e `.r2-login-logo` até 220×88 px, sempre `contain` |
| `brand.icon` | `brand/icon.png` | 512×512 | quadrado obrigatório |
| `brand.favicon` | `brand/favicon.png` | 256×256 | quadrado obrigatório |
| `host/*/Assets/UStracker.ico` | ícone da janela e do atalho | multi-resolução | conferir no Windows |

Teste estático: `tests/r17_brand_assets.test.mjs`.
