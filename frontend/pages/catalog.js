import { formatBRL, parseBRLInput } from '../ui/formatters.js';
const esc=s=>String(s??'').replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));

// AJ-11 — one cost row; rows can be added and removed freely (create and edit).
export function costRow(component={}){
  return `<div class="row catalog-cost-row"><div class="field"><label>Custo</label><input name="cost_description" value="${esc(component.description||'')}" placeholder="Ex.: Chip, Plataforma, Instalação"></div><div class="field"><label>Valor</label><input name="cost_amount" type="text" inputmode="decimal" data-money-input value="${esc(formatBRL(Number(component.amount_cents||0)))}"></div><button type="button" class="ui-icon-btn catalog-cost-remove" data-cost-remove aria-label="Remover custo" title="Remover custo">×</button></div>`;
}
function productFields(row={}){
  const comps=row.cost_components?.length?row.cost_components:[{description:'',amount_cents:row.cost_cents||0}];
  return `<div class="row"><div class="field field-wide"><label>Descrição*</label><input name="description" required value="${esc(row.description||row.name||'')}"></div>
    <div class="field"><label>Tipo*</label><div class="segmented" role="radiogroup" aria-label="Tipo"><label><input type="radio" name="category" value="MENSAL"${row.category!=='AVULSA'?' checked':''}><span>Plano mensal</span></label><label><input type="radio" name="category" value="AVULSA"${row.category==='AVULSA'?' checked':''}><span>Produto avulso</span></label></div></div>
    <div class="field"><label>Preço</label><input name="price" type="text" inputmode="decimal" data-money-input value="${esc(formatBRL(Number(row.price_cents||0)))}"></div></div>
    <div class="catalog-costs"><h4>Custos</h4><div data-cost-list>${comps.map(costRow).join('')}</div><button type="button" class="ui-btn ui-btn-subtle ui-btn-sm" data-cost-add>+ Adicionar custo</button></div>
    <p class="catalog-margin" data-catalog-margin></p>`;
}
export function renderCatalogPage({items=[]}={}){
  const rows=items.map(row=>{
    const active=Number(row.active??1)===1;
    const margin=Number(row.price_cents||0)-Number(row.cost_cents||0);
    return `<tr class="${active?'':'is-muted'}"><td>${esc(row.code)}</td><td>${esc(row.description||row.name)}${active?'':' <span class="badge badge-muted">Arquivado</span>'}</td><td>${row.category==='MENSAL'?'<span class="badge badge-info">Mensal</span>':'<span class="badge">Avulsa</span>'}</td><td class="num">${formatBRL(row.price_cents)}</td><td class="num">${formatBRL(row.cost_cents)}</td><td class="num ${margin<0?'neg':''}">${formatBRL(margin)}</td><td><div class="row-actions"><button type="button" class="ui-btn ui-btn-subtle ui-btn-sm" data-catalog-edit="${esc(row.id)}">Editar</button>${active?`<button type="button" class="ui-btn ui-btn-danger ui-btn-sm" data-catalog-delete="${esc(row.id)}" data-used="${Number(row.usage_count||0)}">${Number(row.usage_count||0)?'Arquivar':'Excluir'}</button>`:`<button type="button" class="ui-btn ui-btn-subtle ui-btn-sm" data-catalog-restore="${esc(row.id)}">Reativar</button>`}</div></td></tr>`;
  }).join('');
  return `<h2>Planos/Produtos</h2>
  <div class="panel"><details class="more-options" ${items.length?'':'open'}><summary class="ui-btn ui-btn-primary">+ Novo plano ou produto</summary><form id="catalogForm" class="catalog-form">${productFields()}<div class="actions"><button class="ui-btn ui-btn-primary">Salvar</button></div></form></details></div>
  <div class="panel"><div class="table-wrap"><table class="compact-table"><thead><tr><th>Código</th><th>Descrição</th><th>Tipo</th><th class="num">Preço</th><th class="num">Custo</th><th class="num">Margem</th><th>Ações</th></tr></thead><tbody>${rows||'<tr><td colspan="7" class="muted">Nenhum produto cadastrado.</td></tr>'}</tbody></table></div></div>`;
}
export function catalogPayload(form){
  const fd=new FormData(form);
  const descriptions=fd.getAll('cost_description'), amounts=fd.getAll('cost_amount');
  const cost_components=amounts.map((amount,i)=>({description:String(descriptions[i]||'').trim(),amount:String(amount||'').trim()||'R$ 0,00'}))
    .filter((c,_,all)=>all.length===1||c.description||c.amount!=='R$ 0,00');
  return {description:fd.get('description'),category:fd.get('category'),price:fd.get('price'),cost_components};
}
export function renderCatalogEditForm(row){
  return `<form id="catalogEditForm" class="catalog-form">${productFields(row)}<div class="actions"><button class="ui-btn ui-btn-primary">Salvar alterações</button></div></form>`;
}
/** Add/remove cost rows and live margin; pure DOM. */
export function bindCatalogForm(form,{bindMoney=()=>{}}={}){
  if(!form)return;
  const list=form.querySelector('[data-cost-list]');
  const margin=()=>{
    const cents=v=>{try{return parseBRLInput(v||'0')}catch{return 0}};
    const cost=[...form.querySelectorAll('[name=cost_amount]')].reduce((a,i)=>a+cents(i.value),0);
    const price=cents(form.querySelector('[name=price]')?.value);
    const out=form.querySelector('[data-catalog-margin]');
    if(out)out.innerHTML=`Custo total <b>${esc(formatBRL(cost))}</b> · Margem <b class="${price-cost<0?'neg':''}">${esc(formatBRL(price-cost))}</b>`;
  };
  const bindRemove=()=>list.querySelectorAll('[data-cost-remove]').forEach(button=>button.onclick=()=>{
    if(list.querySelectorAll('.catalog-cost-row').length===1){list.querySelector('[name=cost_description]').value='';list.querySelector('[name=cost_amount]').value='R$ 0,00'}else button.closest('.catalog-cost-row').remove();
    margin();
  });
  form.querySelector('[data-cost-add]').onclick=()=>{list.insertAdjacentHTML('beforeend',costRow());bindMoney(list);bindRemove();list.lastElementChild.querySelector('input')?.focus()};
  form.addEventListener('input',margin);form.addEventListener('focusout',margin);
  bindRemove();bindMoney(form);margin();
}
