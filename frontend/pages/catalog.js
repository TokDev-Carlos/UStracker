import { formatBRL } from '../ui/formatters.js';
const esc=s=>String(s??'').replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
export function renderCatalogPage({items=[]}={}){
  const rows=items.map(row=>`<tr><td>${esc(row.code)}</td><td>${esc(row.description||row.name)}</td><td>${row.category==='MENSAL'?'Mensal':'Avulsa'}</td><td>${formatBRL(row.price_cents)}</td><td>${formatBRL(row.cost_cents)}</td><td><button type="button" class="ui-btn ui-btn-subtle" data-catalog-edit="${esc(row.id)}">Editar</button></td></tr>`).join('');
  return `<h2>Planos/Produtos</h2>
  <div class="panel"><h3>Novo produto</h3><form id="catalogForm">
    <div class="row"><div class="field"><label>Descrição*</label><input name="description" required></div>
    <div class="field"><label>Categoria*</label><select name="category"><option value="AVULSA">Avulsa</option><option value="MENSAL">Mensal</option></select></div>
    <div class="field"><label>Preço</label><input name="price" type="text" inputmode="decimal" value="R$ 0,00"></div></div>
    <div class="catalog-costs"><h4>Componentes de custo</h4><div class="row catalog-cost-row"><div class="field"><label>Componente de custo</label><input name="cost_description_0"></div><div class="field"><label>Valor</label><input name="cost_amount_0" type="text" inputmode="decimal" value="R$ 0,00"></div></div></div>
    <div class="actions"><button type="button" class="secondary" id="catalogAddCost">Adicionar custo</button><button>Salvar</button></div></form></div>
  <div class="panel"><table class="compact-table"><thead><tr><th>Código</th><th>Descrição</th><th>Categoria</th><th>Preço</th><th>Custo</th><th>Ação</th></tr></thead><tbody>${rows||'<tr><td colspan="6" class="muted">Nenhum produto cadastrado.</td></tr>'}</tbody></table></div>`;
}
export function catalogPayload(form){
  const fd=new FormData(form); const payload={description:fd.get('description'),category:fd.get('category'),price:fd.get('price'),cost_components:[]};
  for(let i=0;;i++){const amount=fd.get(`cost_amount_${i}`); if(amount===null)break; payload.cost_components.push({description:fd.get(`cost_description_${i}`)||'',amount});}
  return payload;
}

export function renderCatalogEditForm(row){
  const comps=(row.cost_components?.length?row.cost_components:[{description:'',amount_cents:row.cost_cents||0}]);
  return `<form id="catalogEditForm"><div class="row"><div class="field"><label>Descrição*</label><input name="description" required value="${esc(row.description||row.name)}"></div><div class="field"><label>Categoria*</label><select name="category"><option value="AVULSA" ${row.category==='AVULSA'?'selected':''}>Avulsa</option><option value="MENSAL" ${row.category==='MENSAL'?'selected':''}>Mensal</option></select></div><div class="field"><label>Preço</label><input name="price" type="text" inputmode="decimal" value="${formatBRL(row.price_cents)}"></div></div><div class="catalog-costs">${comps.map((c,i)=>`<div class="row catalog-cost-row"><div class="field"><label>Componente de custo</label><input name="cost_description_${i}" value="${esc(c.description||'')}"></div><div class="field"><label>Valor</label><input name="cost_amount_${i}" type="text" inputmode="decimal" value="${formatBRL(c.amount_cents)}"></div></div>`).join('')}</div><div class="actions"><button>Salvar alterações</button></div></form>`;
}
