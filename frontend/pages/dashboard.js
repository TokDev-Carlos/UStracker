import { formatBRL } from '../ui/formatters.js';
import { codeTag } from '../ui/logical-codes.js';
import { renderVehicleBreakdown } from '../ui/vehicle-breakdown.js';
const esc=s=>String(s??'').replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
const monthLabel=competence=>{const [y,m]=String(competence||'').split('-');const names=['jan','fev','mar','abr','mai','jun','jul','ago','set','out','nov','dez'];return m?`${names[Number(m)-1]||m}/${y}`:''};
export function renderOverviewPage(data={},query='',selectedYear=''){
 const rows=(data.client_activity||[]).map(r=>`<tr><td>${esc(r.client_name)} ${codeTag(r.client_code)}</td><td>${r.vehicles_count}</td><td>${r.active_subscriptions}</td><td>${r.purchases_count}</td><td class="money">${formatBRL(r.contracted_active_cents||0)}${Number(r.open_purchases_cents||0)?`<span class="forecast-detail">+ ${formatBRL(r.open_purchases_cents)} em compras abertas</span>`:''}</td><td class="money">${formatBRL(r.realized_revenue_cents??r.value_generated_cents??0)}</td><td>${esc(r.status)}</td><td><button type="button" class="ui-btn ui-btn-subtle" data-profile-id="${esc(r.client_id)}">Abrir Ficha</button></td></tr>`).join('')||'<tr><td colspan="8" class="muted">Nenhum cliente encontrado.</td></tr>';
 const period=data.period||{};const years=data.available_years||[];const forecast=data.month_forecast||{};
 // P-01 — two rows of three: Receita | Previsão do Mês | Clientes Ativos / Despesas Gerais | Resultado | Assinaturas Ativas
 const kpi=(cls,value,label,extra='')=>`<div class="card kpi ${cls}"><div class="value">${value}</div><div class="label">${label}</div>${extra}</div>`;
 const kpis=[
  kpi('kpi-revenue',formatBRL(period.revenue_cents||0),'Receita',`<span class="forecast-detail">Realizada até hoje · ${esc(period.label||'Geral')}</span>`),
  kpi('kpi-forecast',formatBRL(forecast.forecast_cents||0),`Previsão do Mês ${esc(monthLabel(forecast.competence))}`,`<span class="forecast-tag">Não realizada · fora do Resultado</span><span class="forecast-detail">Recebido no mês: ${formatBRL(forecast.received_in_month_cents||0)}</span>`),
  kpi('kpi-clients',esc(data.active_clients??0),'Clientes Ativos'),
  kpi('kpi-expenses',formatBRL(period.expenses_cents||0),'Despesas Gerais',`<span class="forecast-detail">Pagas · ${esc(period.label||'Geral')}</span>`),
  kpi(`kpi-result ${Number(period.result_cents||0)>=0?'result-positive':'result-negative'}`,formatBRL(period.result_cents||0),'Resultado','<span class="forecast-detail">Receita − Despesas Gerais</span>'),
  kpi('kpi-subscriptions',esc(data.active_subscriptions??0),'Assinaturas Ativas'),
 ].join('');
 return `<h2>Visão Geral</h2><div class="panel r2-operational"><div class="indicators-head"><h3>Indicadores ${esc(period.label||'Gerais')}</h3><form id="overviewPeriod"><div class="field"><label>Período</label><select name="year"><option value="">Geral</option>${years.map(year=>`<option value="${year}" ${String(selectedYear)===String(year)?'selected':''}>${year}</option>`).join('')}</select></div></form><button type="button" class="ui-btn ui-btn-secondary" data-overview-drilldown>Ver detalhamento</button></div><div class="cards overview-kpis">${kpis}</div>
 <div class="overview-vehicles">${renderVehicleBreakdown(data.vehicle_breakdown||{total:data.active_vehicles||0,categories:[]})}</div></div>
 <div class="panel"><form id="overviewSearch" class="overview-search"><div class="field"><label>Pesquisar clientes</label><input name="q" value="${esc(query)}" placeholder="Nome do cliente"></div><div class="actions"><button>Pesquisar</button><button type="button" class="secondary" id="overviewClear">Limpar</button></div></form></div>
 <div class="panel"><h3>Clientes</h3><div class="overview-table-wrap"><table id="overviewClients" class="compact-table overview-table"><thead><tr><th>Cliente</th><th>Veículos</th><th>Assinaturas</th><th>Compras</th><th>Valor contratado ativo</th><th>Receita realizada</th><th>Status</th><th>Ação</th></tr></thead><tbody>${rows}</tbody></table></div></div>`;
}

const MONTHS=['jan','fev','mar','abr','mai','jun','jul','ago','set','out','nov','dez'];
const periodName=key=>/^\d{4}-\d{2}$/.test(key)?`${MONTHS[Number(key.slice(5))-1]}/${key.slice(0,4)}`:key;
/** R18 — components behind Receita Geral, Despesas Gerais and Resultado (same rules as the cards). */
export function renderOverviewDrilldown(d={}){
 const t=d.totals||{};
 const rows=(d.periods||[]).map(r=>`<tr><td>${esc(periodName(r.period))}</td><td class="money">${formatBRL(r.subscriptions_cents)}</td><td class="money">${formatBRL(r.direct_sales_cents)}</td><td class="money"><strong>${formatBRL(r.revenue_cents)}</strong></td><td class="money">${formatBRL(r.expenses_cents)}</td><td class="money ${r.result_cents>=0?'':'negative'}"><strong>${formatBRL(r.result_cents)}</strong></td></tr>`).join('')||'<tr><td colspan="6" class="muted">Nenhum valor realizado neste período.</td></tr>';
 const cats=(d.expense_categories||[]).map(c=>`<tr><td>${esc(c.category)}</td><td class="money">${formatBRL(c.amount_cents)}</td></tr>`).join('')||'<tr><td colspan="2" class="muted">Nenhuma despesa paga.</td></tr>';
 return `<div class="drilldown"><div class="cards drilldown-cards"><div class="card"><div class="value">${formatBRL(t.revenue_cents||0)}</div><div class="label">Receita Geral</div><span class="forecast-detail">Assinaturas/recebimentos ${formatBRL(t.subscriptions_cents||0)} · Compras pagas ${formatBRL(t.direct_sales_cents||0)}</span></div><div class="card"><div class="value">${formatBRL(t.expenses_cents||0)}</div><div class="label">Despesas Gerais</div></div><div class="card"><div class="value">${formatBRL(t.result_cents||0)}</div><div class="label">Resultado</div></div></div>
 <h4>Por ${d.granularity==='month'?'mês':'ano'}</h4><div class="table-wrap"><table class="compact-table"><thead><tr><th>Período</th><th class="money">Recebimentos</th><th class="money">Compras pagas</th><th class="money">Receita</th><th class="money">Despesas</th><th class="money">Resultado</th></tr></thead><tbody>${rows}</tbody></table></div>
 <h4>Despesas por categoria</h4><div class="table-wrap"><table class="compact-table"><thead><tr><th>Categoria</th><th class="money">Valor pago</th></tr></thead><tbody>${cats}</tbody></table></div>
 <p class="muted">Recebimentos estornados no período (fora da receita): ${formatBRL(d.reversed_payments_cents||0)}. Valores com data futura não entram.</p></div>`;
}
