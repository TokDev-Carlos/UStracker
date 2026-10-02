export const HELP={
  general:{title:'Ajuda do UStracker',summary:'Consulte aqui o objetivo da área atual e o significado dos campos operacionais.'},
  dashboard:{title:'Dashboard',summary:'Visão geral dos principais indicadores operacionais e financeiros.'},
  catalog:{
    title:'Planos e Itens',
    summary:'Cadastre o que a empresa oferece e o que pode compor uma assinatura.',
    fields:{
      code:'Identificador curto e único do plano ou item dentro do UStracker.',
      name:'Nome comercial usado pelos operadores e nas listagens.',
      category:'Agrupamento organizacional do catálogo. A categoria não altera cobrança automaticamente.',
      kind:'Plano representa um pacote comercial; Item representa um componente individual que pode compor uma assinatura.',
      price:'Valor de venda/cobrança do registro.',
      cost:'Custo interno associado ao registro; não é exibido na projeção pública.',
      billing_interval_months:'Quantidade de meses entre ciclos previstos para o plano ou item.',
      public:'Exibir no catálogo público. Isso inclui o registro na projeção pública do UStracker; não publica o sistema na internet por si só.'
    }
  },
  clients:{title:'Clientes',summary:'Cadastro estruturado com documento obrigatório, contato, empresas vinculadas, foto, mobilidade, assinaturas e compras.'},
  mobility:{title:'Frotas/Veículos',summary:'Gestão unificada de veículos particulares, frotas vinculadas às empresas do cliente e transferências de propriedade.'},
  fleets:{title:'Frotas',summary:'Compatibilidade da área antiga. A gestão principal agora fica em Frotas/Veículos.'},
  vehicles:{title:'Veículos',summary:'Compatibilidade da área antiga. A gestão principal agora fica em Frotas/Veículos.'},
  subscriptions:{title:'Assinaturas',summary:'Relação recorrente entre cliente e itens do catálogo, usada para geração de cobranças.',fields:{billing_cycle:'Periodicidade diária, mensal ou anual da assinatura; a cobrança continua por competência manual.'}},
  purchases:{title:'Compras Diretas',summary:'Registre uma compra avulsa do cliente, seus itens e a data em que o valor foi pago.'},
  charges:{title:'Cobranças',summary:'Valores gerados por competência e seus ajustes.'},
  payments:{title:'Recebimentos',summary:'Pagamentos recebidos e suas alocações em cobranças.'},
  credits:{title:'Créditos',summary:'Saldo favorável ao cliente originado de recebimentos não totalmente alocados.'},
  expenses:{title:'Despesas',summary:'Obrigações e custos previstos, com seus desembolsos.'},
  fiscal:{title:'Fiscal',summary:'Acompanhamento manual de referências fiscais. Não transmite nem emite documento fiscal oficial.'},
  media:{title:'Fotos e anexos',summary:'Mídias vinculadas aos registros operacionais.'},
  reports:{title:'Relatórios',summary:'Exportações operacionais em formatos como CSV e XLSX.'},
  system:{title:'Sistema',summary:'Administração, branding, backup, recovery, estações, auditoria e integrações.'}
};

export function helpFor(section,field){
  const page=HELP[section]||HELP.general;
  if(!field)return {title:page.title,body:page.summary};
  return {title:page.title,body:page.fields?.[field]||page.summary};
}

export const helpCatalog=HELP;
