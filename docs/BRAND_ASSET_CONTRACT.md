# Contrato de ativos da marca

| Uso | Slot | Proporção e comportamento |
|---|---|---|
| Cabeçalho e login | `brand.logo` | Logo horizontal ou compacto, `object-fit: contain`, sem corte |
| Janela e executável | `brand.icon` | Ícone quadrado, preferencialmente 256×256, centralizado |
| Navegador | `brand.favicon` | Ícone quadrado, preservando transparência e proporção |

Os ativos rasterizados nunca devem ser esticados. O diretório `frontend/icons/default` é a
fonte visual padrão; substituições feitas pela administração são armazenadas fora do código e
expostas por `/public-assets`. Menus usam `nav.*` e comandos usam `action.*`, sempre via registro.
