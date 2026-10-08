---
paths:
  - "host/**/*"
---
# Host .NET (WebView2) e Updater
- O host abre o backend Python do `Runtime/` e o WebView2; o Updater aplica `.usup` com volta automática.
- Não alterar sem build/teste no Windows real (o build roda no PC, não na nuvem).
