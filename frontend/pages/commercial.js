import { formatBRL, formatDateBR } from '../ui/formatters.js';
import { renderEntityAutocomplete } from '../ui/entity-autocomplete.js';
import { codeTag, vehicleCells, vehicleRef } from '../ui/logical-codes.js';
const esc=s=>String(s??'').replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
const options=(items,value,label,blank='')=>`${blank?`<option value="">${blank}</option>`:''}${(items||[]).map(x=>`<option value="${esc(x[value])}">${esc(x[label]??x[value])}</option>`).join('')}`;
export function coverageRemaining(endAt,now=new Date()){
  const end=new Date(/T/.test(endAt)?endAt:endAt+'T00:00:00'); const ms=end-now;
  if(ms<=0)return 'Expirado'; const days=Math.ceil(ms/86400000); return `${days} dia${days===1?'':'s'}`;
}
const SUB_STATUS={ACTIVE:['Ativa','badge-ok'],PAUSED:['Pausada','badge-warn'],CANCELLED:['Cancelada','badge-muted'],ENDED:['Encerrada','badge-muted']};
const compLabel=c=>{const m=String(c||'').match(/^(\d{4})-(\d{2})/);return m?`${m[2]}/${m[1]}`:'—'};
function paidCell(x){
  if(x.lifecycle_status!=='ACTIVE'&&x.lifecycle_status!=='PAUSED')return '<span class="muted">—</span>';
  const late=Number(x.overdue_months||0);
  return `${x.paid_through?compLabel(x.paid_through):'<span class="muted">Nenhum</span>'}${late?` <span class="badge badge-alert" title="Meses em atraso">${late} em atraso</span>`:''}`;
}
function targetCells(x){
  const fleets=(x.targets||[]).filter(t=>t.target_type==='FLEET').map(t=>`<span class="fleet-chip" title="Frota">${esc(t.fleet_name||'Frota')}</span>`).join(' ');
  const vehicles=(x.vehicles||[]).length?vehicleCells(x.vehicles):'';
  return [vehicles,fleets].filter(Boolean).join(' ')||'—';
}
function subRows(items){return items.map(x=>{const [label,cls]=SUB_STATUS[x.lifecycle_status]||[x.lifecycle_status,''];return `<tr data-row-code="${esc(x.code||'')}"><td>${codeTag(x.code)||'—'}</td><td>${esc(x.client_name)}</td><td>${esc((x.plans||[]).map(p=>p.name||p.code).join(', ')||'—')}</td><td>${targetCells(x)}</td><td class="num">${formatBRL(x.total_cents)}</td><td>${paidCell(x)}</td><td><span class="badge ${cls}">${esc(label)}</span></td><td><button type="button" class="ui-btn ui-btn-secondary ui-btn-sm action-menu-btn" data-sub-actions="${esc(x.id)}" aria-haspopup="menu" aria-expanded="false">Ações <span aria-hidden="true">▾</span></button></td></tr>`}).join('')||'<tr><td colspan="8" class="muted">Nenhuma assinatura.</td></tr>'}
/** Items of the per-subscription "Ações" menu (labels only; app.js binds the behaviour). */
export function subscriptionMenuItems(x={}){
  const open=x.lifecycle_status==='ACTIVE'||x.lifecycle_status==='PAUSED';
  return [
    {key:'pay',label:'Registrar pagamento',hint:x.paid_through?`Pago até ${compLabel(x.paid_through)}`:'Nenhum mês pago',primary:true,hidden:x.lifecycle_status!=='ACTIVE'},
    {key:'amend',label:'Ajustar plano, valor ou veículos',hidden:!open},
    {key:'purchase',label:'Compra direta para este cliente'},
    {key:'profile',label:'Abrir ficha do cliente'},
    {separator:true,hidden:!open},
    {key:'pause',label:'Pausar assinatura',hidden:x.lifecycle_status!=='ACTIVE'},
    {key:'resume',label:'Reativar assinatura',hidden:x.lifecycle_status!=='PAUSED'},
    {key:'cancel',label:'Cancelar assinatura',danger:true,hidden:!open},
  ];
}
export function renderSubscriptionAmendForm(sub={},{catalog=[],vehicles=[],fleets=[]}={}){
  const items=(sub.items||[]).length?sub.items:[{catalog_id:'',quantity:1,unit_price_cents:0}];
  const planOptions=sel=>catalog.filter(c=>Number(c.active??1)===1||c.id===sel).map(c=>`<option value="${esc(c.id)}" data-price="${Number(c.price_cents||0)}"${c.id===sel?' selected':''}>${esc(c.name)} · ${esc(formatBRL(Number(c.price_cents||0)))}</option>`).join('');
  const itemRows=items.map(item=>`<div class="row amend-item"><div class="field field-wide"><label>Plano</label><select name="catalog_id" required>${planOptions(item.catalog_id)}</select></div><div class="field"><label>Quantidade</label><input type="number" name="quantity" min="1" value="${Number(item.quantity||1)}"></div><div class="field"><label>Valor unitário/mês</label><input type="text" inputmode="decimal" data-money-input name="unit_price" value="${esc(formatBRL(Number(item.unit_price_cents||0)))}"></div></div>`).join('');
  const targetV=new Set((sub.targets||[]).filter(t=>t.vehicle_id).map(t=>t.vehicle_id));
  const targetF=new Set((sub.targets||[]).filter(t=>t.fleet_id).map(t=>t.fleet_id));
  const own=vehicles.filter(v=>v.client_id===sub.client_id), ownF=fleets.filter(f=>f.client_id===sub.client_id);
  const checks=[...ownF.map(f=>`<label class="check-chip"><input type="checkbox" name="target_fleet" value="${esc(f.id)}"${targetF.has(f.id)?' checked':''}> Frota ${esc(f.name)}</label>`),
    ...own.map(v=>`<label class="check-chip"><input type="checkbox" name="target_vehicle" value="${esc(v.id)}"${targetV.has(v.id)?' checked':''}> ${esc(vehicleRef(v))}</label>`)].join('')||'<p class="muted">Cliente sem veículos ou frotas.</p>';
  return `<form id="subscriptionAmendForm"><p class="muted">Vale para as próximas cobranças. Mensalidades já lançadas não mudam.</p>${itemRows}
  <div class="row"><div class="field"><label>Dia de vencimento</label><input type="number" name="due_day" min="1" max="31" value="${Number(sub.due_day||10)}"></div></div>
  <fieldset class="check-group"><legend>Veículos e frotas cobertos</legend>${checks}</fieldset>
  <div class="actions"><button class="ui-btn ui-btn-primary">Salvar ajuste</button></div></form>`;
}
function saleRows(items){return items.map(x=>`<tr data-row-code="${esc(x.code||'')}"><td>${codeTag(x.code)||'—'}</td><td>${esc(x.client_name)}</td><td>${formatDateBR(x.sold_on)}</td><td>${esc(x.status)}</td><td>${formatBRL(x.total_cents)}</td></tr>`).join('')||'<tr><td colspan="5" class="muted">Nenhuma compra.</td></tr>'}
function coverageRows(items){return items.map(x=>`<tr><td>${esc(x.client_name)} ${codeTag(x.subscription_code)}</td><td>${formatDateBR(x.start_on)}</td><td>${formatDateBR(x.end_on)}</td><td>${x.cycles}</td><td>${formatBRL(x.applied_value_cents)}</td><td>${esc(coverageRemaining(x.end_on))}</td></tr>`).join('')||'<tr><td colspan="6" class="muted">Nenhuma cobertura.</td></tr>'}
function creditRows(items){return items.map(x=>`<tr><td>${esc(x.client_name||'—')} ${codeTag(x.client_code)}</td><td>${formatBRL(x.amount_cents)}</td><td>${formatBRL(x.balance_cents)}</td><td>${esc(x.status)}</td></tr>`).join('')||'<tr><td colspan="4" class="muted">Nenhum crédito.</td></tr>'}
export function renderCommercialPage(data={},active='subscriptions'){
 const avulsa=data.catalog_avulsa||[], vehicles=data.vehicles||[], subs=data.subscriptions||[], payments=data.payments||[];
 return `<h2>Comercial</h2><div class="tabs commercial-tabs"><button data-commercial-tab="subscriptions" class="${active==='subscriptions'?'active':''}">Assinaturas</button><button data-commercial-tab="purchases" class="${active==='purchases'?'active':''}">Compras Diretas</button><button data-commercial-tab="credits" class="${active==='credits'?'active':''}">Créditos/Tempo Ativo</button></div>
 <section data-commercial-panel="subscriptions" ${active==='subscriptions'?'':'hidden'}><div class="actions"><button type="button" class="ui-btn ui-btn-primary" data-new-subscription>Nova Assinatura</button></div><div class="panel"><table class="compact-table"><thead><tr><th>Código</th><th>Cliente</th><th>Plano</th><th>Veículos/Frotas</th><th class="num">Valor/mês</th><th>Pago até</th><th>Situação</th><th>Ações</th></tr></thead><tbody>${subRows(subs)}</tbody></table></div></section>
 <section data-commercial-panel="purchases" ${active==='purchases'?'':'hidden'}><div class="panel"><h3>Nova Compra Direta</h3><form id="commercialPurchaseForm"><div class="row">${renderEntityAutocomplete({name:'client_id',label:'Cliente',required:true,selected:data.purchase_client||null})}<div class="field"><label>Produto Avulso</label><select name="catalog_id">${options(avulsa,'id','name')}</select></div><div class="field"><label>Veículo</label><select name="vehicle_id" disabled><option value="">— selecione o cliente —</option>${vehicles.map(row=>`<option value="${esc(row.id)}" data-client="${esc(row.client_id)}" hidden>${esc(vehicleRef(row))}</option>`).join('')}</select></div><div class="field"><label>Quantidade</label><input type="number" min="1" name="quantity" value="1"></div><div class="field"><label>Data contratação</label><input type="date" name="sold_on"></div></div><div class="actions"><button>Registrar compra</button></div></form></div><div class="panel"><table class="compact-table"><thead><tr><th>Código</th><th>Cliente</th><th>Data</th><th>Status</th><th>Total</th></tr></thead><tbody>${saleRows(data.direct_sales||[])}</tbody></table></div></section>
 <section data-commercial-panel="credits" ${active==='credits'?'':'hidden'}><div class="panel"><h3>Registrar Tempo Ativo</h3><form id="coverageForm"><div class="row"><div class="field"><label>Assinatura</label><select name="subscription_id">${options(subs,'id','code')}</select></div><div class="field"><label>Pagamento</label><select name="origin_payment_id">${options(payments,'id','code')}</select></div><div class="field"><label>Ciclos</label><input type="number" min="1" name="cycles" value="1"></div><div class="field"><label>Início</label><input type="date" name="start_on"></div><div class="field"><label>Valor aplicado</label><input type="text" inputmode="decimal" name="value" value="R$ 0,00"></div></div><div class="actions"><button>Registrar cobertura</button></div></form></div><div class="panel"><h3>Tempo Ativo</h3><table class="compact-table"><thead><tr><th>Cliente</th><th>Início</th><th>Fim</th><th>Ciclos</th><th>Valor aplicado</th><th>Restante</th></tr></thead><tbody>${coverageRows(data.coverage_periods||[])}</tbody></table></div><div class="panel"><h3>Créditos monetários</h3><p class="muted">Saldo financeiro permanece separado do tempo de serviço pré-pago.</p><table class="compact-table"><thead><tr><th>Cliente</th><th>Crédito</th><th>Saldo</th><th>Status</th></tr></thead><tbody>${creditRows(data.credits||[])}</tbody></table></div></section>`;
}
