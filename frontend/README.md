# frontend — telas

HTML + módulos ES, sem framework e sem build. Carregado pelo Shell (WebView2) a partir da API local.

- `index.html`, `styles.css`, `app.js`: entrada, roteamento e telas principais.
- `pages/`: telas por assunto (clientes, nuvem e placa, usuários…).
- `ui/`: componentes (tabelas, diálogos, menus de ação, permissões, login).
- `icons/`: conjunto de ícones.

Testes: `node --test tests/*.test.mjs` (na raiz).
