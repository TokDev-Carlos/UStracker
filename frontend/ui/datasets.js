export const DATASETS={
  clients:{
    title:'Clientes',subtitle:'Cadastros atendidos e seus vínculos operacionais.',endpoint:'/clients',createLabel:'Novo cliente',primaryField:'legal_name',
    columns:['legal_name','trade_name','public_name','document','email','phone','status']
  },
  fleets:{
    title:'Frotas',subtitle:'Agrupamentos de veículos por cliente, unidade ou setor.',endpoint:'/fleets',createLabel:'Nova frota',primaryField:'name',
    columns:['name','client_id','sector_or_unit','status','revision']
  },
  vehicles:{
    title:'Veículos',subtitle:'Ativos rastreados vinculados a clientes e frotas.',endpoint:'/vehicles',createLabel:'Novo veículo',primaryField:'plate',
    columns:['plate','type','client_id','fleet_id','renavam','tracker_serial_imei','installed_on','status']
  },
  catalog:{
    title:'Planos e Itens',subtitle:'Ofertas e componentes que podem formar assinaturas.',endpoint:'/catalog',createLabel:'Novo plano ou item',primaryField:'name',
    columns:['code','name','category','kind','price_cents','cost_cents','billing_interval_months','public','active']
  },
  subscriptions:{
    title:'Assinaturas',subtitle:'Vínculos recorrentes entre clientes e itens do catálogo.',endpoint:'/subscriptions',createLabel:'Nova assinatura',primaryField:'id',
    columns:['id','client_id','start_on','end_on','due_day','billing_cycle','lifecycle_status']
  },
  purchases:{
    title:'Compras Diretas',subtitle:'Vendas avulsas vinculadas a clientes e itens do catálogo.',
    endpoint:'/direct-sales',createLabel:'Nova compra',primaryField:'client_name',
    columns:['client_name','sold_on','status','paid_on','total_cents','item_count']
  },
  charges:{
    title:'Cobranças',subtitle:'Valores gerados por competência e respectivos ajustes.',endpoint:'/charges',createLabel:'Gerar cobrança',primaryField:'id',
    columns:['id','subscription_id','client_id','competence','due_on','amount_cents','adjustment_cents','status']
  },
  payments:{
    title:'Recebimentos',subtitle:'Pagamentos recebidos e alocados às cobranças.',endpoint:'/payments',createLabel:'Novo recebimento',primaryField:'id',
    columns:['id','client_id','paid_on','amount_cents','method','reversed_at']
  },
  credits:{
    title:'Créditos',subtitle:'Saldos favoráveis a clientes disponíveis para aplicação.',endpoint:'/credits',createLabel:'Aplicar crédito',primaryField:'id',
    columns:['id','client_id','origin_payment_id','amount_cents','balance_cents','status']
  },
  expenses:{
    title:'Despesas',subtitle:'Obrigações, custos previstos e desembolsos.',endpoint:'/expenses',createLabel:'Nova despesa',primaryField:'description',
    columns:['description','category','competence','due_on','expected_amount_cents','supplier','status']
  },
  fiscal:{
    title:'Fiscal',subtitle:'Acompanhamento manual; não transmite nem emite documento fiscal oficial.',endpoint:'/fiscal',createLabel:'Nova referência',primaryField:'description',
    columns:['competence','description','amount_cents','due_on','external_ref','status']
  },
  media:{
    title:'Fotos e anexos',subtitle:'Mídias vinculadas aos registros operacionais.',endpoint:'/media',createLabel:'Enviar mídia',primaryField:'id',
    columns:['id','entity_type','entity_id','created_at']
  }
};

export function datasetConfig(key){
  const config=DATASETS[key];
  if(!config)throw new Error(`Dataset desconhecido: ${key}`);
  return config;
}
