# Manual do Usuário — UStracker 1.00.01.000

## Instalação portátil
Extraia `UStracker_1.00.01.000_win-x64.zip` em uma pasta local do Windows 10/11 x64 e execute `UStracker.exe`. Não opere o produto a partir de pasta de rede, compartilhamento SMB ou diretório sincronizado. `UserData` é o estado local da instalação.

## Primeiro acesso
Crie o Administrador 1 e use os dois tickets de uso único, válidos por 15 minutos, para cadastrar os Administradores 2 e 3. São exatamente três slots administrativos.

## Ambientes
- **Production:** dados reais. Somente a estação designada como escritora pode alterar dados.
- **Test:** laboratório isolado com banco e mídia próprios. `LIMPAR TESTES` recria somente Test.

## Fluxo operacional
Cadastre Clientes → Frotas → Veículos → Planos/Itens → Assinaturas. Gere cobranças por competência. Registre pagamentos e respectivas alocações; saldo excedente somente vira crédito quando escolhido. Créditos podem ser aplicados a novas cobranças. Pagamentos podem ser estornados sem apagar o histórico. Cadastre despesas, desembolsos, recorrências e referências fiscais manuais.

## Fotos e branding
A área Fotos aceita imagens vinculadas a entidades. O sistema remove metadados operacionais ao reencodar, cria miniatura e cifra o conteúdo. Em Sistema é possível trocar logo, favicon, ícone e cores públicas.

## Backup
Use **Sistema → Criar backup**. Backups `.usbk` são cifrados e validados. Ao fazer login em Production, o sistema cria backup automático quando o último automático tem 24 horas ou mais. A retenção padrão é 14 arquivos e pode ser alterada em Sistema.

O restore recebe `.usbk`, valida ambiente/integridade e mantém cópia pré-restore do banco durante a operação.

## Recovery
Recovery `.usre` é diferente do backup comum: inclui AuthStore/Vault, Production, Test, mídia e projeção pública e usa uma passphrase externa de pelo menos 12 caracteres.

Para importar em outra instalação, encerre o UStracker e execute na pasta do produto:

```powershell
.\Runtime\python.exe -m ustracker.recovery import --package "C:\caminho\recovery.usre" --destination "." --passphrase "SUA PASSPHRASE"
```

A importação substitui somente os grupos recuperáveis em `UserData`; arquivos do aplicativo e backups locais não são apagados.

## Transferência da estação escritora
Na máquina escritora, use **Sistema → Recovery e transferência → Preparar transferência**. A máquina de origem deixa de ser escritora antes do pacote ser criado. Importe o `.usre` na nova instalação com o sistema encerrado. Na primeira abertura, a nova estação registra identidade própria e assume a geração transferida. Não copie um banco aberto manualmente.

## Atualização
Encerre o sistema antes de executar `UStracker.Updater.exe pacote.usup`. O updater recusa backend ativo, valida assinatura/hashes, cria rollback dos arquivos do produto, faz staging, switch, verificação final e só então aceita a versão.

## Encerramento
Fechar a janela revoga a sessão do Shell. **Encerrar sistema** finaliza o backend local cooperativamente.
