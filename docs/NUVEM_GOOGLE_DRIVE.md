# Guia do dono — nuvem da empresa (Google) e placa de direção

Você faz isto **uma vez**. Depois cada computador com o UStracker vira um **Servidor** da empresa: instala, entra com usuário e senha e já trabalha com os mesmos dados.

## 1. Banco na nuvem (script no seu Google) — já feito se a Nuvem está "Protegido"
1. **https://script.google.com** → Novo projeto **UStracker Cloud** → cole todo o `Docs\UStracker-Cloud-Code.gs` → Salvar.
2. Escolha **instalar** → Executar → autorize (Avançado → Acessar → Permitir). Copie o **CÓDIGO DE CONEXÃO** do Registro de execução.
3. **Implantar → Nova implantação → App da Web**, Executar como **Eu**, acesso **Qualquer pessoa** → copie a URL `/exec`.
4. Atualizou o script (versão nova do UStracker)? Cole o código novo, Salvar, **Implantar → Gerenciar implantações → editar → Nova versão**. A URL não muda.

## 2. Onde guardar a placa (GitHub, grátis)
1. Crie uma conta em github.com e um repositório **público** (ex.: `ustracker-config`). A placa é assinada e as chaves vão cifradas: ver o arquivo não dá acesso a nada.
2. Crie um token: Settings → Developer settings → **Fine-grained tokens** → só esse repositório → permissão **Contents: Read and write**.

## 3. Publicar a placa (no UStracker, como Administrador)
**Sistema → Nuvem → Placa de direção**:
```
#Banco 1
Endereço Web: https://script.google.com/macros/s/…/exec
Chave de Conexão: …

#Banco 2      (opcional: cópia em outra conta Google)
Endereço Web: …
Chave de Conexão: …
```
Preencha repositório, arquivo (`placa.json`) e token → **Publicar placa**. Pronto: o arquivo `Instalador\placa-bootstrap.json` é criado ao lado do instalador.

## 4. Levar para outro computador
Copie a pasta **`C:\UStracker\Instalador`** inteira (o `install_UStracker.exe` + `placa-bootstrap.json`). No computador novo: execute o instalador → abra o UStracker → **entre com usuário e senha**. Ele baixa os dados e vira o próximo Servidor.

## Trocar de conta Google (sem parar ninguém)
1. Faça o passo 1 na conta nova. 2. Acrescente-a como **Banco 2** e publique. 3. Quando aparecer **em dia** no Banco 2, inverta (a nova vira **Banco 1**) e publique. 4. Depois de alguns dias, apague o banco antigo da placa e publique.

## Como funciona no dia a dia
- Um Servidor grava por vez; a vez passa sozinha em segundos. Se outro estiver salvando, aparece "Aguardando Servidor N…" e o sistema tenta de novo.
- O que um Servidor grava aparece nos outros em até ~30 segundos.
- Sem internet: o sistema continua salvando no computador e envia quando a conexão voltar (se outro Servidor gravou nesse meio-tempo, ele avisa "conflito").
- **Painel**: no editor do Apps Script escolha **painel** → Executar → veja Servidores, último envio e espaço usado (alerta perto de 15 GB).
