import { createApi } from './ui/api.js';
import { createSession } from './ui/session.js';
import { pageHeader, renderAppShell } from './ui/shell.js';
import { createTableController, mountTableController } from './ui/table-controller.js';
import { closeOverlay, openDrawer, toast } from './ui/overlay.js';
import { HELP, helpFor } from './ui/help-catalog.js';
import { loadIconSet } from './ui/icon-registry.js';
import { renderPurchasesForm, renderDashboardCards, formatSubscriptionRates, renderClientProfile, renderLoginScreen } from './ui/r2-ui.js';
import { labelPtBR, localizeDom, messagePtBR, observePtBR, valuePtBR } from './ui/pt-br.js';
import { formatBRL, formatDateBR } from './ui/formatters.js';
import { bindMoneyInputs, renderMoneyInput } from './ui/money-input.js';
import { bindSubscriptionWorkflow, renderSubscriptionWorkflow } from './ui/subscription-workflow.js';
import { bindEntityAutocomplete } from './ui/entity-autocomplete.js';
import { buildClientCreatePayload, clientTableDefinition, renderClientEditor } from './pages/clients.js';
import { buildMobilityQuery, buildVehiclePayload, renderFleetProfile, renderMobilityPage, renderTransferCaseForm } from './pages/mobility.js';
import { catalogPayload, renderCatalogEditForm, renderCatalogPage } from './pages/catalog.js';
import { renderCommercialPage } from './pages/commercial.js';
import { renderFinancePage } from './pages/finance.js';
import { renderOverviewPage } from './pages/dashboard.js';
import { renderFilesPage } from './pages/files.js';

const app=document.querySelector('#app');
let csrf=''; let me=null; let current='dashboard';
const apiClient=createApi({csrfState:{get:()=>csrf,set:value=>{csrf=value}}});
const session=createSession({api:apiClient,onUserChange:user=>{me=user}});
const api=(path,opt)=>path==='/auth/logout'?session.logout():apiClient.request(path,opt).then(result=>{if(path==='/auth/login')session.authenticate(result);return result});
const getCsrf=()=>apiClient.acquireCsrf();
const apiForm=(path,form,method='POST')=>apiClient.requestForm(path,form,method);
const searchClientEntities=async(query,limit=30)=>(await api('/entities/clients?q='+encodeURIComponent(query)+'&limit='+Math.min(Number(limit)||30,30))).items||[];
const tableStore=new Map();
const esc=s=>String(s??'').replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
const sessionProfileLabel=user=>user?.role||(user?.slot?'Administrador':'Usuário');
async function requestSystemShutdown(){const bridge=window.chrome?.webview;if(bridge){bridge.postMessage('system-shutdown');return}await api('/system/shutdown',{method:'POST',body:'{}'});alert('Sistema encerrado com segurança.')}
function formData(form){const o={};for(const [k,v] of new FormData(form).entries())o[k]=v;return o}
function msg(text,type='success'){return `<div class="${type}">${esc(text)}</div>`}
function content(html){const normalized=html.replace(/^<h2>([^<]+)<\/h2>/,(_,title)=>pageHeader(title,'Gestão administrativa')).replaceAll('>Publicar<','>Exibir no catálogo público<');const target=document.querySelector('#content');target.innerHTML=normalized;hydrateTables();bindMoneyInputs(target);localizeDom(target)}
function applyBrand(p){const b=p?.brand||{};if(b.theme_primary)document.documentElement.style.setProperty('--primary',b.theme_primary);if(b.theme_accent)document.documentElement.style.setProperty('--accent',b.theme_accent);document.title=(b.company_display_name||'UStracker')+' — UStracker';const fav=b.assets?.favicon;if(fav){let l=document.querySelector('#dynamicFavicon');if(!l){l=document.createElement('link');l.id='dynamicFavicon';l.rel='icon';document.head.appendChild(l)}l.href=fav+'?v='+Date.now()}}
function dt(items,id){const rows=items||[];const keys=rows.length?Object.keys(rows[0]).filter(k=>!['notes','address','before_json','after_json'].includes(k)).slice(0,12):[];const isDateKey=key=>key.endsWith('_on')||key.endsWith('_at')||['created_at','updated_at','paid_on','due_on','start_on','end_on','sold_on','installed_on'].includes(key);const columns=keys.map(key=>({key,label:labelPtBR(key),format:key.endsWith('_cents')?value=>formatBRL(Number(value||0)):isDateKey(key)?value=>esc(formatDateBR(value,key.endsWith('_at'))):value=>esc(valuePtBR(value))}));tableStore.set(id,createTableController({columns,rows}));return `<div id="${id}" class="data-table"></div>`}
function hydrateTables(){for(const id of tableStore.keys()){if(document.querySelector('#'+CSS.escape(id)))renderDT(id)}}
function renderDT(id){const box=document.querySelector('#'+CSS.escape(id));const controller=tableStore.get(id);if(box&&controller)mountTableController(box,controller)}
function select(items,value='id',label='legal_name',blank=false){return `${blank?'<option value="">—</option>':''}${(items||[]).map(x=>`<option value="${esc(x[value])}">${esc(x[label]??x[value])}</option>`).join('')}`}
function field(label,name,type='text',value=''){const credentialLabels={password:'Senha ou PIN (mínimo 4 caracteres)',current_password:'Senha ou PIN atual',new_password:'Nova senha ou PIN (mínimo 4 caracteres)'};const displayLabel=type==='password'&&credentialLabels[name]?credentialLabels[name]:label;const hint=HELP[current]?.fields?.[name];return `<div class="field"><label>${displayLabel}${hint?` <button type="button" class="ui-help-trigger" title="${esc(hint)}" aria-label="Ajuda sobre ${esc(displayLabel)}">?</button>`:''}</label><input name="${name}" type="${type}" value="${esc(value)}" autocomplete="${name==='password'?'current-password':'off'}">${hint?`<span class="ui-field-hint">${esc(hint)}</span>`:''}</div>`}
function moneyField(label,name,valueCents=null,required=false){return renderMoneyInput({label,name,valueCents,required})}
function openSubscriptionWorkflow(model,{onSuccess,onCancel}={}){
  const drawer=openDrawer({title:'Nova Assinatura',subtitle:'Plano mensal e alvos de mobilidade',content:renderSubscriptionWorkflow(model)});
  if(onCancel)drawer.querySelectorAll('[data-close-overlay]').forEach(button=>button.onclick=async()=>{closeOverlay();await onCancel()});
  bindSubscriptionWorkflow(drawer,{model,searchClients:searchClientEntities,onSubmit:async payload=>{
    await api('/subscriptions',{method:'POST',body:JSON.stringify(payload)});
    closeOverlay();toast({message:'Assinatura criada.'});await onSuccess?.();
  },onError:error=>toast({type:'error',message:error.message})});
  return drawer;
}
async function boot(){const state=await session.bootstrap();const pub=state.publicData,st=state.setupStatus;applyBrand(pub);if(state.state==='setup')return setupScreen();if(state.state==='login')return loginScreen(st,pub);renderShell();await show('dashboard')}
function setupScreen(){app.innerHTML=`<section class="auth"><h1>UStracker — Configuração inicial</h1><p>Crie o Administrador 1. Serão emitidos dois tickets de uso único para os Administradores 2 e 3.</p><form id="setup"><div class="row">${field('Nome','name')}${field('Senha (10+ caracteres)','password','password')}</div><div class="actions"><button>Iniciar configuração</button></div></form><div id="setupOut"></div></section>`;document.querySelector('#setup').onsubmit=async e=>{e.preventDefault();try{await getCsrf();const r=await api('/auth/bootstrap',{method:'POST',body:JSON.stringify(formData(e.target))});enrollmentScreen(r.tickets)}catch(err){document.querySelector('#setupOut').innerHTML=msg(err.message,'error')}}}
function enrollmentScreen(tickets){app.innerHTML=`<section class="auth"><h1>Concluir três administradores</h1><div class="notice">Os tickets expiram em 15 minutos.</div>${tickets.map((t,i)=>`<form class="enroll" data-ticket="${esc(t)}"><h3>Administrador ${i+2}</h3><div class="ticket">${esc(t)}</div><div class="row">${field('Nome','name')}${field('Senha','password','password')}</div><div class="actions"><button>Registrar Admin ${i+2}</button></div><div class="out"></div></form>`).join('')}<button id="goLogin" class="secondary">Ir para login</button></section>`;document.querySelectorAll('.enroll').forEach(f=>f.onsubmit=async e=>{e.preventDefault();try{await getCsrf();const p=formData(f);p.ticket=f.dataset.ticket;await api('/auth/enroll',{method:'POST',body:JSON.stringify(p)});f.querySelector('.out').innerHTML=msg('Administrador registrado.')}catch(err){f.querySelector('.out').innerHTML=msg(err.message,'error')}});document.querySelector('#goLogin').onclick=()=>boot()}
function publicCard(p){const b=p.brand||{};return `<div class="public-card">${b.assets?.logo?`<img src="${esc(b.assets.logo)}" class="public-logo">`:''}<h2>${esc(b.company_display_name||'UStracker')}</h2><p>${esc(b.contact_phone||'')} ${esc(b.contact_email||'')}</p><h3>Planos e serviços</h3>${p.catalog?.length?`<div class="public-grid">${p.catalog.map(x=>`<div class="card"><strong>${esc(x.name)}</strong><div>${esc(x.category)}</div><div class="value">${formatBRL(x.price_cents)}</div></div>`).join('')}</div>`:'<p class="muted">Nenhum item público.</p>'}</div>`}
function loginScreen(st,pub){app.innerHTML=renderLoginScreen(st,pub);document.querySelector('#login').onsubmit=async e=>{e.preventDefault();try{await getCsrf();const r=await api('/auth/login',{method:'POST',body:JSON.stringify(formData(e.target))});csrf=r.csrf;me=r;renderShell();await show('dashboard');if(r.backup_warning)alert('Backup automático: '+r.backup_warning)}catch(err){document.querySelector('#loginOut').innerHTML=msg(err.message,'error')}}}
const nav=[['dashboard','Visão geral'],['clients','Clientes'],['mobility','Frotas/Veículos'],['catalog','Planos/Produtos'],['commercial','Comercial'],['finance','Financeiro'],['files','Fotos/Arquivos'],['reports','Relatórios'],['system','Sistema']];
function renderShell(){renderAppShell({me,nav,onNavigate:show,onSearch:async query=>{const d=await api('/search?q='+encodeURIComponent(query));tableStore.clear();content(pageHeader('Pesquisa','Resultados da busca global')+dt(d.items,'searchTable'))},onHelp:()=>{const help=helpFor(current);openDrawer({title:help.title,subtitle:'Ajuda contextual',content:`<p>${esc(help.body)}</p>${HELP[current]?.fields?`<dl>${Object.entries(HELP[current].fields).map(([key,value])=>`<dt><strong>${esc(key.replaceAll('_',' '))}</strong></dt><dd>${esc(value)}</dd>`).join('')}</dl>`:''}`})},onUser:()=>content(pageHeader('Usuário','Sessão atual')+`<div class="panel"><strong>${esc(me.name)}</strong><p class="muted">Perfil: ${esc(sessionProfileLabel(me))}</p><p class="muted">Ambiente: ${esc(me.environment)}</p></div>`),onLogout:async()=>{await session.logout();await boot()},onShutdown:requestSystemShutdown})}
async function openClientProfile(clientId){
  const profile=await api('/clients/'+encodeURIComponent(clientId)+'/profile');
  const drawer=openDrawer({title:'Ficha do Cliente',subtitle:profile.client?.legal_name||'',content:renderClientProfile(profile)});
  drawer.querySelector('.ui-drawer').classList.add('r2-profile-wide');
  const refresh=async()=>{closeOverlay();await openClientProfile(clientId)};
  const basics=drawer.querySelector('#clientBasicsForm');
  if(basics)basics.onsubmit=async event=>{event.preventDefault();const payload=formData(event.target);payload.expected_revision=profile.client.revision;await api('/clients/'+encodeURIComponent(clientId),{method:'PATCH',body:JSON.stringify(payload)});toast({message:'Dados do cliente atualizados.'});await refresh()};
  const companyForm=drawer.querySelector('#clientCompanyForm');
  if(companyForm)companyForm.onsubmit=async event=>{event.preventDefault();const payload=formData(event.target);payload.is_primary=payload.is_primary==='true';await api('/clients/'+encodeURIComponent(clientId)+'/companies',{method:'POST',body:JSON.stringify(payload)});toast({message:'Empresa adicionada.'});await refresh()};
  const photoForm=drawer.querySelector('#clientPhotoForm');
  if(photoForm)photoForm.onsubmit=async event=>{event.preventDefault();const input=event.target.querySelector('[name=file]');if(!input.files?.[0])return;const body=new FormData();body.append('file',input.files[0]);await apiForm('/media/client/'+encodeURIComponent(clientId),body);toast({message:'Foto do cliente atualizada.'});await refresh()};
  const signatureForm=drawer.querySelector('#clientSignatureForm');
  if(signatureForm)signatureForm.onsubmit=async event=>{event.preventDefault();const input=event.target.querySelector('[name=file]');const subscriptionId=event.target.querySelector('[name=subscription_id]')?.value;if(!subscriptionId||!input.files?.[0])return;const body=new FormData();body.append('file',input.files[0]);await apiForm('/attachments/subscription/'+encodeURIComponent(subscriptionId),body);toast({message:'Assinatura anexada.'});await refresh()};
  const newSubscription=drawer.querySelector('[data-client-new-subscription]');
  if(newSubscription)newSubscription.onclick=async()=>{const catalog=await api('/catalog');openSubscriptionWorkflow({context:'CLIENT_PROFILE',clientId,clients:[profile.client],catalog:catalog.items||[],vehicles:profile.vehicles||[],fleets:profile.fleets||[]},{onSuccess:()=>openClientProfile(clientId),onCancel:()=>openClientProfile(clientId)})};
  return drawer;
}
async function show(page){if(page==='fleets'||page==='vehicles')page='mobility';current=page;tableStore.clear();document.querySelectorAll('[data-page]').forEach(b=>b.classList.toggle('active',b.dataset.page===page));try{const fn={dashboard:dashboardPage,clients:clientsPage,mobility:mobilityPage,catalog:catalogPage,commercial:commercialPage,subscriptions:commercialPage,purchases:commercialPage,charges:commercialPage,credits:commercialPage,finance:financePage,payments:financePage,expenses:financePage,fiscal:financePage,files:filesPage,media:filesPage,reports:reportsPage,system:systemPage}[page];if(fn)await fn()}catch(e){content(`<div class="error">${esc(e.message)}</div>`)}}
async function dashboardPage(query=''){
  const d=await api('/dashboard'+(query?'?q='+encodeURIComponent(query):''));
  content(renderOverviewPage(d,query));
  const form=document.querySelector('#overviewSearch');if(form)form.onsubmit=async event=>{event.preventDefault();await dashboardPage(formData(form).q||'')};
  const clear=document.querySelector('#overviewClear');if(clear)clear.onclick=()=>dashboardPage('');
  document.querySelectorAll('[data-profile-id]').forEach(button=>button.onclick=()=>openClientProfile(button.dataset.profileId).catch(error=>toast({type:'error',message:error.message})));
}
async function clientsPage(){
  const d=await api('/clients');
  content(pageHeader('Clientes','Cadastros e relacionamento','<button type="button" id="archiveClients" class="ui-btn ui-btn-danger" disabled>Excluir selecionados</button><button type="button" id="newClient" class="ui-btn ui-btn-primary">Novo cliente</button>')+'<div id="clientsCentralTable"></div>');
  const newButton=document.querySelector('#newClient');
  const archiveButton=document.querySelector('#archiveClients');
  newButton.onclick=()=>{
    const drawer=openDrawer({title:'Novo cliente',subtitle:'Cadastre documento e ao menos um contato.',content:renderClientEditor(),actions:'<button type="button" class="ui-btn ui-btn-secondary" data-close-overlay>Cancelar</button><button type="submit" form="clientDrawerForm" class="ui-btn ui-btn-primary">Salvar</button>'});
    drawer.querySelectorAll('[data-close-overlay]').forEach(button=>button.onclick=()=>closeOverlay());
    drawer.querySelector('#clientDrawerForm').onsubmit=async event=>{event.preventDefault();const flat=formData(event.target);if(!flat.email?.trim()&&!flat.phone?.trim())return toast({type:'error',message:'Informe ao menos e-mail ou telefone.'});const payload=buildClientCreatePayload(flat);await api('/clients',{method:'POST',body:JSON.stringify(payload)});closeOverlay();toast({message:'Cliente cadastrado.'});await show('clients')};
  };
  const definition=clientTableDefinition(row=>openClientProfile(row.id).catch(error=>toast({type:'error',message:error.message})));
  const controller=createTableController({...definition,rows:d.items});
  const updateSelection=ids=>{archiveButton.disabled=!ids.length;archiveButton.textContent=ids.length?`Excluir selecionados (${ids.length})`:'Excluir selecionados'};
  mountTableController(document.querySelector('#clientsCentralTable'),controller,{onSelectionChange:updateSelection});
  archiveButton.onclick=async()=>{const ids=controller.view().selectedIds;if(!ids.length)return;if(!confirm(`Arquivar ${ids.length} cliente(s) selecionado(s)?`))return;const result=await api('/clients/archive',{method:'POST',body:JSON.stringify({client_ids:ids})});const blocked=(result.blocked||[]).map(item=>{const row=d.items.find(client=>client.id===item.id);return `${row?.legal_name||item.id}: ${(item.reasons||[]).join(', ')}`});const message=`${result.archived_ids?.length||0} cliente(s) arquivado(s).${blocked.length?' Bloqueados: '+blocked.join(' | '):''}`;toast({type:blocked.length?'error':'success',message});await show('clients')};
}
async function mobilityPage(filters={}){
  const [clients,fleets,data]=await Promise.all([
    api('/clients'),
    api('/fleets'),
    api('/mobility'+buildMobilityQuery(filters))
  ]);
  const activeClients=(clients.items||[]).filter(row=>!row.archived);
  const activeFleets=(fleets.items||[]).filter(row=>!row.archived);
  content(renderMobilityPage(data,{clients:activeClients,fleets:activeFleets,filters}));

  const filterForm=document.querySelector('#mobilityFilter');
  filterForm.onsubmit=async event=>{event.preventDefault();await mobilityPage(formData(event.target))};
  document.querySelector('#mobilityClear').onclick=()=>mobilityPage({});
  document.querySelectorAll('[data-mobility-tab]').forEach(button=>button.onclick=()=>{
    document.querySelectorAll('[data-mobility-tab]').forEach(item=>item.classList.toggle('active',item===button));
    document.querySelectorAll('[data-mobility-panel]').forEach(panel=>panel.hidden=panel.dataset.mobilityPanel!==button.dataset.mobilityTab);
  });

  const fleetsForClient=clientId=>activeFleets.filter(row=>row.client_id===clientId&&row.client_company_id);
  const setFleetOptions=(selectEl,clientId,selected='')=>{
    const rows=fleetsForClient(clientId);
    selectEl.innerHTML='<option value="">—</option>'+rows.map(row=>`<option value="${esc(row.id)}" ${row.id===selected?'selected':''}>${esc(row.name)}</option>`).join('');
  };

  const openVehicleDrawer=async(prefill={})=>{
    const template=document.querySelector('#vehicleFormTemplate');
    const drawer=openDrawer({title:'Novo veículo',subtitle:prefill.fleet_id?'Adicionar à frota':'Veículo particular ou de frota',content:template.innerHTML,actions:'<button type="button" class="ui-btn ui-btn-secondary" data-close-overlay>Cancelar</button><button type="submit" form="vehicleForm" class="ui-btn ui-btn-primary">Salvar</button>'});
    drawer.querySelectorAll('[data-close-overlay]').forEach(button=>button.onclick=()=>closeOverlay());
    const form=drawer.querySelector('#vehicleForm');
    const clientSelect=form.querySelector('[name=client_id]');
    const fleetSelect=form.querySelector('[name=fleet_id]');
    if(prefill.client_id)clientSelect.value=prefill.client_id;
    setFleetOptions(fleetSelect,clientSelect.value,prefill.fleet_id||'');
    clientSelect.onchange=()=>setFleetOptions(fleetSelect,clientSelect.value,'');
    const typeSelect=form.querySelector('[name=type]');
    const customField=form.querySelector('.custom-type-field');
    typeSelect.onchange=()=>{customField.hidden=typeSelect.value!=='__custom__';customField.querySelector('input').required=!customField.hidden};
    form.onsubmit=async event=>{event.preventDefault();const payload=buildVehiclePayload(formData(form));await api('/vehicles',{method:'POST',body:JSON.stringify(payload)});closeOverlay();toast({message:'Veículo cadastrado.'});await mobilityPage(filters)};
  };

  const loadCompanies=async(clientId,companySelect,submitButton,selected='')=>{
    if(!clientId){companySelect.innerHTML='<option value="">Selecione o cliente primeiro</option>';companySelect.disabled=true;submitButton.disabled=true;return []}
    const result=await api('/clients/'+encodeURIComponent(clientId)+'/companies');
    const companies=result.items||[];
    companySelect.innerHTML=companies.length?companies.map(company=>`<option value="${esc(company.id)}" ${company.id===selected?'selected':''}>${esc(company.legal_name)}</option>`).join(''):'<option value="">Cadastre uma empresa na ficha do cliente</option>';
    companySelect.disabled=!companies.length;submitButton.disabled=!companies.length;
    return companies;
  };

  const openFleetDrawer=()=>{
    const template=document.querySelector('#fleetFormTemplate');
    const drawer=openDrawer({title:'Nova frota',subtitle:'A frota precisa estar vinculada a uma empresa do cliente.',content:template.innerHTML,actions:'<button type="button" class="ui-btn ui-btn-secondary" data-close-overlay>Cancelar</button><button type="submit" form="fleetForm" class="ui-btn ui-btn-primary">Salvar</button>'});
    drawer.querySelectorAll('[data-close-overlay]').forEach(button=>button.onclick=()=>closeOverlay());
    const form=drawer.querySelector('#fleetForm');
    const clientSelect=form.querySelector('[name=client_id]');
    const companySelect=form.querySelector('[name=client_company_id]');
    const submitButton=drawer.querySelector('[form=fleetForm]');
    const sync=()=>loadCompanies(clientSelect.value,companySelect,submitButton).catch(error=>toast({type:'error',message:error.message}));
    clientSelect.onchange=sync;sync();
    form.onsubmit=async event=>{event.preventDefault();await api('/fleets',{method:'POST',body:JSON.stringify(formData(form))});closeOverlay();toast({message:'Frota cadastrada.'});await mobilityPage(filters)};
  };

  const openTransfer=async vehicle=>{
    const cases=await api(`/vehicles/${encodeURIComponent(vehicle.id)}/transfer-cases`);
    const drawer=openDrawer({title:'Transferência de propriedade',subtitle:vehicle.plate||vehicle.id,content:renderTransferCaseForm(vehicle,{clients:activeClients,fleets:activeFleets,cases:cases.items||[]})});
    const form=drawer.querySelector('#transferCaseForm');
    if(form){
      const clientSelect=form.querySelector('[name=client_id]');
      const fleetSelect=form.querySelector('[name=fleet_id]');
      const sync=()=>setFleetOptions(fleetSelect,clientSelect.value,'');
      clientSelect.onchange=sync;sync();
      form.onsubmit=async event=>{event.preventDefault();const payload=formData(form);payload.expected_revision=Number(payload.expected_revision);if(!payload.fleet_id)delete payload.fleet_id;if(!payload.effective_from)delete payload.effective_from;await api(`/vehicles/${vehicle.id}/transfer-cases`,{method:'POST',body:JSON.stringify(payload)});closeOverlay();toast({message:'Transferência criada como pendente.'});await mobilityPage(filters)};
    }
    const complete=drawer.querySelector('[data-complete-transfer]');
    if(complete)complete.onclick=async()=>{await api(`/vehicle-transfer-cases/${complete.dataset.completeTransfer}/complete`,{method:'POST',body:'{}'});closeOverlay();toast({message:'Transferência concluída.'});await mobilityPage(filters)};
    const cancel=drawer.querySelector('[data-cancel-transfer]');
    if(cancel)cancel.onclick=async()=>{await api(`/vehicle-transfer-cases/${cancel.dataset.cancelTransfer}/cancel`,{method:'POST',body:'{}'});closeOverlay();toast({message:'Transferência cancelada.'});await mobilityPage(filters)};
  };

  const openFleetProfile=async fleetId=>{
    const profile=await api('/fleets/'+encodeURIComponent(fleetId)+'/profile');
    const companies=await api('/clients/'+encodeURIComponent(profile.fleet.client_id)+'/companies');
    const drawer=openDrawer({title:'Ficha da Frota',subtitle:profile.fleet.name||'',content:renderFleetProfile(profile,{companies:companies.items||[]})});
    drawer.querySelector('.ui-drawer').classList.add('r2-profile-wide');
    const edit=drawer.querySelector('#fleetEditForm');
    edit.onsubmit=async event=>{event.preventDefault();const payload=formData(edit);payload.expected_revision=Number(payload.expected_revision);await api('/fleets/'+encodeURIComponent(fleetId),{method:'PATCH',body:JSON.stringify(payload)});closeOverlay();toast({message:'Frota atualizada.'});await mobilityPage(filters)};
    const addVehicle=drawer.querySelector('[data-add-vehicle-fleet]');
    if(addVehicle)addVehicle.onclick=()=>{closeOverlay();openVehicleDrawer({client_id:profile.fleet.client_id,fleet_id:fleetId})};
    const upload=drawer.querySelector('[data-upload-fleet-photo]');
    if(upload)upload.onclick=()=>{
      const photoDrawer=openDrawer({title:'Foto da Frota',subtitle:profile.fleet.name||'',content:'<form id="fleetPhotoForm"><div class="field"><label>Imagem</label><input name="file" type="file" accept="image/*" required></div><div class="actions"><button class="ui-btn ui-btn-primary">Enviar</button></div></form>'});
      photoDrawer.querySelector('#fleetPhotoForm').onsubmit=async event=>{event.preventDefault();const body=new FormData();body.append('file',new FormData(event.target).get('file'));await apiForm(`/media/fleet/${encodeURIComponent(fleetId)}`,body);closeOverlay();toast({message:'Foto da frota adicionada.'});await mobilityPage(filters)};
    };
    drawer.querySelectorAll('[data-open-vehicle-transfer]').forEach(button=>button.onclick=()=>{const vehicle=profile.vehicles.find(row=>row.id===button.dataset.openVehicleTransfer);if(vehicle)openTransfer(vehicle)});
  };

  document.querySelector('#newVehicle').onclick=()=>openVehicleDrawer();
  document.querySelector('#newFleet').onclick=openFleetDrawer;
  document.querySelectorAll('[data-open-fleet]').forEach(button=>button.onclick=()=>openFleetProfile(button.dataset.openFleet).catch(error=>toast({type:'error',message:error.message})));
  document.querySelectorAll('[data-open-vehicle-transfer]').forEach(button=>button.onclick=()=>{const vehicle=(data.particulars||[]).find(row=>row.id===button.dataset.openVehicleTransfer);if(vehicle)openTransfer(vehicle).catch(error=>toast({type:'error',message:error.message}))});
}

async function catalogPage(){
  const d=await api('/catalog');
  content(renderCatalogPage(d));
  const form=document.querySelector('#catalogForm');
  let costIndex=1;
  document.querySelector('#catalogAddCost').onclick=()=>{
    const box=form.querySelector('.catalog-costs');
    box.insertAdjacentHTML('beforeend',`<div class="row catalog-cost-row"><div class="field"><label>Componente de custo</label><input name="cost_description_${costIndex}"></div><div class="field"><label>Valor</label><input name="cost_amount_${costIndex}" type="text" inputmode="decimal" value="R$ 0,00"></div></div>`);
    costIndex++; bindMoneyInputs(box);
  };
  form.onsubmit=async event=>{event.preventDefault();await api('/catalog',{method:'POST',body:JSON.stringify(catalogPayload(form))});toast({message:'Produto cadastrado.'});show('catalog')};
  document.querySelectorAll('[data-catalog-edit]').forEach(button=>button.onclick=()=>{
    const row=d.items.find(item=>item.id===button.dataset.catalogEdit); if(!row)return;
    const drawer=openDrawer({title:'Editar produto',subtitle:row.code,content:renderCatalogEditForm(row)}); bindMoneyInputs(drawer);
    const edit=drawer.querySelector('#catalogEditForm');
    edit.onsubmit=async event=>{event.preventDefault();const payload=catalogPayload(edit);payload.expected_revision=row.revision;await api('/catalog/'+encodeURIComponent(row.id),{method:'PATCH',body:JSON.stringify(payload)});closeOverlay();toast({message:'Produto atualizado.'});show('catalog')};
  });
}
async function commercialPage(){
  const data=await api('/commercial');
  let purchaseClient=null;
  const legacyTab=current==='purchases'?'purchases':current==='credits'?'credits':'subscriptions';
  let active=(location.hash.match(/^#commercial\/(subscriptions|purchases|credits)$/)?.[1])||legacyTab;
  current='commercial'; document.querySelectorAll('[data-page]').forEach(b=>b.classList.toggle('active',b.dataset.page==='commercial'));
  const draw=()=>{
    content(renderCommercialPage({...data,purchase_client:purchaseClient},active));
    document.querySelectorAll('[data-commercial-tab]').forEach(button=>button.onclick=()=>{active=button.dataset.commercialTab;history.replaceState(null,'','#commercial/'+active);draw()});
    document.querySelectorAll('[data-buy-client]').forEach(button=>button.onclick=()=>{purchaseClient={id:button.dataset.buyClient,display_name:button.dataset.buyClientName};active='purchases';history.replaceState(null,'','#commercial/purchases');draw()});
    const newSubscription=document.querySelector('[data-new-subscription]');if(newSubscription)newSubscription.onclick=()=>openSubscriptionWorkflow({context:'COMMERCIAL',catalog:data.catalog_mensal||[],vehicles:data.vehicles||[],fleets:data.fleets||[]},{onSuccess:()=>show('commercial')});
    const purchase=document.querySelector('#commercialPurchaseForm'); if(purchase){
      const vehicleSelect=purchase.querySelector('[name=vehicle_id]');
      const filterVehicles=client=>{const clientId=client?.id||'';vehicleSelect.disabled=!clientId;for(const option of [...vehicleSelect.options].slice(1))option.hidden=option.dataset.client!==clientId;if(vehicleSelect.selectedOptions[0]?.hidden)vehicleSelect.value=''};
      bindEntityAutocomplete(purchase,{search:searchClientEntities,onSelection:filterVehicles});
      filterVehicles(purchaseClient);
      purchase.onsubmit=async event=>{event.preventDefault();const p=formData(purchase);const item={catalog_id:p.catalog_id,vehicle_id:p.vehicle_id||null,quantity:Number(p.quantity||1)};await api('/direct-sales',{method:'POST',body:JSON.stringify({client_id:p.client_id,sold_on:p.sold_on||new Date().toISOString().slice(0,10),items:[item]})});toast({message:'Compra direta registrada.'});show('commercial')};
    }
    const coverage=document.querySelector('#coverageForm'); if(coverage)coverage.onsubmit=async event=>{event.preventDefault();const p=formData(coverage);p.cycles=Number(p.cycles||1);if(!p.start_on)delete p.start_on;if(!p.value||p.value==='R$ 0,00')delete p.value;await api('/commercial/coverage',{method:'POST',body:JSON.stringify(p)});toast({message:'Tempo ativo registrado.'});show('commercial')};
  }; draw();
}
async function purchasesPage(){
  const [sales,clients,catalog,vehicles]=await Promise.all([api('/direct-sales'),api('/clients'),api('/catalog'),api('/vehicles')]);
  content(pageHeader('Compras Diretas','Vendas avulsas vinculadas aos clientes')+
    renderPurchasesForm({clients:clients.items.filter(row=>!row.archived),catalog:catalog.items,vehicles:vehicles.items.filter(row=>!row.archived)})+
    '<div class="panel"><h3>Compras registradas</h3><div id="purchasesTable"></div></div>');
  const form=document.querySelector('#purchaseForm');
  const items=[];
  const catalogSelect=form.querySelector('#purchaseCatalog');
  const vehicleSelect=form.querySelector('#purchaseVehicle');
  const draw=()=>{form.querySelector('#purchaseItems').innerHTML=items.length?items.map((item,index)=>{
    const catalogRow=catalog.items.find(row=>row.id===item.catalog_id);
    const price=item.unit_price||formatBRL(catalogRow?.price_cents||0);
    return `${index+1}. ${esc(catalogRow?.name||'Item')} · ${item.quantity} unidade(s) · ${esc(price)}`;
  }).join('<br>'):'Nenhum item.'};
  const syncVehicles=()=>{
    const clientId=form.querySelector('[name=client_id]').value;
    [...vehicleSelect.options].forEach(option=>{if(option.value)option.hidden=option.dataset.client!==clientId});
    if(vehicleSelect.selectedOptions[0]?.hidden)vehicleSelect.value='';
  };
  form.querySelector('[name=client_id]').onchange=syncVehicles;
  syncVehicles();
  form.querySelector('#addPurchaseItem').onclick=()=>{
    const catalogId=catalogSelect.value;
    const quantity=Number(form.querySelector('[name=quantity]').value);
    if(!catalogId||!Number.isInteger(quantity)||quantity<=0)return toast({type:'error',message:'Selecione um item e informe uma quantidade positiva.'});
    const item={catalog_id:catalogId,vehicle_id:vehicleSelect.value||null,quantity};
    const unitPrice=form.querySelector('[name=unit_price]').value.trim();
    if(unitPrice)item.unit_price=unitPrice;
    items.push(item);draw();
  };
  form.onsubmit=async event=>{
    event.preventDefault();
    if(!items.length)return toast({type:'error',message:'Adicione ao menos um item.'});
    const payload=formData(form);
    delete payload.quantity;delete payload.unit_price;
    if(!payload.paid_on)delete payload.paid_on;
    payload.items=items;
    await api('/direct-sales',{method:'POST',body:JSON.stringify(payload)});
    toast({message:'Compra registrada.'});await show('purchases');
  };
  const openStatusDrawer=row=>{
    const drawer=openDrawer({title:'Alterar status da compra',subtitle:row.client_name,
      content:`<form id="purchaseStatusForm"><div class="row"><div class="field"><label>Status</label><select name="status"><option value="OPEN">Em aberto</option><option value="PAID">Paga</option><option value="CANCELLED">Cancelada</option></select></div><div class="field"><label>Data do pagamento</label><input name="paid_on" type="date" value="${esc(row.paid_on||'')}"></div></div></form>`,
      actions:'<button type="button" class="ui-btn ui-btn-secondary" data-close-overlay>Fechar</button><button type="submit" form="purchaseStatusForm" class="ui-btn ui-btn-primary">Salvar</button>'});
    drawer.querySelector('[name=status]').value=row.status;
    drawer.querySelector('#purchaseStatusForm').onsubmit=async event=>{
      event.preventDefault();const payload=formData(event.target);
      if(!payload.paid_on)delete payload.paid_on;
      payload.expected_revision=row.revision;
      await api('/direct-sales/'+encodeURIComponent(row.id)+'/status',{method:'PATCH',body:JSON.stringify(payload)});
      closeOverlay();toast({message:'Status atualizado.'});await show('purchases');
    };
  };
  const controller=createTableController({
    columns:[{key:'client_name',label:'Cliente'},{key:'sold_on',label:'Data'},{key:'status',label:'Status',format:value=>esc(valuePtBR(value))},
      {key:'paid_on',label:'Pago em'},{key:'total_cents',label:'Valor',format:value=>formatBRL(value)},{key:'item_count',label:'Itens'}],
    rows:sales.items||[],actions:[{key:'edit',label:'Alterar status',icon:'edit',onClick:openStatusDrawer}]
  });
  mountTableController(document.querySelector('#purchasesTable'),controller);
}
async function chargesPage(){const [d,s]=await Promise.all([api('/charges'),api('/subscriptions')]);content(`<h2>Cobranças</h2><div class="panel"><h3>Gerar competência</h3><form id="chargeForm"><div class="row"><div class="field"><label>Assinatura</label><select name="sid">${select(s.items,'id','id')}</select></div>${field('Competência','competence','month')}</div><div class="actions"><button>Gerar</button></div></form></div><div class="panel"><h3>Ajuste manual</h3><form id="adjustForm"><div class="row"><div class="field"><label>Cobrança</label><select name="id">${select(d.items,'id','id')}</select></div><div class="field"><label>Tipo</label><select name="kind"><option>FEE</option><option>INTEREST</option><option>PENALTY</option><option>DISCOUNT</option><option>OTHER</option></select></div>${moneyField('Valor','amount')}${field('Motivo','reason')}</div><div class="actions"><button>Aplicar ajuste</button></div></form></div>${dt(d.items,'chargesDT')}`);document.querySelector('#chargeForm').onsubmit=async e=>{e.preventDefault();const p=formData(e.target);await api(`/subscriptions/${p.sid}/charges/${p.competence}`,{method:'POST',body:'{}'});show('charges')};document.querySelector('#adjustForm').onsubmit=async e=>{e.preventDefault();const p=formData(e.target);const id=p.id;delete p.id;await api(`/charges/${id}/adjustments`,{method:'POST',body:JSON.stringify(p)});show('charges')}}
async function financePage(){
  const data=await api('/finance');
  const legacyTab=current==='expenses'?'expenses':current==='fiscal'?'fiscal':'payments';
  let active=(location.hash.match(/^#finance\/(payments|expenses|fiscal)$/)?.[1])||legacyTab;
  current='finance';document.querySelectorAll('[data-page]').forEach(b=>b.classList.toggle('active',b.dataset.page==='finance'));
  const draw=()=>{
    content(renderFinancePage(data,active));
    document.querySelectorAll('[data-finance-tab]').forEach(button=>button.onclick=()=>{active=button.dataset.financeTab;history.replaceState(null,'','#finance/'+active);draw()});
    const payment=document.querySelector('#financePaymentForm');if(payment){
      const chargeSelect=payment.querySelector('[name=charge_id]');
      bindEntityAutocomplete(payment,{search:searchClientEntities,onSelection:client=>{const clientId=client?.id||'';chargeSelect.disabled=!clientId;for(const option of [...chargeSelect.options].slice(1))option.hidden=option.dataset.client!==clientId;if(chargeSelect.selectedOptions[0]?.hidden)chargeSelect.value=''}});
      payment.onsubmit=async event=>{event.preventDefault();const p=formData(payment);p.create_credit=p.create_credit==='true';p.allocations=[];if(p.charge_id&&p.allocation_amount&&p.allocation_amount!=='R$ 0,00')p.allocations.push({charge_id:p.charge_id,amount:p.allocation_amount});delete p.charge_id;delete p.allocation_amount;if(!p.paid_on)delete p.paid_on;await api('/payments',{method:'POST',body:JSON.stringify(p)});toast({message:'Recebimento registrado.'});show('finance')};
    }
    const expense=document.querySelector('#financeExpenseForm');if(expense)expense.onsubmit=async event=>{event.preventDefault();const p=formData(expense);if(!p.due_on)delete p.due_on;await api('/expenses',{method:'POST',body:JSON.stringify(p)});toast({message:'Despesa registrada.'});show('finance')};
    const fiscal=document.querySelector('#financeFiscalForm');if(fiscal)fiscal.onsubmit=async event=>{event.preventDefault();const p=formData(fiscal);if(!p.amount)delete p.amount;if(!p.due_on)delete p.due_on;if(!p.external_ref)delete p.external_ref;await api('/fiscal',{method:'POST',body:JSON.stringify(p)});toast({message:'Obrigação fiscal registrada.'});show('finance')};
  };draw();
}
async function paymentsPage(){const [d,c,ch]=await Promise.all([api('/payments'),api('/clients'),api('/charges')]);content(`<h2>Recebimentos</h2><div class="panel"><form id="payForm"><div class="row"><div class="field"><label>Cliente</label><select name="client_id">${select(c.items)}</select></div>${moneyField('Valor','amount')}${field('Data','paid_on','date')}${field('Método','method')}</div><h4>Alocações</h4><div class="alloc-grid">${ch.items.map(x=>`<label>${esc(x.id.slice(0,8))} · ${formatBRL(x.amount_cents+x.adjustment_cents)} <input data-charge="${x.id}" data-money-input type="text" inputmode="decimal" autocomplete="off" placeholder="R$ 0,00"></label>`).join('')}</div><label><input type="checkbox" name="create_credit" value="true"> Transformar sobra em crédito</label><div class="actions"><button>Registrar pagamento</button></div></form></div><div class="panel"><h3>Estornar pagamento</h3><form id="reversePay"><div class="field"><label>Pagamento</label><select name="id">${select(d.items,'id','id')}</select></div><div class="actions"><button class="danger">Estornar</button></div></form></div>${dt(d.items,'paymentsDT')}`);document.querySelector('#payForm').onsubmit=async e=>{e.preventDefault();const p=formData(e.target);p.create_credit=p.create_credit==='true';p.allocations=[...document.querySelectorAll('[data-charge]')].filter(x=>x.value.trim()).map(x=>({charge_id:x.dataset.charge,amount:x.value.trim()}));if(!p.paid_on)delete p.paid_on;await api('/payments',{method:'POST',body:JSON.stringify(p)});show('payments')};document.querySelector('#reversePay').onsubmit=async e=>{e.preventDefault();const id=formData(e.target).id;if(confirm('Confirmar estorno?')){await api(`/payments/${id}/reverse`,{method:'POST',body:'{}'});show('payments')}}}
async function creditsPage(){const [d,ch]=await Promise.all([api('/credits'),api('/charges')]);content(`<h2>Créditos</h2><div class="panel"><form id="creditForm"><div class="row"><div class="field"><label>Crédito</label><select name="credit_id">${select(d.items.filter(x=>x.status==='OPEN'),'id','id')}</select></div><div class="field"><label>Cobrança</label><select name="charge_id">${select(ch.items,'id','id')}</select></div>${moneyField('Valor','amount')}</div><div class="actions"><button>Aplicar crédito</button></div></form></div>${dt(d.items,'creditsDT')}`);document.querySelector('#creditForm').onsubmit=async e=>{e.preventDefault();const p=formData(e.target);const id=p.credit_id;delete p.credit_id;await api(`/credits/${id}/apply`,{method:'POST',body:JSON.stringify(p)});show('credits')}}
async function expensesPage(){const d=await api('/expenses');content(`<h2>Despesas</h2><div class="panel"><h3>Nova despesa</h3><form id="expForm"><div class="row">${field('Categoria*','category')}${field('Descrição*','description')}${field('Competência*','competence','month')}${moneyField('Valor previsto*','expected_amount',null,true)}${field('Vencimento','due_on','date')}${field('Fornecedor','supplier')}</div><div class="actions"><button>Salvar</button></div></form></div><div class="panel"><h3>Desembolso</h3><form id="disbForm"><div class="row"><div class="field"><label>Despesa</label><select name="id">${select(d.items,'id','description')}</select></div>${moneyField('Valor','amount')}${field('Data','paid_on','date')}</div><div class="actions"><button>Registrar desembolso</button></div></form></div><div class="panel"><h3>Gerar recorrência</h3><form id="recurForm"><div class="row"><div class="field"><label>Despesa origem</label><select name="id">${select(d.items,'id','description')}</select></div>${field('Nova competência','competence','month')}</div><div class="actions"><button>Gerar recorrência</button></div></form></div><div class="panel"><h3>Estornar desembolso</h3><form id="reverseDisb"><div class="row">${field('ID do desembolso','id')}</div><div class="actions"><button class="danger">Estornar</button></div></form></div>${dt(d.items,'expensesDT')}`);document.querySelector('#expForm').onsubmit=async e=>{e.preventDefault();await api('/expenses',{method:'POST',body:JSON.stringify(formData(e.target))});show('expenses')};document.querySelector('#disbForm').onsubmit=async e=>{e.preventDefault();const p=formData(e.target);const id=p.id;delete p.id;if(!p.paid_on)delete p.paid_on;await api(`/expenses/${id}/disbursements`,{method:'POST',body:JSON.stringify(p)});show('expenses')};document.querySelector('#recurForm').onsubmit=async e=>{e.preventDefault();const p=formData(e.target);await api(`/expenses/${p.id}/recur/${p.competence}`,{method:'POST',body:'{}'});show('expenses')};document.querySelector('#reverseDisb').onsubmit=async e=>{e.preventDefault();const id=formData(e.target).id;await api(`/disbursements/${id}/reverse`,{method:'POST',body:'{}'});show('expenses')}}
async function fiscalPage(){const d=await api('/fiscal');content(`<h2>Acompanhamento fiscal manual</h2><div class="notice">Não transmite nem emite documento fiscal oficial.</div><div class="panel"><form id="fisForm"><div class="row">${field('Competência*','competence','month')}${field('Descrição*','description')}${moneyField('Valor','amount')}${field('Vencimento','due_on','date')}${field('Referência externa','external_ref')}</div><div class="actions"><button>Salvar referência</button></div></form></div>${dt(d.items,'fiscalDT')}`);document.querySelector('#fisForm').onsubmit=async e=>{e.preventDefault();await api('/fiscal',{method:'POST',body:JSON.stringify(formData(e.target))});show('fiscal')}}
async function filesPage(){
  const [media,attachments]=await Promise.all([api('/media'),api('/attachments')]);
  content(renderFilesPage({media:media.items||[],attachments:attachments.items||[]}));
  const mediaForm=document.querySelector('#mediaForm');
  if(mediaForm)mediaForm.onsubmit=async event=>{event.preventDefault();const fd=new FormData(event.target),type=fd.get('entity_type'),id=fd.get('entity_id'),file=fd.get('file'),retain=fd.get('retain_original')==='true';const body=new FormData();body.append('file',file);await apiForm(`/media/${encodeURIComponent(type)}/${encodeURIComponent(id)}?retain_original=${retain}`,body);toast({message:'Foto adicionada.'});await filesPage()};
  const upload=document.querySelector('#attachmentUploadForm');
  if(upload)upload.onsubmit=async event=>{event.preventDefault();const fd=new FormData(event.target),type=fd.get('entity_type'),id=fd.get('entity_id'),file=fd.get('file');const body=new FormData();body.append('file',file);await apiForm(`/attachments/${encodeURIComponent(type)}/${encodeURIComponent(id)}`,body);toast({message:'Arquivo anexado.'});await filesPage()};
  const link=document.querySelector('#attachmentLinkForm');
  if(link)link.onsubmit=async event=>{event.preventDefault();const payload=formData(event.target);await api('/attachments/link',{method:'POST',body:JSON.stringify(payload)});toast({message:'Link salvo.'});await filesPage()};
}

function reportsPage(){const names=['clients','vehicles','charges','payments','credits','expenses'];content(`<h2>Relatórios</h2><div class="panel"><p>CSV e XLSX com neutralização de formula injection.</p><div class="report-grid">${names.map(n=>`<div class="card"><strong>${esc(n)}</strong><div class="actions"><button data-report="${n}" data-ext="csv">CSV</button><button data-report="${n}" data-ext="xlsx" class="secondary">XLSX</button></div></div>`).join('')}</div></div>`);document.querySelectorAll('[data-report]').forEach(b=>b.onclick=()=>downloadReport(b.dataset.report,b.dataset.ext))}
async function downloadReport(name,ext){const r=await fetch(`/api/v1/reports/${name}.${ext}`);if(!r.ok)throw new Error('Falha no relatório');const a=document.createElement('a');a.href=URL.createObjectURL(await r.blob());a.download=`${name}.${ext}`;a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000)}
async function systemPage(){const [st,sets,baks,ints,stations,audit]=await Promise.all([api('/auth/setup-status'),api('/settings'),api('/backups'),api('/integrations'),api('/stations'),api('/audit?limit=100')]);content(`<h2>Sistema</h2><div class="panel"><h3>Administradores</h3>${dt(st.admins,'adminsDT')}<form id="resetForm"><div class="row">${field('Slot para reset','slot','number')}${field('Motivo','reason')}</div><div class="actions"><button class="danger">Resetar slot</button></div></form><form id="pwdForm"><div class="row">${field('Senha atual','current_password','password')}${field('Nova senha','new_password','password')}</div><div class="actions"><button>Trocar minha senha</button></div></form><div id="adminOut"></div></div><div class="panel"><h3>Branding e configuração</h3><form id="settingsForm"><div class="row">${field('Empresa','company_display_name','text',sets.company_display_name||'')}${field('Telefone','contact_phone','text',sets.contact_phone||'')}${field('E-mail','contact_email','email',sets.contact_email||'')}${field('Endereço público','address_display','text',sets.address_display||'')}${field('Cor primária','theme_primary','color',sets.theme_primary||'#155eef')}${field('Cor destaque','theme_accent','color',sets.theme_accent||'#0f9f6e')}${field('Retenção backups','backup_retention','number',sets.backup_retention||'14')}</div><div class="actions"><button>Salvar configurações</button></div></form><form id="brandForm"><div class="row"><div class="field"><label>Tipo</label><select name="kind"><option>logo</option><option>favicon</option><option>icon</option></select></div><div class="field"><label>Imagem</label><input name="file" type="file" accept="image/*"></div></div><div class="actions"><button>Enviar branding</button></div></form></div><div class="panel"><h3>Backup</h3><div class="actions"><button id="backup">Criar backup cifrado</button></div><form id="restoreForm"><div class="field"><label>Restaurar .usbk</label><input name="file" type="file" accept=".usbk" required></div><div class="actions"><button class="danger">Restaurar backup</button></div></form>${dt(baks.items,'backupsDT')}</div><div class="panel"><h3>Recovery / transferência</h3><form id="recoveryForm"><div class="row">${field('Passphrase (12+ caracteres)','passphrase','password')}<label><input name="transfer" type="checkbox" value="true"> Preparar transferência e desarmar esta escritora</label></div><div class="actions"><button>Gerar .usre</button></div></form><div id="recoveryOut"></div></div><div class="panel"><h3>Estações</h3>${dt(stations.items,'stationsDT')}<form id="claimForm"><div class="actions"><button>ASSUMIR ESCRITA pendente</button></div></form><form id="emergencyForm"><div class="row">${field('Motivo da emergência','reason')}</div><div class="actions"><button class="danger">ASSUMIR EMERGÊNCIA</button></div></form></div><div class="panel"><h3>Auditoria</h3><div class="actions"><button id="verifyAudit">Verificar cadeia</button></div><div id="auditOut"></div>${dt(audit.items,'auditDT')}</div><div class="panel"><h3>Integrações futuras</h3><pre>${esc(JSON.stringify(ints,null,2))}</pre></div>${me.environment==='test'?`<div class="panel"><h3>Laboratório Test</h3><button id="resetTest" class="danger">LIMPAR TESTES</button></div>`:''}<div class="panel"><h3>Sessão</h3><div class="actions"><button id="logout" class="secondary">Sair</button><button id="shutdown" class="danger">Encerrar sistema</button></div></div>`);document.querySelector('#settingsForm').onsubmit=async e=>{e.preventDefault();await api('/settings',{method:'PUT',body:JSON.stringify(formData(e.target))});show('system')};document.querySelector('#brandForm').onsubmit=async e=>{e.preventDefault();const fd=new FormData(e.target),kind=fd.get('kind'),file=fd.get('file');const body=new FormData();body.append('file',file);await apiForm('/branding/'+kind,body);location.reload()};document.querySelector('#backup').onclick=async()=>{await api('/backups',{method:'POST',body:'{}'});show('system')};document.querySelector('#restoreForm').onsubmit=async e=>{e.preventDefault();if(!confirm('Restaurar este backup e substituir o ambiente atual?'))return;const fd=new FormData();fd.append('file',new FormData(e.target).get('file'));await apiForm('/backups/restore',fd);show('dashboard')};document.querySelector('#recoveryForm').onsubmit=async e=>{e.preventDefault();const p=formData(e.target);p.transfer=p.transfer==='true';const r=await api('/recovery/export',{method:'POST',body:JSON.stringify(p)});document.querySelector('#recoveryOut').innerHTML=msg(`Recovery criado: ${r.name}`,'notice')+`<a class="download-link" href="/api/v1/recovery/${encodeURIComponent(r.name)}">Baixar ${esc(r.name)}</a>`;if(p.transfer){me.station={...(me.station||{}),is_writer:0};toast({message:'Estação atual alterada para somente leitura.'})}};document.querySelector('#claimForm').onsubmit=async e=>{e.preventDefault();await api('/stations/claim',{method:'POST',body:JSON.stringify({confirm:'ASSUMIR ESCRITA'})});location.reload()};document.querySelector('#emergencyForm').onsubmit=async e=>{e.preventDefault();const reason=formData(e.target).reason;if(!confirm('Use apenas se a estação escritora anterior foi retirada de operação. Continuar?'))return;await api('/stations/emergency-takeover',{method:'POST',body:JSON.stringify({confirm:'ASSUMIR EMERGENCIA',reason})});location.reload()};document.querySelector('#verifyAudit').onclick=async()=>{const r=await api('/audit/verify');document.querySelector('#auditOut').innerHTML=msg(r.ok?`Cadeia íntegra (${r.events} eventos)`:`Cadeia quebrada no evento ${r.broken_at_id}`,r.ok?'success':'error')};document.querySelector('#resetForm').onsubmit=async e=>{e.preventDefault();const p=formData(e.target);try{const r=await api('/auth/reset-admin/'+p.slot,{method:'POST',body:JSON.stringify({reason:p.reason})});document.querySelector('#adminOut').innerHTML=msg('Ticket: '+r.ticket,'notice')}catch(err){document.querySelector('#adminOut').innerHTML=msg(err.message,'error')}};document.querySelector('#pwdForm').onsubmit=async e=>{e.preventDefault();await api('/auth/change-password',{method:'POST',body:JSON.stringify(formData(e.target))});me=null;boot()};if(document.querySelector('#resetTest'))document.querySelector('#resetTest').onclick=async()=>{await api('/sandbox/reset',{method:'POST',body:JSON.stringify({confirm:'LIMPAR TESTES'})});show('dashboard')};document.querySelector('#logout').onclick=async()=>{await api('/auth/logout',{method:'POST',body:'{}'});me=null;boot()};document.querySelector('#shutdown').onclick=async()=>{await api('/system/shutdown',{method:'POST',body:'{}'});content('<div class="success">Sistema encerrado com segurança.</div>')}}
document.addEventListener?.('click',e=>{if(e.target?.id==='shutdown'){e.preventDefault();e.stopImmediatePropagation();requestSystemShutdown().catch(err=>alert(err.message))}},true);
const nativeAlert=globalThis.alert?.bind(globalThis);if(nativeAlert)globalThis.alert=message=>nativeAlert(messagePtBR(message));observePtBR(document.body);localizeDom(document.body);loadIconSet().then(boot).catch(e=>app.innerHTML=`<section class="auth"><div class="error">${esc(messagePtBR(e.message))}</div></section>`);
