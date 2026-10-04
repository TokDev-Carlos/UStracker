# Nuvem do UStracker no Google Drive — guia de 5 minutos

Você faz isto **uma vez**. Depois o UStracker envia tudo sozinho, já cifrado (o Google guarda, mas não consegue ler).

## 1. Criar o script no seu Google
1. Abra **https://script.google.com** com a conta Google onde quer guardar os dados.
2. Clique em **Novo projeto**. Dê o nome **UStracker Cloud** (canto superior esquerdo).
3. Apague o conteúdo de `Code.gs` e cole **todo** o arquivo `Docs\UStracker-Cloud-Code.gs` (vem junto com o UStracker). Clique em **Salvar** (ícone de disquete).

## 2. Instalar e pegar o Código de conexão
1. Na barra de cima, escolha a função **instalar** e clique em **Executar**.
2. O Google pede autorização: **Revisar permissões** → escolha sua conta → **Avançado** → **Acessar UStracker Cloud (não seguro)** → **Permitir**.
   (O aviso aparece porque o script é seu e não foi publicado na loja do Google. Ele só usa a pasta "UStracker Cloud" do seu Drive.)
3. Abra **Registro de execução**: aparece **CÓDIGO DE CONEXÃO: …** (48 letras/números). Copie.

## 3. Publicar como App da Web
1. **Implantar → Nova implantação** → engrenagem → **App da Web**.
2. **Executar como:** Eu · **Quem pode acessar:** Qualquer pessoa.
3. **Implantar** → copie a **URL do app da Web** (termina em `/exec`).

> "Qualquer pessoa" é necessário para o UStracker conseguir falar com o script; mesmo assim só quem tem o Código de conexão consegue usar (cada pedido é assinado) e os dados já chegam cifrados.

## 4. Conectar o UStracker
1. Entre no UStracker em **REAL** → **Sistema → Nuvem**.
2. Cole a **URL** e o **Código de conexão** → **Conectar e enviar agora**.
3. A situação fica **Protegido**. Pronto.

## 5. Guarde o Kit de recuperação
Anote a **URL** e o **Código de conexão** fora do computador (papel ou cofre de senhas). Com eles e a sua senha de sempre você recupera tudo.

## Como funciona
- Envio automático uns **2 minutos** após a última alteração e ao **sair/fechar** o sistema.
- **Pontos de restauração** dos últimos **14 dias**; o mais recente **nunca** expira.
- Excluir algo **dentro do sistema** → vai para a **Lixeira (14 dias)** → depois é apagado de vez, também da nuvem.
- Apagar a pasta, formatar ou perder o computador **não apaga nada** da nuvem.
- Se outra máquina tentar enviar dados velhos, a nuvem recusa e o sistema avisa.

## Recuperar em outro computador
1. Copie a pasta do UStracker (ou o pacote) para o novo computador e abra **UStracker.exe**.
2. Na tela de entrada, clique em **Restaurar da nuvem** (ou **Já uso o UStracker: restaurar da nuvem** na configuração inicial).
3. Cole a URL e o Código, confirme e aguarde.
4. Entre com seu **usuário e senha de sempre**. Esta máquina passa a ser a escritora.
