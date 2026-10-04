# host — executáveis Windows (.NET)

- `Bootstrap/`: `UStracker.exe`; prepara pastas, inicia o backend e o Shell, cria atalho.
- `Shell/`: janela WPF com Microsoft WebView2 que mostra a tela.
- `Updater/`: aplica pacotes de atualização assinados (chave pública em `Trust/`).
- `Shared/`: caminhos comuns (`RootPaths.cs`).

Compilação com .NET SDK (Windows). Os binários prontos vão para o instalador.
