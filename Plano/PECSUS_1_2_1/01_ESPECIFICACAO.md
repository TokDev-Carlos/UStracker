# Especificação consolidada UStracker — PECSUS 1.2.1

**Produto inicial:** 1.00.00.000  
**Revisão documental:** 1.2.1  
**Estado:** G0_FECHADO — pronto para iniciar T01/G1  
**Data:** 12/09/2026 — America/Sao_Paulo

## 1. Autoridade e escopo
O UStracker é um terceiro produto independente. ASCALPI e Automação de Artes são referências arquiteturais; nenhum domínio alheio é herdado automaticamente. O objetivo é substituir controles dispersos por gestão local de clientes de rastreamento, veículos/frotas, planos, contratos, cobranças, recebimentos, créditos, despesas, acompanhamento fiscal manual, fotos, dashboards e relatórios.

A V1 é **offline-first/local-first**. Google Drive, rastreamento externo, emissão fiscal oficial, hosting, GitHub operacional, WhatsApp/e-mail automático, PDF oficial e multiwriter offline são fronteiras futuras desativadas.

O documento histórico continua fonte de intenção. A nova `MATRIZ_ESCOPO_HISTORICO.csv` resolve cada item auditado como MANTER/SUBSTITUIR/ADIAR/EXCLUIR/RESOLVIDO/ADICIONAR. Nenhum item pode ser silenciosamente descartado pela executora.

## 2. Requisitos normativos R01–R36
- **R01:** Identidade UStracker e finalidade de controle local/offline-first independente dos sistemas de referência.
- **R02:** Acesso exclusivamente PUBLIC e ADMIN; PUBLIC nunca recebe dados privados.
- **R03:** Exatamente três slots administrativos individualizados, bootstrap fechado e enrollment obrigatório.
- **R04:** Sessão administrativa segura, CSRF, autorização backend, revogação e lifecycle de janela sem reaparecimento de sessão.
- **R05:** Cadastro completo de clientes: razão/nome, nome fantasia, nome público opcional, documento, contatos, endereço, observações e status.
- **R06:** Veículos e frotas: placa histórica/Mercosul, tipo, RENAVAM opcional, rastreador/serial/IMEI, instalação, status e histórico de propriedade.
- **R07:** Catálogo editável de planos/itens com código, categoria, periodicidade, preço/custo, observações, publicação e histórico de preços.
- **R08:** Assinaturas versionadas com data de assinatura/início/fim, renovação, periodicidade, itens/veículos e competências idempotentes.
- **R09:** Recebimentos: pagamentos parciais, alocações, crédito do cliente, ajustes, vencimento, juros/multa manuais e estorno sem edição destrutiva.
- **R10:** Despesas previstas/pagas, recorrências e vínculos opcionais a cliente, veículo, assinatura e item/serviço.
- **R11:** Acompanhamento fiscal manual, referências/obrigações e prevenção de dupla contagem; sem emissão/transmissão oficial na V1.
- **R12:** Resultados por caixa e competência, dashboard completo, próximos vencimentos, inadimplência, distribuição por plano, busca global e relatórios.
- **R13:** Dinheiro BRL em centavos inteiros/Decimal e política de arredondamento versionada e reproduzível.
- **R14:** Interface organizada, responsiva, acessível, tabelas com busca/filtro/ordenação/paginação e estados de erro/empty/loading.
- **R15:** Branding/configuração administrável: nomes da empresa/sistema, logo, favicon, ícones, cores, contato, textos permitidos e rodapé protegido.
- **R16:** Fotos validadas, reencodadas, comprimidas, com miniaturas, metadados removidos, privadas, cifradas e recuperáveis.
- **R17:** SQLCipher, mídia AEAD, cofre por envelopes, hash, audit trail before/after sanitizado e gestão segura de chaves.
- **R18:** Pacote Windows x64 portátil: Python 3.13.15 embutido, Host WPF .NET Framework 4.8 e WebView2; sem SDK no cliente.
- **R19:** Launcher/Host WebView2, instância única, backend persistente, reabertura pública limpa e encerramento cooperativo.
- **R20:** Até três estações registradas, exatamente uma escritora por dataset/generation e transferência manual; sem multiwriter offline.
- **R21:** Persistência transacional, revisão otimista, idempotência, journal de arquivos e recuperação de queda.
- **R22:** Backups automáticos/manuais, restauração testada, recuperação, retenção e export de recuperação separado.
- **R23:** Patch manual assinado, staging, migração em cópia, aceite e rollback sem perder dados posteriores.
- **R24:** Versionamento BA/ES/IN/SE e autoridade única VERSION.json/current.json.
- **R25:** Ambiente de testes totalmente isolado de produção e reset seguro sem apagar AuthStore.
- **R26:** Google Drive preparado por interface/configuração não secreta e explicitamente desativado na V1.
- **R27:** Integração fiscal oficial preparada por interface e explicitamente desativada na V1.
- **R28:** Integração de rastreamento preparada por interface e explicitamente desativada na V1.
- **R29:** Arquitetura separa domínio/API/arquivos/integrações para futura hospedagem sem criar dependência online na V1.
- **R30:** GitHub não é requisito operacional da V1; sem credenciais, repositório remoto ou workflow obrigatório.
- **R31:** Revisão inline por função, gate por tarefa e integração completa com evidências reproduzíveis.
- **R32:** Somente defeitos não bloqueantes podem entrar em AJUSTES_FUTUROS.log; segurança/dados/valores/update não são adiáveis.
- **R33:** Entrega reproduzível com binários, código-fonte ao proprietário, SBOM/licenças, hashes, snapshot, manuais e recovery.
- **R34:** Erros compreensíveis, logs sem segredos/PII desnecessária, correlation id e ações críticas auditadas.
- **R35:** Copyright CRJ preservado e separado do branding personalizável e licenças de terceiros.
- **R36:** Retomada por outra IA via checkpoint, hashes, matriz requisito→tarefa→caso→evidência e invalidação seletiva de provas.

## 3. Decisões G0 fixadas
### D01
PUBLIC só recebe projeção allowlist (marca, catálogo/preço publicado e public_name explicitamente publicado). ADMIN: exatamente três slots com mesmos poderes e autoria individual.

### D02
Bootstrap: senha inicial admin só em instalação vazia. Slot 1 troca nome/senha; emite enrollment tickets de uso único/15 min para slots 2/3. Reset de outro admin volta o slot a PENDING_ENROLLMENT e emite novo ticket; o admin que reseta nunca escolhe/conhece a nova senha.

### D03
Sessão: token 256-bit em memória, cookie HttpOnly/SameSite=Strict, idle 60 min, absoluto 12 h; polling não renova. X da janela revoga a sessão daquele Shell; ao terminar a última sessão, jobs privados pausam em checkpoint e conexões/chaves são liberadas. Fecha o profile WebView2 e remove seus arquivos após os processos liberarem os handles. Nova Shell usa profile novo e abre PUBLIC_UI.

### D04
Uma escritora por dataset/generation; até três estações. Transferência manual fechada; nada de SQLite em UNC/SMB/sincronizador e nada de merge offline automático.

### D05
BRL; centavos inteiros em DB; Decimal no cálculo; HALF_EVEN default versionado; ajustes manuais de juros/multa/desconto/pró-rata exigem tipo, motivo e competência. Nenhuma regra tributária inventada.

### D06
Assinatura registra contrato existente; alteração cria versão efetiva. Status contratual ACTIVE/PAUSED/CANCELLED/ENDED; AWAITING_PAYMENT/OVERDUE são estados financeiros derivados, não lifecycle duplicado.

### D07
Cliente mantém legal_name, trade_name, public_name e status ACTIVE/INACTIVE/BLOCKED/CANCELLED. Documento é opcional por default, mas único quando presente.

### D08
Veículo mantém tipo, RENAVAM opcional, tracker_ref, tracker_serial_imei, installed_on e tracking_status. Plano/valor mensal não ficam duplicados no veículo: são derivados da assinatura vigente.

### D09
Catálogo mantém code, category, billing_interval_months, notes, price/cost e histórico. Categorias do catálogo são editáveis e separadas de categorias de despesas.

### D10
Pagamentos suportam parcial, alocação e crédito explícito. Valor não alocado só vira crédito com create_credit=true; crédito pode ser aplicado depois e é reversível/auditado.

### D11
Despesas podem ligar client_id, vehicle_id, subscription_id e catalog_id. Equipamento/serviço específico é representado por catalog_id e, quando instalado em veículo, também vehicle_id.

### D12
Dashboard V1 inclui próximos vencimentos, inadimplentes, distribuição por plano e estado de integrações. “Sincronização” mostra DESATIVADA/PREPARADA, nunca simula Drive.

### D13
Personalização V1 inclui nomes, logo/favicon/ícones, paleta permitida, contato e textos configuráveis. Copyright/licenças e mensagens de segurança não são sobrescrevíveis.

### D14
Audit event guarda before_json/after_json sanitizados quando aplicável, mais hash chain; nunca senha, VRK, DB key, token, cookie ou foto binária.

### D15
AuthStore é compartilhado; VaultStore tem uma VRK (Vault Root Key) aleatória. Cada senha de admin deriva KEK via scrypt e cifra um envelope da mesma VRK. Production/Test possuem chaves distintas cifradas pela VRK. Reset Test gera novas chaves Test e não toca AuthStore/Production.

### D16
Backups: LOCAL_BACKUP_V1 usa chave por backup derivada da VRK (HKDF-SHA256) e payload chunked AES-256-GCM; RECOVERY_EXPORT_V1 usa scrypt de passphrase externa e não persiste a passphrase. Transferência de estação usa pacote separado por target/generation.

### D17
Plataforma: Host/Bootstrap/Updater WPF C# target .NET Framework 4.8 x64 + Microsoft.Web.WebView2 1.0.4191.47. Windows 10 22H2 x64 é a base de homologação usada pelo proprietário. Windows 10 e Windows 11 x64 são plataformas de funcionamento do produto. A disponibilidade de Windows 11 não é condição para avançar ou homologar a entrega no Windows 10. Não usar .NET 10 no Host V1.

### D18
Runtime Python V1: CPython 3.13.15 x64 embeddable; SHA-256 oficial esperado d1f04d990aee1253d8569e8e5104e30fa9f5fa830899f14843448872d936a2cf. SQLCipher binding base: sqlcipher3 0.6.2 cp313 win_amd64; SHA-256 esperado do wheel 9dc959ff792228c6df836cfd3667c713ae13e6e18dc2905c9d5666558606e832. T01 confirma assinatura/origem/licença e PRAGMA cipher_version.

### D19
Exports V1: CSV UTF-8-SIG e XLSX; ambos admin-only e com prevenção de formula injection. PDF estruturado fica para versão futura; impressão do navegador não é declarada export PDF oficial.

### D20
Fotos: original descartado por padrão; retenção de original é opt-in por foto/config e original retido é cifrado. JPEG/PNG/WebP, até 20 MiB e 40 MP; operacional até 1920 px, thumb 320 px.

### D21
Retenção técnica default: backups 7 diários + 4 semanais + 3 mensais; pré-update até existir sucessor aceito. Dados/auditoria não têm purge automático por default; política organizacional deve ser configurada antes de uso produtivo, sem alegar prazo legal universal.

### D22
Performance de homologação P1: seed sintético 5.000 clientes, 15.000 veículos, 100.000 cobranças, 60.000 pagamentos, 40.000 despesas, 10.000 metadados de fotos. Busca P95 <=1,5 s e dashboard período de 12 meses <=3 s no hardware de homologação registrado; sem perda/erro/duplicidade.

### D23
Drive/rastreamento/fiscal oficial/hospedagem/GitHub/WhatsApp/e-mail automático/PDF oficial/multi-filial simultânea ficam fora da V1. Interfaces existem e executam 501/Disabled sem rede.

### D24
Código-fonte acompanha a entrega ao proprietário em Source.zip/snapshot com hashes; pacote de usuário final pode conter só binários/runtime/assets/licenças.

## 4. Matriz de plataforma
| Nível | SO | Host | Status de produto |
|---|---|---|---|
| Base de homologação | Windows 10 22H2 x64 | WPF .NET Framework 4.8 x64 + WebView2 | T18 exige PASS |
| Plataforma de funcionamento | Windows 11 x64 | Mesmo Host net48 + WebView2 | registrar testes quando disponível; ausência não bloqueia homologação no Windows 10 |
| Fora | x86, ARM64, Windows <10, Linux/macOS como cliente | — | V1 não entrega |

O cliente não precisa de Python/.NET SDK/Node. Python 3.13.15 x64 acompanha o produto. O Host usa .NET Framework 4.8 do Windows; WebView2 é verificado/provisionado. Ferramentas de build ficam somente no ambiente de engenharia.

## 5. Fluxo de segurança e dados
```text
PUBLIC_UI
  -> Public/view.json allowlist (Production)
  -> nunca desbloqueia SQLCipher

ADMIN LOGIN
  -> scrypt(password) => KEK
  -> unwrap VRK do slot
  -> VRK unwrap Production/Test DB/media keys
  -> Session(environment)
  -> StorageFactory(DatabaseKeyProvider)
  -> SQLCipher + Media AEAD
```

`X` na janela não encerra o backend, mas **revoga a sessão daquela Shell, fecha seu perfil WebView2 e remove o cache após liberação dos handles**. Reabrir o executável abre PUBLIC_UI. Minimizar a janela não equivale a fechar.

## 6. Dados reais e laboratório
Production começa vazio e recebe apenas dados cadastrados pelo operador. Test é um dataset fisicamente separado com keys próprias e banner permanente. Fixtures são fictícias/anonimizadas. Dados reais nunca entram em snapshots técnicos, testes automatizados ou pacote de distribuição.

## 7. Definições de “pronto”
- G0: esta revisão documental + validação sem referências quebradas — **FECHADO nesta entrega**.
- T01/G1: foundation native PASS no Windows 10 22H2 — primeiro gate de código. Windows 11 é verificação adicional de compatibilidade, registrada separadamente.
- T02–T17: cada gate depende do anterior, com review inline/function.
- T18: integração completa + Windows 10 22H2 native PASS + rastreabilidade 100% dos itens obrigatórios.
- `BLOQUEADO`/`NAO_EXECUTADO` nunca são convertidos em PASS por leitura de código.

## 8. Itens pré-produção que não bloqueiam a criação
Antes de colocar dados reais em produção, o proprietário deve configurar identidade empresarial final, política organizacional de retenção/consentimento/incidente e backups externos. O software fornece controles para isso; o PECSUS não inventa obrigação legal ou prazo universal.

## 9. Limites operacionais explicitados na revisão 1.2
- Uma escritora é garantida pelo protocolo nas estações participantes, não por uma autoridade remota inexistente. Clone integral de disco/VM ou cópia antiga deliberadamente reativada offline não pode ser revogado à distância. Recovery exige retirar essas cópias de uso administrativamente; não alegar prevenção absoluta de split-brain contra clonagem.
- Protocolo financeiro e relatórios são regras internas de gestão, sem afirmação de conformidade fiscal/legal automática.
- Esta revisão alinha documentos e cenários. Aprovação documental não certifica software sem defeitos; os casos do produto permanecem NAO_EXECUTADO até evidência real.

## Política de plataforma corrigida em 1.2.1
Windows 10 22H2 x64 é a base de homologação. O mesmo produto deve funcionar em Windows 10 e Windows 11 x64, sem bloqueio de inicialização por escolher qualquer um desses sistemas. Gates T01/T16/T18 usam win10_22h2 por padrão; windows11 permanece perfil aceito para ensaios adicionais. Falha funcional comprovada em qualquer plataforma-alvo deve ser corrigida; indisponibilidade de Windows 11 não é falha funcional nem bloqueia avanço/entrega homologada no Windows 10. Não declarar teste executado quando ele não ocorreu.
