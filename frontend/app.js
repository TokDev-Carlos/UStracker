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
import { closeSubscriptionPopover, openSubscriptionPopover } from './ui/subscription-popover.js';
import { bindClientProfileUi } from './ui/client-profile.js';
import { bindActionButton, bindActionForm, runDomAction } from './ui/action-state.js';
import { buildClientCreatePayload, clientTableDefinition, renderClientEditor } from './pages/clients.js';
import { buildMobilityQuery, buildVehiclePayload, renderFleetProfile, renderMobilityPage, renderTransferCaseForm } from './pages/mobility.js';
import { bindCatalogForm, catalogPayload, renderCatalogEditForm, renderCatalogPage } from './pages/catalog.js';
import { renderCommercialPage, renderSubscriptionAmendForm, subscriptionMenuItems } from './pages/commercial.js';
import { openActionMenu } from './ui/action-menu.js';
import { renderFinancePage, renderSellExpenseForm } from './pages/finance.js';
import { localToday, openPaymentDialog } from './ui/payment-dialog.js';
import { renderOverviewDrilldown, renderOverviewPage } from './pages/dashboard.js';
import { entityChoices, renderFilesPage } from './pages/files.js';

const app=document.querySelector('#app');
let csrf=''; let me=null; let current='dashboard'; let navigationSequence=0; let systemNavigationLease=null;
const apiClient=createApi({csrfState:{get:()=>csrf,set:value=>{csrf=value}}});
const session=createSession({api:apiClient,onUserChange:user=>{me=user}});
// AJ-03: every successful mutation re-reads the page behind any open drawer, so projections never need F5.
let pageReload=null,projectionTimer=null;
function scheduleProjectionRefresh(path,method){
  if(!method||['GET','HEAD','OPTIONS'].includes(String(method).toUpperCase())||/^\/(auth|system\/shutdown)/.test(path))return;
  const seq=navigationSequence;clearTimeout(projectionTimer);
  projectionTimer=setTimeout(()=>{if(seq!==navigationSequence||typeof pageReload!=='function')return;Promise.resolve(pageReload()).catch(()=>{})},300);
}
const api=(path,opt)=>path==='/auth/logout'?session.logout():apiClient.request(path,opt).then(result=>{if(path==='/auth/login')session.authenticate(result);scheduleProjectionRefresh(path,opt?.method);return result});
const getCsrf=()=>apiClient.acquireCsrf();
const apiForm=(path,form,method='POST')=>apiClient.requestForm(path,form,method).then(result=>{scheduleProjectionRefresh(path,method);return result});
const searchClientEntities=async(query,limit=30)=>(await api('/entities/clients?q='+encodeURIComponent(query)+'&limit='+Math.min(Number(limit)||30,30))).items||[];
const tableStore=new Map();
const esc=s=>String(s??'').replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
const sessionProfileLabel=user=>user?.role||(user?.slot?'Administrador':'Usuário');
async function requestSystemShutdown(){const bridge=window.chrome?.webview;if(bridge){bridge.postMessage('system-shutdown');return}await api('/system/shutdown',{method:'POST',body:'{}'});alert('Sistema encerrado com segurança.')}
// AJ-06 — one delegated handler for every subscription count (pages and drawers).
document.addEventListener('click',event=>{
  const button=event.target.closest?.('[data-subs-vehicle],[data-subs-fleet]');
  if(button){event.preventDefault();const query=button.dataset.subsVehicle?'vehicle_id='+encodeURIComponent(button.dataset.subsVehicle):'fleet_id='+encodeURIComponent(button.dataset.subsFleet);
    openSubscriptionPopover(button,()=>api('/mobility/subscriptions?'+query),{onCommercial:(tab,code)=>{closeOverlay();history.replaceState(null,'','#commercial/'+tab+(code?'/'+encodeURIComponent(code):''));show('commercial')}});return}
  if(!event.target.closest?.('#subsPopover'))closeSubscriptionPopover();
});
// R14 — one visible action: choosing the file uploads it; removal always asks for confirmation.
async function refreshAfterMedia(){const profile=document.querySelector('.cp');if(profile){const clientId=profile.dataset.clientId;const tab=profile.dataset.cpActive;closeOverlay();if(clientId)await openClientProfile(clientId,{tab})}else if(typeof pageReload==='function')await pageReload()}
document.addEventListener('change',event=>{
  const input=event.target;const kind=input?.dataset?.vehiclePhoto?'vehicle':input?.dataset?.fleetPhoto?'fleet':null;if(!kind||!input.files?.[0])return;
  const id=input.dataset.vehiclePhoto||input.dataset.fleetPhoto;const body=new FormData();body.append('file',input.files[0]);
  runDomAction({key:`${kind}-photo:${id}`,scope:input.closest('label')||input,action:()=>apiForm(`/media/${kind}/${encodeURIComponent(id)}`,body),refresh:refreshAfterMedia,successMessage:'Foto enviada.',notify:toast}).finally(()=>{input.value=''});
});
document.addEventListener('click',event=>{
  const button=event.target.closest?.('[data-remove-photo]');if(!button)return;event.preventDefault();
  if(!confirm('Remover esta foto? Esta ação não pode ser desfeita.'))return;
  runDomAction({key:`media-remove:${button.dataset.removePhoto}`,scope:button,action:()=>api('/media/'+encodeURIComponent(button.dataset.removePhoto),{method:'DELETE'}),refresh:refreshAfterMedia,successMessage:'Foto removida.',notify:toast});
});
document.addEventListener('keydown',event=>{if(event.key==='Escape'&&document.querySelector('#subsPopover')){event.stopPropagation();closeSubscriptionPopover()}},true);
function formData(form){const o={};for(const [k,v] of new FormData(form).entries())o[k]=v;return o}
function enableAutoUpload(form){const input=form?.querySelector('input[type="file"]');if(input)input.onchange=()=>{if(input.files?.length)form.requestSubmit()};return form}
function msg(text,type='success'){return `<div class="${type}">${esc(text)}</div>`}
const PAGE_SUBTITLES={'Visão Geral':'Resultado, previsão do mês e situação dos clientes','Comercial':'Assinaturas, compras diretas e tempo ativo','Financeiro':'Recebimentos, despesas e obrigações fiscais','Fotos/Arquivos':'Fotos e anexos vinculados a clientes, veículos, frotas e assinaturas','Relatórios':'Exportação de dados em CSV e Excel','Sistema':'Administração, backup e diagnóstico','Planos/Produtos':'Planos mensais e produtos avulsos'};
function content(html,lease=null){if((lease!==null&&lease!==navigationSequence)||(String(html).startsWith('<h2>Sistema')&&systemNavigationLease!==navigationSequence))return false;const normalized=html.replace(/^<h2>([^<]+)<\/h2>/,(_,title)=>pageHeader(title,PAGE_SUBTITLES[title]||'Gestão administrativa')).replaceAll('>Publicar<','>Exibir no catálogo público<');const target=document.querySelector('#content');target.innerHTML=normalized;hydrateTables();bindMoneyInputs(target);localizeDom(target);queueMicrotask(bindSystemActions);return true}
function applyBrand(p){const b=p?.brand||{};if(b.theme_primary)document.documentElement.style.setProperty('--primary',b.theme_primary);if(b.theme_accent)document.documentElement.style.setProperty('--accent',b.theme_accent);document.title=(b.company_display_name||'UStracker')+' — UStracker';const fav=b.assets?.favicon;if(fav){let l=document.querySelector('#dynamicFavicon');if(!l){l=document.createElement('link');l.id='dynamicFavicon';l.rel='icon';document.head.appendChild(l)}l.href=fav+'?v='+Date.now()}}
const DIAGNOSTIC_TABLES=new Set(['auditDT','stationsDT','adminsDT','backupsDT']);
function dt(items,id){const rows=items||[];const technical=k=>!DIAGNOSTIC_TABLES.has(id)&&(k==='id'||k.endsWith('_id'));const keys=rows.length?Object.keys(rows[0]).filter(k=>!['notes','address','before_json','after_json'].includes(k)&&!technical(k)).sort((a,b)=>(b==='code')-(a==='code')).slice(0,12):[];const isDateKey=key=>key.endsWith('_on')||key.endsWith('_at')||['created_at','updated_at','paid_on','due_on','start_on','end_on','sold_on','installed_on'].includes(key);const columns=keys.map(key=>({key,label:key==='code'?'Código':labelPtBR(key),format:key==='code'?value=>value?`<span class="ui-code">${esc(value)}</span>`:'—':key.endsWith('_cents')?value=>formatBRL(Number(value||0)):isDateKey(key)?value=>esc(formatDateBR(value,key.endsWith('_at'))):value=>esc(valuePtBR(value))}));tableStore.set(id,createTableController({columns,rows}));return `<div id="${id}" class="data-table"></div>`}
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
function loginScreen(st,pub){app.innerHTML=renderLoginScreen(st,pub);document.querySelector('#login').onsubmit=async e=>{e.preventDefault();try{await getCsrf();const r=await api('/auth/login',{method:'POST',body:JSON.stringify(formData(e.target))});csrf=r.csrf;me=r;renderShell();await show('dashboard');if(r.backup_warning)alert('Backup automático: '+r.backup_warning)}catch(err){document.querySelector('#loginOut').innerHTML=msg(err.message,'error')}}}
const nav=[['dashboard','Visão geral'],['clients','Clientes'],['mobility','Frotas/Veículos'],['catalog','Planos/Produtos'],['commercial','Comercial'],['finance','Financeiro'],['files','Fotos/Arquivos'],['reports','Relatórios'],['system','Sistema']];
function renderShell(){renderAppShell({me,nav,onNavigate:show,onSearch:async query=>{const d=await api('/search?q='+encodeURIComponent(query));tableStore.clear();content(pageHeader('Pesquisa','Resultados da busca global')+dt(d.items,'searchTable'))},onHelp:()=>{const help=helpFor(current);openDrawer({title:help.title,subtitle:'Ajuda contextual',content:`<p>${esc(help.body)}</p>${HELP[current]?.fields?`<dl>${Object.entries(HELP[current].fields).map(([key,value])=>`<dt><strong>${esc(key.replaceAll('_',' '))}</strong></dt><dd>${esc(value)}</dd>`).join('')}</dl>`:''}`})},onUser:()=>content(pageHeader('Usuário','Sessão atual')+`<div class="panel"><strong>${esc(me.name)}</strong><p class="muted">Perfil: ${esc(sessionProfileLabel(me))}</p><p class="muted">Ambiente: ${esc(me.environment)}</p></div>`),onLogout:async()=>{await session.logout();await boot()},onShutdown:requestSystemShutdown})}
function bindClientJourney(drawer,profile,clientId){
  const reopen=focus=>async()=>{closeOverlay();await openClientProfile(clientId,{focus})};
  bindClientProfileUi(drawer);
  drawer.querySelectorAll('[data-open-commercial]').forEach(button=>button.onclick=()=>{closeOverlay();history.replaceState(null,'','#commercial/'+button.dataset.openCommercial+(button.dataset.code?'/'+encodeURIComponent(button.dataset.code):''));show('commercial')});
  const vehicleForm=drawer.querySelector('#clientVehicleForm');
  if(vehicleForm){
    const typeSelect=vehicleForm.querySelector('[name=type]');const customField=vehicleForm.querySelector('.custom-type-field');
    typeSelect.onchange=()=>{customField.hidden=typeSelect.value!=='__custom__';customField.querySelector('input').required=!customField.hidden};
    bindActionForm(vehicleForm,{key:`client-vehicle:${clientId}`,action:async()=>{const payload=buildVehiclePayload({...formData(vehicleForm),client_id:clientId});await api('/vehicles',{method:'POST',body:JSON.stringify(payload)})},refresh:reopen('mobility'),successMessage:'Veículo cadastrado. Próximo passo: plano ou compra.',notify:toast});
  }
  const fleetForm=drawer.querySelector('#clientFleetForm');
  if(fleetForm)bindActionForm(fleetForm,{key:`client-fleet:${clientId}`,action:async()=>{await api('/fleets',{method:'POST',body:JSON.stringify({...formData(fleetForm),client_id:clientId})})},refresh:reopen('mobility'),successMessage:'Frota cadastrada.',notify:toast});
  const purchaseForm=drawer.querySelector('#clientPurchaseForm');
  if(purchaseForm){
    const catalogSelect=purchaseForm.querySelector('[data-avulsa-catalog]');
    api('/catalog').then(result=>{const rows=(result.items||[]).filter(row=>Number(row.active??1)===1&&String(row.category||'').toUpperCase()==='AVULSA');catalogSelect.innerHTML=rows.length?'<option value="">Selecione</option>'+rows.map(row=>`<option value="${esc(row.id)}">${esc(row.name||row.description)} · ${esc(formatBRL(Number(row.price_cents||0)))}</option>`).join(''):'<option value="">Nenhum produto avulso ativo</option>'}).catch(error=>toast({type:'error',message:error.message}));
    bindActionForm(purchaseForm,{key:`client-purchase:${clientId}`,action:async()=>{const p=formData(purchaseForm);if(!p.catalog_id)throw new Error('Selecione o produto avulso.');await api('/direct-sales',{method:'POST',body:JSON.stringify({client_id:clientId,sold_on:p.sold_on||localToday(),items:[{catalog_id:p.catalog_id,vehicle_id:p.vehicle_id||null,quantity:Number(p.quantity||1)}]})})},refresh:reopen('commercial'),successMessage:'Compra direta registrada.',notify:toast});
  }
}
async function openClientProfile(clientId,options={}){
  const profile=await api('/clients/'+encodeURIComponent(clientId)+'/profile');
  const drawer=openDrawer({title:'Ficha do Cliente',subtitle:[profile.client?.legal_name,profile.client?.code].filter(Boolean).join(' · '),content:renderClientProfile(profile,options)});
  drawer.querySelector('.ui-drawer').classList.add('r2-profile-wide','cp-drawer');
  const refresh=async()=>{const tab=drawer.querySelector('.cp')?.dataset.cpActive;closeOverlay();await openClientProfile(clientId,{tab})};
  const basics=drawer.querySelector('#clientBasicsForm');
  bindActionForm(basics,{key:`client-basics:${clientId}`,action:async()=>{const payload=formData(basics);payload.expected_revision=profile.client.revision;await api('/clients/'+encodeURIComponent(clientId),{method:'PATCH',body:JSON.stringify(payload)})},refresh,successMessage:'Dados do cliente atualizados.',notify:toast});
  const companyForm=drawer.querySelector('#clientCompanyForm');
  bindActionForm(companyForm,{key:`client-company:${clientId}`,action:async()=>{const payload=formData(companyForm);payload.is_primary=payload.is_primary==='true';await api('/clients/'+encodeURIComponent(clientId)+'/companies',{method:'POST',body:JSON.stringify(payload)})},refresh,successMessage:'Empresa adicionada.',notify:toast});
  const photoForm=drawer.querySelector('#clientPhotoForm');
  enableAutoUpload(photoForm);
  bindActionForm(photoForm,{key:`client-photo:${clientId}`,action:async()=>{const input=photoForm.querySelector('[name=file]');if(!input.files?.[0])throw new Error('Selecione uma imagem.');const body=new FormData();body.append('file',input.files[0]);await apiForm('/media/client/'+encodeURIComponent(clientId),body)},refresh,successMessage:'Foto do cliente atualizada.',notify:toast});
  const signatureForm=drawer.querySelector('#clientSignatureForm');
  enableAutoUpload(signatureForm);
  bindActionForm(signatureForm,{key:`client-signature:${clientId}`,action:async()=>{const input=signatureForm.querySelector('[name=file]');const subscriptionId=signatureForm.querySelector('[name=subscription_id]')?.value;if(!subscriptionId||!input.files?.[0])throw new Error('Selecione a assinatura e o arquivo.');const body=new FormData();body.append('file',input.files[0]);await apiForm('/attachments/subscription/'+encodeURIComponent(subscriptionId),body)},refresh,successMessage:'Assinatura anexada.',notify:toast});
  bindClientJourney(drawer,profile,clientId,options);
  const newSubscription=drawer.querySelector('[data-client-new-subscription]');
  const journeySubscription=drawer.querySelector('[data-journey-subscription]');
  if(journeySubscription&&newSubscription)journeySubscription.onclick=()=>newSubscription.click();
  if(newSubscription)newSubscription.onclick=async()=>{const catalog=await api('/catalog');openSubscriptionWorkflow({context:'CLIENT_PROFILE',clientId,clients:[profile.client],catalog:catalog.items||[],vehicles:profile.vehicles||[],fleets:profile.fleets||[]},{onSuccess:()=>openClientProfile(clientId,{focus:'commercial'}),onCancel:()=>openClientProfile(clientId)})};
  // AJ-12 — pay from the profile (client and, from a row, the subscription come pre-selected).
  drawer.querySelectorAll('[data-client-payment]').forEach(button=>button.onclick=()=>{const tab=drawer.querySelector('.cp')?.dataset.cpActive;openPaymentDialog({api,search:searchClientEntities,client:{id:clientId,display_name:profile.client?.legal_name},subscriptionId:button.dataset.subscriptionId||'',notify:toast,onSuccess:()=>openClientProfile(clientId,{tab})})});
  return drawer;
}
async function show(page){if(page==='fleets'||page==='vehicles')page='mobility';const lease=++navigationSequence;pageReload=()=>show(page);systemNavigationLease=page==='system'?lease:null;current=page;tableStore.clear();document.querySelectorAll('[data-page]').forEach(b=>b.classList.toggle('active',b.dataset.page===page));try{const fn={dashboard:()=>dashboardPage('',lease),clients:()=>clientsPage(lease),mobility:()=>mobilityPage({},lease),catalog:()=>catalogPage(lease),commercial:()=>commercialPage(lease),subscriptions:()=>commercialPage(lease),purchases:()=>commercialPage(lease),charges:()=>commercialPage(lease),credits:()=>commercialPage(lease),finance:()=>financePage(lease),payments:()=>financePage(lease),expenses:()=>financePage(lease),fiscal:()=>financePage(lease),files:()=>filesPage(lease),media:()=>filesPage(lease),reports:()=>reportsPage(lease),system:()=>systemPage(lease)}[page];if(fn)await fn()}catch(e){content(`<div class="error">${esc(e.message)}</div>`,lease)}}
async function dashboardPage(query='',lease=null,year=''){
  const params=new URLSearchParams();if(query)params.set('q',query);if(year)params.set('year',year);
  const d=await api('/dashboard'+(params.size?'?'+params.toString():''));
  if(!content(renderOverviewPage(d,query,year),lease))return;
  pageReload=()=>dashboardPage(query,null,year);
  const form=document.querySelector('#overviewSearch');if(form)form.onsubmit=async event=>{event.preventDefault();await dashboardPage(formData(form).q||'',null,year)};
  const drill=document.querySelector('[data-overview-drilldown]');if(drill)drill.onclick=async()=>{try{const data=await api('/dashboard/drilldown'+(year?'?year='+encodeURIComponent(year):''));const drawer=openDrawer({title:'Detalhamento financeiro',subtitle:data.label==='Geral'?'Período: Geral':'Ano '+data.label,content:renderOverviewDrilldown(data)});drawer.querySelector('.ui-drawer').classList.add('r2-profile-wide')}catch(error){toast({type:'error',message:error.message})}};
  const period=document.querySelector('#overviewPeriod [name=year]');if(period)period.onchange=()=>dashboardPage(query,null,period.value);
  const clear=document.querySelector('#overviewClear');if(clear)clear.onclick=()=>dashboardPage('',null,year);
  document.querySelectorAll('[data-profile-id]').forEach(button=>button.onclick=()=>openClientProfile(button.dataset.profileId).catch(error=>toast({type:'error',message:error.message})));
}
async function clientsPage(lease=null){
  const d=await api('/clients');
  if(!content(pageHeader('Clientes','Cadastros e relacionamento','<button type="button" id="archiveClients" class="ui-btn ui-btn-danger" disabled>Excluir selecionados</button><button type="button" id="newClient" class="ui-btn ui-btn-primary">Novo cliente</button>')+'<div id="clientsCentralTable"></div>',lease))return;
  const newButton=document.querySelector('#newClient');
  const archiveButton=document.querySelector('#archiveClients');
  newButton.onclick=()=>{
    const drawer=openDrawer({title:'Novo cliente',subtitle:'Cadastre documento e ao menos um contato.',content:renderClientEditor(),actions:'<button type="button" class="ui-btn ui-btn-secondary" data-close-overlay>Cancelar</button><button type="submit" form="clientDrawerForm" class="ui-btn ui-btn-primary">Salvar</button>'});
    drawer.querySelectorAll('[data-close-overlay]').forEach(button=>button.onclick=()=>closeOverlay());
    const createForm=drawer.querySelector('#clientDrawerForm');
    bindActionForm(createForm,{key:'client-create',action:async()=>{const flat=formData(createForm);if(!flat.email?.trim()&&!flat.phone?.trim())throw new Error('Informe ao menos e-mail ou telefone.');const payload=buildClientCreatePayload(flat);const created=await api('/clients',{method:'POST',body:JSON.stringify(payload)});closeOverlay();return created},refresh:async created=>{await show('clients');if(created?.id)await openClientProfile(created.id,{focus:'mobility'})},successMessage:'Cliente cadastrado. Continue com veículo/frota e plano.',notify:toast});
  };
  const definition=clientTableDefinition(row=>openClientProfile(row.id).catch(error=>toast({type:'error',message:error.message})));
  const controller=createTableController({...definition,rows:d.items});
  const updateSelection=ids=>{archiveButton.disabled=!ids.length;archiveButton.textContent=ids.length?`Excluir selecionados (${ids.length})`:'Excluir selecionados'};
  mountTableController(document.querySelector('#clientsCentralTable'),controller,{onSelectionChange:updateSelection});
  archiveButton.onclick=()=>{const ids=controller.view().selectedIds;if(!ids.length||!confirm(`Arquivar ${ids.length} cliente(s) selecionado(s)?`))return;return runDomAction({key:'client-archive',scope:archiveButton,action:()=>api('/clients/archive',{method:'POST',body:JSON.stringify({client_ids:ids})}),refresh:async result=>{const blocked=(result.blocked||[]).map(item=>{const row=d.items.find(client=>client.id===item.id);return `${row?.legal_name||item.id}: ${(item.reasons||[]).join(', ')}`});toast({type:blocked.length?'error':'success',message:`${result.archived_ids?.length||0} cliente(s) arquivado(s).${blocked.length?' Bloqueados: '+blocked.join(' | '):''}`});await show('clients')},notify:toast})};
}
async function mobilityPage(filters={},lease=null){
  const [data,initialFleets]=await Promise.all([
    api('/mobility'+buildMobilityQuery(filters)),
    filters.client_id?api('/fleets?client_id='+encodeURIComponent(filters.client_id)+'&limit=100'):Promise.resolve({items:[]})
  ]);
  if(!content(renderMobilityPage(data,{fleets:initialFleets.items||[],filters}),lease))return;
  pageReload=()=>mobilityPage(filters);

  const filterForm=document.querySelector('#mobilityFilter');
  document.querySelector('#mobilityClear').onclick=()=>mobilityPage({});
  document.querySelectorAll('[data-mobility-tab]').forEach(button=>button.onclick=()=>{
    document.querySelectorAll('[data-mobility-tab]').forEach(item=>item.classList.toggle('active',item===button));
    document.querySelectorAll('[data-mobility-panel]').forEach(panel=>panel.hidden=panel.dataset.mobilityPanel!==button.dataset.mobilityTab);
  });

  const loadFleets=async(selectEl,clientId,selected='')=>{
    if(!clientId){selectEl.innerHTML='<option value="">Selecione o cliente primeiro</option>';selectEl.disabled=true;return []}
    const result=await api('/fleets?client_id='+encodeURIComponent(clientId)+'&limit=100');
    const rows=result.items||[];
    const groupName={CAR:'Carros',TRUCK:'Caminhões',BOAT:'Embarcações',AIRCRAFT:'Aeronaves',OTHER:'Outros',MIXED:'Misto'};
    selectEl.innerHTML='<option value="">— Particular (sem frota) —</option>'+rows.map(row=>`<option value="${esc(row.id)}" data-group="${esc(row.vehicle_group||'MIXED')}" ${row.id===selected?'selected':''}>${esc(row.name)} · ${esc(groupName[row.vehicle_group||'MIXED'])}</option>`).join('');
    selectEl.disabled=false;
    return rows;
  };

  const filterFleet=filterForm.querySelector('[name=fleet_id]');
  let filterClientName=filters.client_name||'';
  const filterCompany=filterForm.querySelector('[name=company_id]');
  const loadFilterCompanies=async(clientId,selected='')=>{if(!filterCompany)return;if(!clientId){filterCompany.innerHTML='<option value="">— selecione o cliente —</option>';filterCompany.disabled=true;return}const result=await api('/clients/'+encodeURIComponent(clientId)+'/companies');filterCompany.innerHTML='<option value="">Todas</option>'+(result.items||[]).map(row=>`<option value="${esc(row.id)}" ${row.id===selected?'selected':''}>${esc(row.trade_name||row.legal_name)}</option>`).join('');filterCompany.disabled=false};
  loadFilterCompanies(filters.client_id||'',filters.company_id||'').catch(()=>{});
  bindEntityAutocomplete(filterForm,{search:searchClientEntities,onSelection:client=>{filterClientName=client?.display_name||'';loadFleets(filterFleet,client?.id||'').catch(error=>toast({type:'error',message:error.message}));loadFilterCompanies(client?.id||'').catch(error=>toast({type:'error',message:error.message}))}});
  filterForm.onsubmit=async event=>{event.preventDefault();const payload=formData(event.target);if(filterClientName)payload.client_name=filterClientName;await mobilityPage(payload)};

  const openVehicleDrawer=async(prefill={})=>{
    const template=document.querySelector('#vehicleFormTemplate');
    const drawer=openDrawer({title:'Novo veículo',subtitle:prefill.fleet_id?'Adicionar à frota':'Veículo particular ou de frota',content:template.innerHTML,actions:'<button type="button" class="ui-btn ui-btn-secondary" data-close-overlay>Cancelar</button><button type="submit" form="vehicleForm" class="ui-btn ui-btn-primary">Salvar</button>'});
    drawer.querySelectorAll('[data-close-overlay]').forEach(button=>button.onclick=()=>closeOverlay());
    const form=drawer.querySelector('#vehicleForm');
    const fleetSelect=form.querySelector('[name=fleet_id]');
    if(prefill.client_id){form.querySelector('[name=client_id]').value=prefill.client_id;form.querySelector('[data-entity-query]').value=prefill.client_name||prefill.client_id}
    bindEntityAutocomplete(form,{search:searchClientEntities,onSelection:client=>loadFleets(fleetSelect,client?.id||'').catch(error=>toast({type:'error',message:error.message}))});
    await loadFleets(fleetSelect,prefill.client_id||'',prefill.fleet_id||'');
    const typeSelect=form.querySelector('[name=type]');
    const customField=form.querySelector('.custom-type-field');
    typeSelect.onchange=()=>{customField.hidden=typeSelect.value!=='__custom__';customField.querySelector('input').required=!customField.hidden};
    bindActionForm(form,{key:'vehicle-create',action:async()=>{const payload=buildVehiclePayload(formData(form));await api('/vehicles',{method:'POST',body:JSON.stringify(payload)});closeOverlay()},refresh:()=>mobilityPage(filters),successMessage:'Veículo cadastrado.',notify:toast});
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
    const companySelect=form.querySelector('[name=client_company_id]');
    const submitButton=drawer.querySelector('[form=fleetForm]');
    bindEntityAutocomplete(form,{search:searchClientEntities,onSelection:client=>loadCompanies(client?.id||'',companySelect,submitButton).catch(error=>toast({type:'error',message:error.message}))});
    loadCompanies('',companySelect,submitButton);
    bindActionForm(form,{key:'fleet-create',action:async()=>{await api('/fleets',{method:'POST',body:JSON.stringify(formData(form))});closeOverlay()},refresh:()=>mobilityPage(filters),successMessage:'Frota cadastrada.',notify:toast});
  };

  const openTransfer=async vehicle=>{
    const cases=await api(`/vehicles/${encodeURIComponent(vehicle.id)}/transfer-cases`);
    const drawer=openDrawer({title:'Transferência de propriedade',subtitle:[vehicle.code,vehicle.plate].filter(Boolean).join(' · ')||'Veículo',content:renderTransferCaseForm(vehicle,{cases:cases.items||[]})});
    const form=drawer.querySelector('#transferCaseForm');
    if(form){
      const fleetSelect=form.querySelector('[name=fleet_id]');
      bindEntityAutocomplete(form,{search:searchClientEntities,onSelection:client=>loadFleets(fleetSelect,client?.id||'').catch(error=>toast({type:'error',message:error.message}))});
      bindActionForm(form,{key:`transfer-create:${vehicle.id}`,action:async()=>{const payload=formData(form);payload.expected_revision=Number(payload.expected_revision);if(!payload.fleet_id)delete payload.fleet_id;if(!payload.effective_from)delete payload.effective_from;await api(`/vehicles/${vehicle.id}/transfer-cases`,{method:'POST',body:JSON.stringify(payload)});closeOverlay()},refresh:()=>mobilityPage(filters),successMessage:'Transferência criada como pendente.',notify:toast});
    }
    const complete=drawer.querySelector('[data-complete-transfer]');
    bindActionButton(complete,{key:`transfer-complete:${complete?.dataset.completeTransfer||''}`,action:async()=>{await api(`/vehicle-transfer-cases/${complete.dataset.completeTransfer}/complete`,{method:'POST',body:'{}'});closeOverlay()},refresh:()=>mobilityPage(filters),successMessage:'Transferência concluída.',notify:toast});
    const cancel=drawer.querySelector('[data-cancel-transfer]');
    bindActionButton(cancel,{key:`transfer-cancel:${cancel?.dataset.cancelTransfer||''}`,action:async()=>{await api(`/vehicle-transfer-cases/${cancel.dataset.cancelTransfer}/cancel`,{method:'POST',body:'{}'});closeOverlay()},refresh:()=>mobilityPage(filters),successMessage:'Transferência cancelada.',notify:toast});
  };

  const openFleetProfile=async fleetId=>{
    const profile=await api('/fleets/'+encodeURIComponent(fleetId)+'/profile');
    const companies=await api('/clients/'+encodeURIComponent(profile.fleet.client_id)+'/companies');
    const drawer=openDrawer({title:'Ficha da Frota',subtitle:[profile.fleet.name,profile.fleet.code].filter(Boolean).join(' · '),content:renderFleetProfile(profile,{companies:companies.items||[]})});
    drawer.querySelector('.ui-drawer').classList.add('r2-profile-wide');
    const edit=drawer.querySelector('#fleetEditForm');
    bindActionForm(edit,{key:`fleet-edit:${fleetId}`,action:async()=>{const payload=formData(edit);payload.expected_revision=Number(payload.expected_revision);await api('/fleets/'+encodeURIComponent(fleetId),{method:'PATCH',body:JSON.stringify(payload)});closeOverlay()},refresh:()=>mobilityPage(filters),successMessage:'Frota atualizada.',notify:toast});
    const addVehicle=drawer.querySelector('[data-add-vehicle-fleet]');
    if(addVehicle)addVehicle.onclick=()=>{closeOverlay();openVehicleDrawer({client_id:profile.fleet.client_id,client_name:profile.fleet.client_name||profile.company?.legal_name,fleet_id:fleetId})};
    drawer.querySelectorAll('[data-open-vehicle-transfer]').forEach(button=>button.onclick=()=>{const vehicle=profile.vehicles.find(row=>row.id===button.dataset.openVehicleTransfer);if(vehicle)openTransfer(vehicle)});
  };

  document.querySelector('#newVehicle').onclick=()=>openVehicleDrawer();
  document.querySelector('#newFleet').onclick=openFleetDrawer;
  document.querySelectorAll('[data-open-fleet]').forEach(button=>button.onclick=()=>openFleetProfile(button.dataset.openFleet).catch(error=>toast({type:'error',message:error.message})));
  document.querySelectorAll('[data-open-vehicle-transfer]').forEach(button=>button.onclick=()=>{const vehicle=(data.particulars||[]).find(row=>row.id===button.dataset.openVehicleTransfer);if(vehicle)openTransfer(vehicle).catch(error=>toast({type:'error',message:error.message}))});
}

async function catalogPage(lease=null){
  const d=await api('/catalog');
  if(!content(renderCatalogPage(d),lease))return;
  const form=document.querySelector('#catalogForm');
  bindCatalogForm(form,{bindMoney:bindMoneyInputs});
  bindActionForm(form,{key:'catalog-create',action:()=>api('/catalog',{method:'POST',body:JSON.stringify(catalogPayload(form))}),refresh:()=>show('catalog'),successMessage:'Produto cadastrado.',notify:toast});
  const byId=id=>d.items.find(item=>item.id===id);
  document.querySelectorAll('[data-catalog-edit]').forEach(button=>button.onclick=()=>{
    const row=byId(button.dataset.catalogEdit); if(!row)return;
    const drawer=openDrawer({title:'Editar plano/produto',subtitle:row.code,content:renderCatalogEditForm(row)});
    const edit=drawer.querySelector('#catalogEditForm');bindCatalogForm(edit,{bindMoney:bindMoneyInputs});
    bindActionForm(edit,{key:`catalog-edit:${row.id}`,action:async()=>{const payload=catalogPayload(edit);payload.expected_revision=row.revision;await api('/catalog/'+encodeURIComponent(row.id),{method:'PATCH',body:JSON.stringify(payload)});closeOverlay()},refresh:()=>show('catalog'),successMessage:'Produto atualizado.',notify:toast});
  });
  document.querySelectorAll('[data-catalog-delete]').forEach(button=>{const used=Number(button.dataset.used||0);bindActionButton(button,{key:'catalog-delete:'+button.dataset.catalogDelete,confirm:used?'Este item já foi usado em assinaturas ou compras. Ele será arquivado (some das novas vendas, o histórico continua). Continuar?':'Excluir este item definitivamente?',action:()=>api('/catalog/'+encodeURIComponent(button.dataset.catalogDelete),{method:'DELETE'}),refresh:()=>show('catalog'),successMessage:used?'Item arquivado.':'Item excluído.',notify:toast})});
  document.querySelectorAll('[data-catalog-restore]').forEach(button=>{const row=byId(button.dataset.catalogRestore);bindActionButton(button,{key:'catalog-restore:'+row.id,action:()=>api('/catalog/'+encodeURIComponent(row.id),{method:'PATCH',body:JSON.stringify({active:true,expected_revision:row.revision})}),refresh:()=>show('catalog'),successMessage:'Item reativado.',notify:toast})});
}
async function commercialPage(lease=null){
  const data=await api('/commercial');
  let purchaseClient=null;
  const legacyTab=current==='purchases'?'purchases':current==='credits'?'credits':'subscriptions';
  const deepLink=location.hash.match(/^#commercial\/(subscriptions|purchases|credits)(?:\/([^/]+))?$/);
  let active=deepLink?.[1]||legacyTab;let focusCode=deepLink?.[2]?decodeURIComponent(deepLink[2]):'';
  current='commercial'; document.querySelectorAll('[data-page]').forEach(b=>b.classList.toggle('active',b.dataset.page==='commercial'));
  const draw=()=>{
    if(!content(renderCommercialPage({...data,purchase_client:purchaseClient},active),lease))return;
    if(focusCode){const row=[...document.querySelectorAll('[data-row-code]')].find(item=>item.dataset.rowCode===focusCode);if(row){row.classList.add('commercial-focus');row.scrollIntoView({block:'center'})}focusCode=''}
    document.querySelectorAll('[data-commercial-tab]').forEach(button=>button.onclick=()=>{active=button.dataset.commercialTab;history.replaceState(null,'','#commercial/'+active);draw()});
    // AJ-10 — one "Ações" menu per subscription.
    document.querySelectorAll('[data-sub-actions]').forEach(button=>button.onclick=()=>{
      const sub=(data.subscriptions||[]).find(row=>row.id===button.dataset.subActions);if(!sub)return;
      const reload=()=>show('commercial');
      const setStatus=(status,message,confirmText)=>runDomAction({key:'sub-status:'+sub.id,scope:button,confirm:confirmText,action:()=>api('/subscriptions/'+encodeURIComponent(sub.id)+'/status',{method:'PATCH',body:JSON.stringify({lifecycle_status:status,expected_revision:sub.revision,...(status==='CANCELLED'?{end_on:localToday()}:{})})}),refresh:reload,successMessage:message,notify:toast});
      const handlers={
        pay:()=>openPaymentDialog({api,search:searchClientEntities,client:{id:sub.client_id,display_name:sub.client_name},subscriptionId:sub.id,notify:toast,onSuccess:reload}),
        amend:()=>{const drawer=openDrawer({title:'Ajustar assinatura',subtitle:[sub.code,sub.client_name].filter(Boolean).join(' · '),content:renderSubscriptionAmendForm(sub,{catalog:data.catalog_mensal_all||data.catalog_mensal||[],vehicles:data.vehicles||[],fleets:data.fleets||[]})});
          const form=drawer.querySelector('#subscriptionAmendForm');bindMoneyInputs(form);
          form.querySelectorAll('[name=catalog_id]').forEach(select=>select.onchange=()=>{const price=Number(select.selectedOptions[0]?.dataset.price||0);const unit=select.closest('.amend-item').querySelector('[name=unit_price]');if(unit)unit.value=formatBRL(price)});
          bindActionForm(form,{key:'sub-amend:'+sub.id,action:async()=>{const rows=[...form.querySelectorAll('.amend-item')].map(row=>({catalog_id:row.querySelector('[name=catalog_id]').value,quantity:Number(row.querySelector('[name=quantity]').value||1),unit_price:row.querySelector('[name=unit_price]').value}));
            const fd=new FormData(form);await api('/subscriptions/'+encodeURIComponent(sub.id),{method:'PATCH',body:JSON.stringify({expected_revision:sub.revision,items:rows,due_day:Number(fd.get('due_day')||sub.due_day),target_vehicle_ids:fd.getAll('target_vehicle'),target_fleet_ids:fd.getAll('target_fleet')})});closeOverlay()},refresh:reload,successMessage:'Assinatura ajustada.',notify:toast});},
        purchase:()=>{purchaseClient={id:sub.client_id,display_name:sub.client_name};active='purchases';history.replaceState(null,'','#commercial/purchases');draw()},
        profile:()=>openClientProfile(sub.client_id,{focus:'commercial'}).catch(error=>toast({type:'error',message:error.message})),
        pause:()=>setStatus('PAUSED','Assinatura pausada.'),
        resume:()=>setStatus('ACTIVE','Assinatura reativada.'),
        cancel:()=>setStatus('CANCELLED','Assinatura cancelada.','Cancelar esta assinatura? Ela deixa de gerar mensalidades. O histórico é mantido.'),
      };
      openActionMenu(button,subscriptionMenuItems(sub).map(item=>({...item,onClick:handlers[item.key]})));
    });
    const newSubscription=document.querySelector('[data-new-subscription]');if(newSubscription)newSubscription.onclick=()=>openSubscriptionWorkflow({context:'COMMERCIAL',catalog:data.catalog_mensal||[],vehicles:data.vehicles||[],fleets:data.fleets||[]},{onSuccess:()=>show('commercial')});
    const purchase=document.querySelector('#commercialPurchaseForm'); if(purchase){
      const vehicleSelect=purchase.querySelector('[name=vehicle_id]');
      const filterVehicles=client=>{const clientId=client?.id||'';vehicleSelect.disabled=!clientId;for(const option of [...vehicleSelect.options].slice(1))option.hidden=option.dataset.client!==clientId;if(vehicleSelect.selectedOptions[0]?.hidden)vehicleSelect.value=''};
      bindEntityAutocomplete(purchase,{search:searchClientEntities,onSelection:filterVehicles});
      filterVehicles(purchaseClient);
      bindActionForm(purchase,{key:'purchase-create',action:async()=>{const p=formData(purchase);const item={catalog_id:p.catalog_id,vehicle_id:p.vehicle_id||null,quantity:Number(p.quantity||1)};await api('/direct-sales',{method:'POST',body:JSON.stringify({client_id:p.client_id,sold_on:p.sold_on||localToday(),items:[item]})})},refresh:()=>show('commercial'),successMessage:'Compra direta registrada.',notify:toast});
    }
    const coverage=document.querySelector('#coverageForm');bindActionForm(coverage,{key:'coverage-create',action:async()=>{const p=formData(coverage);p.cycles=Number(p.cycles||1);if(!p.start_on)delete p.start_on;if(!p.value||p.value==='R$ 0,00')delete p.value;await api('/commercial/coverage',{method:'POST',body:JSON.stringify(p)})},refresh:()=>show('commercial'),successMessage:'Tempo ativo registrado.',notify:toast});
  }; draw();
}
async function financePage(lease=null){
  let data=await api('/finance');
  // AJ-13: recurring expenses due up to this month are issued once, without triggering a reload loop.
  if(Number(data.recurring_pending||0)>0){try{await apiClient.request('/expenses/recurring/run',{method:'POST',body:'{}'});data=await api('/finance')}catch{}}
  const legacyTab=current==='expenses'?'expenses':current==='fiscal'?'fiscal':'payments';
  let active=(location.hash.match(/^#finance\/(payments|expenses|fiscal)$/)?.[1])||legacyTab;
  current='finance';document.querySelectorAll('[data-page]').forEach(b=>b.classList.toggle('active',b.dataset.page==='finance'));
  const reload=()=>show('finance');
  const draw=()=>{
    if(!content(renderFinancePage(data,active),lease))return;
    document.querySelectorAll('[data-finance-tab]').forEach(button=>button.onclick=()=>{active=button.dataset.financeTab;history.replaceState(null,'','#finance/'+active);draw()});
    const openPay=document.querySelector('[data-open-payment]');if(openPay)openPay.onclick=()=>openPaymentDialog({api,search:searchClientEntities,notify:toast,onSuccess:reload});
    document.querySelectorAll('[data-reverse-payment]').forEach(button=>bindActionButton(button,{key:'payment-reverse:'+button.dataset.reversePayment,confirm:'Estornar este recebimento? As mensalidades cobertas voltam a ficar em aberto.',action:()=>api('/payments/'+encodeURIComponent(button.dataset.reversePayment)+'/reverse',{method:'POST',body:'{}'}),refresh:reload,successMessage:'Recebimento estornado.',notify:toast}));
    const payment=document.querySelector('#financePaymentForm');if(payment){
      const chargeSelect=payment.querySelector('[name=charge_id]');
      bindEntityAutocomplete(payment,{search:searchClientEntities,onSelection:client=>{const clientId=client?.id||'';chargeSelect.disabled=!clientId;for(const option of [...chargeSelect.options].slice(1))option.hidden=option.dataset.client!==clientId;if(chargeSelect.selectedOptions[0]?.hidden)chargeSelect.value=''}});
      bindActionForm(payment,{key:'payment-create',action:async()=>{const p=formData(payment);p.create_credit=p.create_credit==='true';p.allocations=[];if(p.charge_id&&p.allocation_amount&&p.allocation_amount!=='R$ 0,00')p.allocations.push({charge_id:p.charge_id,amount:p.allocation_amount});delete p.charge_id;delete p.allocation_amount;if(!p.paid_on)delete p.paid_on;await api('/payments',{method:'POST',body:JSON.stringify(p)})},refresh:reload,successMessage:'Recebimento registrado.',notify:toast});
    }
    const expense=document.querySelector('#financeExpenseForm');
    if(expense){bindMoneyInputs(expense);bindActionForm(expense,{key:'expense-create',action:async()=>{const p=formData(expense);p.paid=p.paid==='true';if(!p.supplier)delete p.supplier;await api('/expenses',{method:'POST',body:JSON.stringify(p)})},refresh:()=>{active='expenses';return reload()},successMessage:'Despesa registrada.',notify:toast});}
    const byId=id=>(data.expenses||[]).find(row=>row.id===id);
    document.querySelectorAll('[data-expense-pay]').forEach(button=>bindActionButton(button,{key:'expense-pay:'+button.dataset.expensePay,action:()=>api('/expenses/'+encodeURIComponent(button.dataset.expensePay)+'/pay',{method:'POST',body:'{}'}),refresh:reload,successMessage:'Despesa paga hoje.',notify:toast}));
    document.querySelectorAll('[data-expense-stop]').forEach(button=>bindActionButton(button,{key:'expense-stop:'+button.dataset.expenseStop,confirm:'Parar a repetição desta despesa? As já lançadas continuam.',action:()=>api('/expenses/'+encodeURIComponent(button.dataset.expenseStop)+'/stop-repeat',{method:'POST',body:'{}'}),refresh:reload,successMessage:'Repetição encerrada.',notify:toast}));
    document.querySelectorAll('[data-expense-delete]').forEach(button=>bindActionButton(button,{key:'expense-delete:'+button.dataset.expenseDelete,confirm:'Excluir esta despesa? Esta ação não pode ser desfeita.',action:()=>api('/expenses/'+encodeURIComponent(button.dataset.expenseDelete),{method:'DELETE'}),refresh:reload,successMessage:'Despesa excluída.',notify:toast}));
    document.querySelectorAll('[data-expense-sell]').forEach(button=>button.onclick=()=>{
      const row=byId(button.dataset.expenseSell);if(!row)return;
      const drawer=openDrawer({title:'Vender ao cliente',subtitle:'Transforma este custo em uma Compra Direta.',content:renderSellExpenseForm(row)});
      const form=drawer.querySelector('#sellExpenseForm');bindMoneyInputs(form);bindEntityAutocomplete(form,{search:searchClientEntities});
      bindActionForm(form,{key:'expense-sell:'+row.id,action:async()=>{const p=formData(form);await api('/expenses/'+encodeURIComponent(row.id)+'/convert-sale',{method:'POST',body:JSON.stringify({client_id:p.client_id,price:p.price})});closeOverlay()},refresh:reload,successMessage:'Compra direta criada.',notify:toast});
    });
    const fiscal=document.querySelector('#financeFiscalForm');bindActionForm(fiscal,{key:'fiscal-create',action:async()=>{const p=formData(fiscal);if(!p.amount)delete p.amount;if(!p.due_on)delete p.due_on;if(!p.external_ref)delete p.external_ref;await api('/fiscal',{method:'POST',body:JSON.stringify(p)})},refresh:reload,successMessage:'Obrigação fiscal registrada.',notify:toast});
  };draw();
}
async function filesPage(lease=null){
  const [media,attachments]=await Promise.all([api('/media'),api('/attachments')]);
  if(!content(renderFilesPage({media:media.items||[],attachments:attachments.items||[]}),lease))return;
  // R14 — choose the record once (client search + record list); every upload/link below uses it.
  const target=document.querySelector('#filesTargetForm');const targetSelect=target.querySelector('[name=target]');const targetLabel=document.querySelector('[data-files-target-label]');
  target.onsubmit=event=>event.preventDefault();
  const applyTarget=()=>{const [type,id]=String(targetSelect.value||'').split(':');document.querySelectorAll('#mediaForm,#attachmentUploadForm,#attachmentLinkForm').forEach(form=>{form.querySelector('[name=entity_type]').value=type||'';form.querySelector('[name=entity_id]').value=id||''});
    const ok=Boolean(id);const mediaOk=ok&&type!=='subscription';
    document.querySelector('#mediaForm input[type=file]').disabled=!mediaOk;document.querySelector('[data-needs-target="media"]').classList.toggle('is-disabled',!mediaOk);
    document.querySelectorAll('#attachmentUploadForm input[type=file],#attachmentLinkForm button').forEach(el=>el.disabled=!ok);document.querySelector('#attachmentUploadForm [data-needs-target]').classList.toggle('is-disabled',!ok);
    targetLabel.textContent=ok?'Selecionado: '+targetSelect.selectedOptions[0].textContent+(mediaOk?'':' (assinatura aceita apenas anexos)'):'Nenhum registro selecionado.'};
  targetSelect.onchange=applyTarget;
  bindEntityAutocomplete(target,{search:searchClientEntities,onSelection:async client=>{if(!client?.id){targetSelect.innerHTML='<option value="">Selecione o cliente primeiro</option>';targetSelect.disabled=true;applyTarget();return}
    const profile=await api('/clients/'+encodeURIComponent(client.id)+'/profile');targetSelect.innerHTML='<option value="">Selecione o registro</option>'+entityChoices(profile).map(row=>`<option value="${esc(row.value)}">${esc(row.label)}</option>`).join('');targetSelect.disabled=false;targetSelect.value=`client:${client.id}`;applyTarget()}});
  const mediaForm=document.querySelector('#mediaForm');
  enableAutoUpload(mediaForm);
  bindActionForm(mediaForm,{key:'media-upload',action:async()=>{const fd=new FormData(mediaForm),type=fd.get('entity_type'),id=fd.get('entity_id'),file=fd.get('file'),retain=fd.get('retain_original')==='true';const body=new FormData();body.append('file',file);await apiForm(`/media/${encodeURIComponent(type)}/${encodeURIComponent(id)}?retain_original=${retain}`,body)},refresh:filesPage,successMessage:'Foto adicionada.',notify:toast});
  const upload=document.querySelector('#attachmentUploadForm');
  enableAutoUpload(upload);
  bindActionForm(upload,{key:'attachment-upload',action:async()=>{const fd=new FormData(upload),type=fd.get('entity_type'),id=fd.get('entity_id'),file=fd.get('file');const body=new FormData();body.append('file',file);await apiForm(`/attachments/${encodeURIComponent(type)}/${encodeURIComponent(id)}`,body)},refresh:filesPage,successMessage:'Arquivo anexado.',notify:toast});
  const link=document.querySelector('#attachmentLinkForm');
  bindActionForm(link,{key:'attachment-link',action:()=>api('/attachments/link',{method:'POST',body:JSON.stringify(formData(link))}),refresh:filesPage,successMessage:'Link salvo.',notify:toast});
  document.querySelectorAll('[data-remove-media]').forEach(button=>button.onclick=()=>{if(!confirm('Remover esta foto?'))return;return runDomAction({key:`media-remove:${button.dataset.removeMedia}`,scope:button,action:()=>api('/media/'+encodeURIComponent(button.dataset.removeMedia),{method:'DELETE'}),refresh:filesPage,successMessage:'Foto removida.',notify:toast})});
}

function reportsPage(lease=null){const names=['clients','vehicles','charges','payments','credits','expenses'];if(!content(`<h2>Relatórios</h2><div class="panel"><p>CSV e XLSX com neutralização de formula injection.</p><div class="report-grid">${names.map(n=>`<div class="card"><strong>${esc(n)}</strong><div class="actions"><button data-report="${n}" data-ext="csv">CSV</button><button data-report="${n}" data-ext="xlsx" class="secondary">XLSX</button></div></div>`).join('')}</div></div>`,lease))return;document.querySelectorAll('[data-report]').forEach(b=>b.onclick=()=>downloadReport(b.dataset.report,b.dataset.ext))}
async function downloadReport(name,ext){const r=await fetch(`/api/v1/reports/${name}.${ext}`);if(!r.ok)throw new Error('Falha no relatório');const a=document.createElement('a');a.href=URL.createObjectURL(await r.blob());a.download=`${name}.${ext}`;a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000)}
function organizeSystemPage(runtime){
  const root=document.querySelector('#content');if(!root||root.querySelector('.system-tabs'))return;
  const tabs=document.createElement('div');tabs.className='system-tabs';tabs.innerHTML='<button type="button" class="active" data-system-tab="admin">Administração</button><button type="button" data-system-tab="development">Desenvolvimento</button>';
  const admin=document.createElement('section');admin.className='system-panel';admin.dataset.systemPanel='admin';
  const development=document.createElement('section');development.className='system-panel';development.dataset.systemPanel='development';development.hidden=true;
  const advanced=new Set(['Recovery / transferência','Recuperação / transferência','Estações','Auditoria','Integrações futuras','Integrações planejadas','Laboratório Test','Laboratório de testes']);
  [...root.querySelectorAll(':scope > .panel')].forEach(panel=>(advanced.has(panel.querySelector('h3')?.textContent?.trim())?development:admin).appendChild(panel));
  const runtimePanel=document.createElement('div');runtimePanel.className='panel';runtimePanel.innerHTML=`<h3>Runtime e atualização</h3><dl class="runtime-grid"><dt>Versão</dt><dd>${esc(runtime?.version||'—')}</dd><dt>Schema</dt><dd>${esc(runtime?.schema_version||'—')}</dd><dt>Ambiente</dt><dd>${esc(runtime?.environment||'—')}</dd><dt>APP_ROOT</dt><dd>${esc(runtime?.app_root||'—')}</dd><dt>DATA_ROOT</dt><dd>${esc(runtime?.data_root||'—')}</dd><dt>BACKUP_ROOT</dt><dd>${esc(runtime?.backup_root||'—')}</dd><dt>Última atualização</dt><dd>${esc(runtime?.update?.state||'Nenhuma registrada')}</dd></dl><p class="muted">Pacotes .usup são verificados por assinatura e checksum pelo atualizador externo antes da troca transacional.</p>`;development.prepend(runtimePanel);
  const header=root.querySelector('.ui-page-header');header?.after(tabs,admin,development);
  tabs.querySelectorAll('[data-system-tab]').forEach(button=>button.onclick=()=>{tabs.querySelectorAll('button').forEach(item=>item.classList.toggle('active',item===button));admin.hidden=button.dataset.systemTab!=='admin';development.hidden=button.dataset.systemTab!=='development'});
}
function bindSystemActions(){
  const settingsForm=document.querySelector('#settingsForm');if(!settingsForm)return;
  api('/system/runtime').then(organizeSystemPage).catch(()=>organizeSystemPage(null));
  bindActionForm(settingsForm,{key:'settings-save',action:()=>api('/settings',{method:'PUT',body:JSON.stringify(formData(settingsForm))}),refresh:()=>show('system'),successMessage:'Configurações salvas.',notify:toast});
  const brandForm=document.querySelector('#brandForm');bindActionForm(brandForm,{key:'branding-upload',action:async()=>{const fd=new FormData(brandForm),kind=fd.get('kind'),file=fd.get('file');const body=new FormData();body.append('file',file);await apiForm('/branding/'+kind,body)},refresh:()=>location.reload(),successMessage:'Identidade visual atualizada.',notify:toast});
  bindActionButton(document.querySelector('#backup'),{key:'backup-create',action:()=>api('/backups',{method:'POST',body:'{}'}),refresh:()=>show('system'),successMessage:'Backup criado.',notify:toast});
  const restoreForm=document.querySelector('#restoreForm');restoreForm.onsubmit=event=>{event.preventDefault();if(!confirm('Restaurar este backup e substituir o ambiente atual?'))return;return runDomAction({key:'backup-restore',scope:restoreForm,action:async()=>{const body=new FormData();body.append('file',new FormData(restoreForm).get('file'));await apiForm('/backups/restore',body)},refresh:()=>show('dashboard'),successMessage:'Backup restaurado.',notify:toast})};
  const recoveryForm=document.querySelector('#recoveryForm');bindActionForm(recoveryForm,{key:'recovery-export',action:async()=>{const payload=formData(recoveryForm);payload.transfer=payload.transfer==='true';return {result:await api('/recovery/export',{method:'POST',body:JSON.stringify(payload)}),transfer:payload.transfer}},refresh:({result,transfer})=>{document.querySelector('#recoveryOut').innerHTML=msg(`Recovery criado: ${result.name}`,'notice')+`<a class="download-link" href="/api/v1/recovery/${encodeURIComponent(result.name)}">Baixar ${esc(result.name)}</a>`;if(transfer)me.station={...(me.station||{}),is_writer:0}},successMessage:'Recovery criado.',notify:toast});
  bindActionForm(document.querySelector('#claimForm'),{key:'station-claim',action:()=>api('/stations/claim',{method:'POST',body:JSON.stringify({confirm:'ASSUMIR ESCRITA'})}),refresh:()=>location.reload(),successMessage:'Escrita assumida.',notify:toast});
  const emergencyForm=document.querySelector('#emergencyForm');emergencyForm.onsubmit=event=>{event.preventDefault();if(!confirm('Use apenas se a estação escritora anterior foi retirada de operação. Continuar?'))return;const reason=formData(emergencyForm).reason;return runDomAction({key:'station-emergency',scope:emergencyForm,action:()=>api('/stations/emergency-takeover',{method:'POST',body:JSON.stringify({confirm:'ASSUMIR EMERGENCIA',reason})}),refresh:()=>location.reload(),successMessage:'Escrita de emergência assumida.',notify:toast})};
  const resetForm=document.querySelector('#resetForm');bindActionForm(resetForm,{key:'admin-reset',confirm:'Redefinir esta posição administrativa? O acesso atual dela deixará de funcionar.',action:async()=>{const payload=formData(resetForm);return api('/auth/reset-admin/'+payload.slot,{method:'POST',body:JSON.stringify({reason:payload.reason})})},refresh:result=>{document.querySelector('#adminOut').innerHTML=msg('Ticket: '+result.ticket,'notice')},successMessage:'Administrador preparado para recadastro.',notify:toast});
  const passwordForm=document.querySelector('#pwdForm');bindActionForm(passwordForm,{key:'password-change',action:()=>api('/auth/change-password',{method:'POST',body:JSON.stringify(formData(passwordForm))}),refresh:()=>{me=null;return boot()},successMessage:'Senha alterada.',notify:toast});
  bindActionButton(document.querySelector('#resetTest'),{key:'sandbox-reset',confirm:'Apagar TODOS os dados do ambiente de TESTE? O ambiente Real não é afetado.',action:()=>api('/sandbox/reset',{method:'POST',body:JSON.stringify({confirm:'LIMPAR TESTES'})}),refresh:()=>show('dashboard'),successMessage:'Ambiente de testes limpo.',notify:toast});
}
async function systemPage(){const [st,sets,baks,ints,stations,audit]=await Promise.all([api('/auth/setup-status'),api('/settings'),api('/backups'),api('/integrations'),api('/stations'),api('/audit?limit=100')]);content(`<h2>Sistema</h2><div class="panel"><h3>Administradores</h3>${dt(st.admins,'adminsDT')}<form id="resetForm"><div class="row">${field('Slot para reset','slot','number')}${field('Motivo','reason')}</div><div class="actions"><button class="danger">Resetar slot</button></div></form><form id="pwdForm"><div class="row">${field('Senha atual','current_password','password')}${field('Nova senha','new_password','password')}</div><div class="actions"><button>Trocar minha senha</button></div></form><div id="adminOut"></div></div><div class="panel"><h3>Branding e configuração</h3><form id="settingsForm"><div class="row">${field('Empresa','company_display_name','text',sets.company_display_name||'')}${field('Telefone','contact_phone','text',sets.contact_phone||'')}${field('E-mail','contact_email','email',sets.contact_email||'')}${field('Endereço público','address_display','text',sets.address_display||'')}${field('Cor primária','theme_primary','color',sets.theme_primary||'#155eef')}${field('Cor destaque','theme_accent','color',sets.theme_accent||'#0f9f6e')}${field('Retenção backups','backup_retention','number',sets.backup_retention||'14')}</div><div class="actions"><button>Salvar configurações</button></div></form><form id="brandForm"><div class="row"><div class="field"><label>Tipo</label><select name="kind"><option>logo</option><option>favicon</option><option>icon</option></select></div><div class="field"><label>Imagem</label><input name="file" type="file" accept="image/*"></div></div><div class="actions"><button>Enviar branding</button></div></form></div><div class="panel"><h3>Backup</h3><div class="actions"><button id="backup">Criar backup cifrado</button></div><form id="restoreForm"><div class="field"><label>Restaurar .usbk</label><input name="file" type="file" accept=".usbk" required></div><div class="actions"><button class="danger">Restaurar backup</button></div></form>${dt(baks.items,'backupsDT')}</div><div class="panel"><h3>Recovery / transferência</h3><form id="recoveryForm"><div class="row">${field('Passphrase (12+ caracteres)','passphrase','password')}<label><input name="transfer" type="checkbox" value="true"> Preparar transferência e desarmar esta escritora</label></div><div class="actions"><button>Gerar .usre</button></div></form><div id="recoveryOut"></div></div><div class="panel"><h3>Estações</h3>${dt(stations.items,'stationsDT')}<form id="claimForm"><div class="actions"><button>ASSUMIR ESCRITA pendente</button></div></form><form id="emergencyForm"><div class="row">${field('Motivo da emergência','reason')}</div><div class="actions"><button class="danger">ASSUMIR EMERGÊNCIA</button></div></form></div><div class="panel"><h3>Auditoria</h3><div class="actions"><button id="verifyAudit">Verificar cadeia</button></div><div id="auditOut"></div>${dt(audit.items,'auditDT')}</div><div class="panel"><h3>Integrações futuras</h3><pre>${esc(JSON.stringify(ints,null,2))}</pre></div>${me.environment==='test'?`<div class="panel"><h3>Laboratório Test</h3><button id="resetTest" class="danger">LIMPAR TESTES</button></div>`:''}<div class="panel"><h3>Sessão</h3><div class="actions"><button id="logout" class="secondary">Sair</button><button id="shutdown" class="danger">Encerrar sistema</button></div></div>`);document.querySelector('#settingsForm').onsubmit=async e=>{e.preventDefault();await api('/settings',{method:'PUT',body:JSON.stringify(formData(e.target))});show('system')};document.querySelector('#brandForm').onsubmit=async e=>{e.preventDefault();const fd=new FormData(e.target),kind=fd.get('kind'),file=fd.get('file');const body=new FormData();body.append('file',file);await apiForm('/branding/'+kind,body);location.reload()};document.querySelector('#backup').onclick=async()=>{await api('/backups',{method:'POST',body:'{}'});show('system')};document.querySelector('#restoreForm').onsubmit=async e=>{e.preventDefault();if(!confirm('Restaurar este backup e substituir o ambiente atual?'))return;const fd=new FormData();fd.append('file',new FormData(e.target).get('file'));await apiForm('/backups/restore',fd);show('dashboard')};document.querySelector('#recoveryForm').onsubmit=async e=>{e.preventDefault();const p=formData(e.target);p.transfer=p.transfer==='true';const r=await api('/recovery/export',{method:'POST',body:JSON.stringify(p)});document.querySelector('#recoveryOut').innerHTML=msg(`Recovery criado: ${r.name}`,'notice')+`<a class="download-link" href="/api/v1/recovery/${encodeURIComponent(r.name)}">Baixar ${esc(r.name)}</a>`;if(p.transfer){me.station={...(me.station||{}),is_writer:0};toast({message:'Estação atual alterada para somente leitura.'})}};document.querySelector('#claimForm').onsubmit=async e=>{e.preventDefault();await api('/stations/claim',{method:'POST',body:JSON.stringify({confirm:'ASSUMIR ESCRITA'})});location.reload()};document.querySelector('#emergencyForm').onsubmit=async e=>{e.preventDefault();const reason=formData(e.target).reason;if(!confirm('Use apenas se a estação escritora anterior foi retirada de operação. Continuar?'))return;await api('/stations/emergency-takeover',{method:'POST',body:JSON.stringify({confirm:'ASSUMIR EMERGENCIA',reason})});location.reload()};document.querySelector('#verifyAudit').onclick=async()=>{const r=await api('/audit/verify');document.querySelector('#auditOut').innerHTML=msg(r.ok?`Cadeia íntegra (${r.events} eventos)`:`Cadeia quebrada no evento ${r.broken_at_id}`,r.ok?'success':'error')};document.querySelector('#resetForm').onsubmit=async e=>{e.preventDefault();const p=formData(e.target);try{const r=await api('/auth/reset-admin/'+p.slot,{method:'POST',body:JSON.stringify({reason:p.reason})});document.querySelector('#adminOut').innerHTML=msg('Ticket: '+r.ticket,'notice')}catch(err){document.querySelector('#adminOut').innerHTML=msg(err.message,'error')}};document.querySelector('#pwdForm').onsubmit=async e=>{e.preventDefault();await api('/auth/change-password',{method:'POST',body:JSON.stringify(formData(e.target))});me=null;boot()};if(document.querySelector('#resetTest'))document.querySelector('#resetTest').onclick=async()=>{await api('/sandbox/reset',{method:'POST',body:JSON.stringify({confirm:'LIMPAR TESTES'})});show('dashboard')};document.querySelector('#logout').onclick=async()=>{await api('/auth/logout',{method:'POST',body:'{}'});me=null;boot()};document.querySelector('#shutdown').onclick=async()=>{await api('/system/shutdown',{method:'POST',body:'{}'});content('<div class="success">Sistema encerrado com segurança.</div>')}}
document.addEventListener?.('click',e=>{if(e.target?.id==='shutdown'){e.preventDefault();e.stopImmediatePropagation();requestSystemShutdown().catch(err=>alert(err.message))}},true);
const nativeAlert=globalThis.alert?.bind(globalThis);if(nativeAlert)globalThis.alert=message=>nativeAlert(messagePtBR(message));observePtBR(document.body);localizeDom(document.body);loadIconSet().then(boot).catch(e=>app.innerHTML=`<section class="auth"><div class="error">${esc(messagePtBR(e.message))}</div></section>`);
