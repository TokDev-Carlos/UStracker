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
import { installInteractions, navigationFinished, navigationStarted } from './ui/interactions.js';
installInteractions();
import { buildClientCreatePayload, clientTableDefinition, renderClientEditor } from './pages/clients.js';
import { buildMobilityQuery, buildVehiclePayload, renderFleetProfile, renderMobilityPage, renderMoveVehicleForm } from './pages/mobility.js';
import { bindCatalogForm, catalogPayload, renderCatalogEditForm, renderCatalogPage } from './pages/catalog.js';
import { renderCommercialPage, renderSubscriptionAmendForm, subscriptionMenuItems } from './pages/commercial.js';
import { openActionMenu } from './ui/action-menu.js';
import { renderFinancePage, renderSellExpenseForm } from './pages/finance.js';
import { localToday, openPaymentDialog } from './ui/payment-dialog.js';
import { renderOverviewDrilldown, renderOverviewPage } from './pages/dashboard.js';
import { entityChoices, renderFilesPage } from './pages/files.js';
import { confirmDialog, openDialog, openPlateOwnerDialog } from './ui/dialog.js';
import { allowedPages, applyPermissions, can, filterMenu, isAdmin, setAccess, watchPermissions } from './ui/permissions.js';
import { bindUsersTab, renderUsersTab } from './pages/users.js';
import { renderCloudPanel, renderPlacaPanel, renderCloudRestoreForm, renderPointsTable, renderRecoveryKit, renderTrashPanel } from './pages/cloud.js';

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
const api=(path,opt)=>path==='/auth/logout'?session.logout():(opt?.method&&opt.method!=='GET'&&syncWatchSave(),apiClient.request(path,opt)).then(result=>{if(path==='/auth/login')session.authenticate(result);scheduleProjectionRefresh(path,opt?.method);return result});
const getCsrf=()=>apiClient.acquireCsrf();
const apiForm=(path,form,method='POST')=>apiClient.requestForm(path,form,method).then(result=>{scheduleProjectionRefresh(path,method);return result});
const searchClientEntities=async(query,limit=30)=>(await api('/entities/clients?q='+encodeURIComponent(query)+'&limit='+Math.min(Number(limit)||30,30))).items||[];
const tableStore=new Map();
const esc=s=>String(s??'').replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
const sessionProfileLabel=user=>user?.role||(user?.slot?'Administrador':'Usuário');
async function requestSystemShutdown(){const bridge=window.chrome?.webview;toast({message:'Enviando as últimas alterações para a nuvem e encerrando…'});try{await getCsrf().catch(()=>{});await api('/system/shutdown',{method:'POST',body:'{}'})}catch{}if(bridge){bridge.postMessage('system-shutdown');return}toast({type:'success',message:'Sistema encerrado com segurança.'})}
// S-02/S-03 — other Servidores' changes appear by themselves; the chip tells when saving waits for another Servidor.
let syncVersion=null,syncTimer=null,syncFast=0;
function syncChip(state){let chip=document.querySelector('#syncChip');const actions=document.querySelector('.topbar-actions');if(!actions)return;if(!chip){chip=document.createElement('span');chip.id='syncChip';chip.className='sync-chip';chip.setAttribute('role','status');actions.prepend(chip)}
  const text=state?.waiting_for?`Aguardando ${state.waiting_for} terminar de salvar…`:state?.script_outdated?'Atualize o script da nuvem (veja Docs › Guia do dono)':state?.offline?'Sem conexão com a nuvem: salvando neste computador':'';chip.textContent=text;chip.hidden=!text;chip.classList.toggle('is-offline',!!state?.offline&&!state?.waiting_for)}
async function syncTick(){clearTimeout(syncTimer);if(!me||me.environment!=='production'){syncTimer=setTimeout(syncTick,15000);return}
  try{const state=await apiClient.request('/sync/state');syncChip(state);
    if(syncVersion!==null&&state.data_version!==syncVersion){const busy=document.querySelector('#uiOverlay,#uiDialog,#uiActionMenu')||['INPUT','TEXTAREA','SELECT'].includes(document.activeElement?.tagName);if(!busy&&typeof pageReload==='function'){pageReload();toast({type:'info',message:'Dados atualizados por outro Servidor.'})}else{syncTimer=setTimeout(syncTick,5000);return}}
    syncVersion=state.data_version}catch{}
  syncTimer=setTimeout(syncTick,syncFast>Date.now()?2000:15000)}
function syncWatchSave(){syncFast=Date.now()+60000;clearTimeout(syncTimer);syncTimer=setTimeout(syncTick,1500)}
// AJ-06 — one delegated handler for every subscription count (pages and drawers).
document.addEventListener('click',event=>{
  const button=event.target.closest?.('[data-subs-vehicle],[data-subs-fleet]');
  if(button){event.preventDefault();const query=button.dataset.subsVehicle?'vehicle_id='+encodeURIComponent(button.dataset.subsVehicle):'fleet_id='+encodeURIComponent(button.dataset.subsFleet);
    openSubscriptionPopover(button,()=>api('/mobility/subscriptions?'+query),{onCommercial:(tab,code)=>{closeOverlay();history.replaceState(null,'','#commercial/'+tab+(code?'/'+encodeURIComponent(code):''));show('commercial')}});return}
  if(!event.target.closest?.('#subsPopover'))closeSubscriptionPopover();
});
// R14/V-05 — one visible action: choosing the file uploads it; "×" removes at once (it goes to the Lixeira, with "Desfazer").
async function refreshAfterMedia(){const profile=document.querySelector('.cp');if(profile){const clientId=profile.dataset.clientId;const tab=profile.dataset.cpActive;closeOverlay();if(clientId)await openClientProfile(clientId,{tab})}else if(typeof pageReload==='function')await pageReload()}
const refreshAfterChange=refreshAfterMedia;
function undoToast(message,trashId){toast({type:'success',message,action:trashId?{label:'Desfazer',onClick:()=>api('/trash/'+encodeURIComponent(trashId)+'/restore',{method:'POST',body:'{}'}).then(()=>{toast({type:'success',message:'Desfeito.'});return refreshAfterChange()}).catch(error=>toast({type:'error',message:error.message}))}:null})}
document.addEventListener('change',event=>{
  const input=event.target;const kind=input?.dataset?.vehiclePhoto?'vehicle':input?.dataset?.fleetPhoto?'fleet':null;if(!kind||!input.files?.[0])return;
  const id=input.dataset.vehiclePhoto||input.dataset.fleetPhoto;const body=new FormData();body.append('file',input.files[0]);
  runDomAction({key:`${kind}-photo:${id}`,scope:input.closest('label')||input,action:()=>apiForm(`/media/${kind}/${encodeURIComponent(id)}`,body),refresh:refreshAfterMedia,successMessage:'Foto atualizada.',notify:toast}).finally(()=>{input.value=''});
});
document.addEventListener('click',event=>{
  const button=event.target.closest?.('[data-remove-photo],[data-remove-media]');if(!button)return;event.preventDefault();event.stopPropagation();
  const mid=button.dataset.removePhoto||button.dataset.removeMedia;
  runDomAction({key:`media-remove:${mid}`,scope:button,action:()=>api('/media/'+encodeURIComponent(mid),{method:'DELETE'}),refresh:async result=>{await refreshAfterMedia();undoToast('Foto removida (fica 14 dias na Lixeira).',result?.trash_id)},notify:toast});
});
// V-01 — delete a vehicle or a fleet from anywhere (tables, Ficha do Cliente, Ficha da Frota).
document.addEventListener('click',async event=>{
  const vehicleButton=event.target.closest?.('[data-delete-vehicle]');const fleetButton=event.target.closest?.('[data-delete-fleet]');
  if(!vehicleButton&&!fleetButton)return;event.preventDefault();event.stopPropagation();
  if(vehicleButton){
    const id=vehicleButton.dataset.deleteVehicle;const label=vehicleButton.dataset.label||'este veículo';
    if(!await confirmDialog(`Excluir ${label}? Ele vai para a Lixeira e pode ser restaurado em até 14 dias.`,{title:'Excluir veículo',okLabel:'Excluir',danger:true}))return;
    return runDomAction({key:`vehicle-delete:${id}`,scope:vehicleButton,action:()=>api('/vehicles/'+encodeURIComponent(id),{method:'DELETE'}),refresh:async result=>{await refreshAfterChange();undoToast('Veículo excluído.',result?.trash_id)},notify:toast});
  }
  const id=fleetButton.dataset.deleteFleet;const label=fleetButton.dataset.label||'esta frota';const count=Number(fleetButton.dataset.vehicles||0);
  const actions=[{label:'Cancelar',value:null}];
  if(count)actions.push({label:'Excluir só a frota',kind:'primary',value:'detach'},{label:`Excluir frota e ${count} veículo(s)`,kind:'danger',value:'with_vehicles'});
  else actions.push({label:'Excluir frota',kind:'danger',value:'detach'});
  const mode=await openDialog({title:'Excluir frota',body:`<p>Excluir <strong>${esc(label)}</strong>? Ela vai para a Lixeira e pode ser restaurada em até 14 dias.</p>${count?`<p class="muted">A frota tem ${count} veículo(s). “Excluir só a frota” mantém os veículos como <b>Particular</b> do mesmo cliente.</p>`:''}`,actions});
  if(!mode)return;
  return runDomAction({key:`fleet-delete:${id}`,scope:fleetButton,action:()=>api('/fleets/'+encodeURIComponent(id)+'?mode='+mode,{method:'DELETE'}),refresh:async result=>{if(!document.querySelector('.cp'))closeOverlay();await refreshAfterChange();undoToast('Frota excluída.',result?.trash_id)},notify:toast});
});
// V-02 — plate already registered: warn while typing (on leaving the field) and on save.
function showPlateOwner(vehicle){return openPlateOwnerDialog(vehicle,{onOpenClient:id=>{closeOverlay();openClientProfile(id,{focus:'mobility'}).catch(error=>toast({type:'error',message:error.message}))}})}
function bindPlateCheck(form){
  const input=form?.querySelector('[name=plate]');if(!input)return;
  let box=form.querySelector('[data-plate-warning]');
  if(!box){box=document.createElement('p');box.dataset.plateWarning='';box.className='plate-warning';box.hidden=true;(input.closest('.field')||input.parentElement).append(box)}
  input.addEventListener('blur',async()=>{const value=input.value.trim();if(value.replace(/[^a-z0-9]/gi,'').length<3){box.hidden=true;return}
    try{const result=await api('/vehicles/plate-check?plate='+encodeURIComponent(value));if(!result.exists){box.hidden=true;input.removeAttribute('aria-invalid');return}
      box.hidden=false;input.setAttribute('aria-invalid','true');box.innerHTML=`Placa já cadastrada · ${esc(result.vehicle.client_name||'outro cliente')} <button type="button" class="link-btn">Ver cadastro</button>`;box.querySelector('button').onclick=()=>showPlateOwner(result.vehicle)}catch{}});
}
async function createVehicle(payload){try{return await api('/vehicles',{method:'POST',body:JSON.stringify(payload)})}catch(error){if(error?.code==='PLATE_EXISTS'&&error.data?.vehicle)showPlateOwner(error.data.vehicle);throw error}}
document.addEventListener('keydown',event=>{if(event.key==='Escape'&&document.querySelector('#subsPopover')){event.stopPropagation();closeSubscriptionPopover()}},true);
function formData(form){const o={};for(const [k,v] of new FormData(form).entries())o[k]=v;return o}
function enableAutoUpload(form){const input=form?.querySelector('input[type="file"]');if(input)input.onchange=()=>{if(input.files?.length)form.requestSubmit()};return form}
function msg(text,type='success'){return `<div class="${type}">${esc(text)}</div>`}
const PAGE_SUBTITLES={'Visão Geral':'Resultado, previsão do mês e situação dos clientes','Comercial':'Assinaturas, compras diretas e tempo ativo','Financeiro':'Recebimentos, despesas e obrigações fiscais','Fotos/Arquivos':'Fotos e anexos vinculados a clientes, veículos, frotas e assinaturas','Relatórios':'Exportação de dados em CSV e Excel','Sistema':'Administração, backup e diagnóstico','Planos/Produtos':'Planos mensais e produtos avulsos'};
function content(html,lease=null){if((lease!==null&&lease!==navigationSequence)||(String(html).startsWith('<h2>Sistema')&&systemNavigationLease!==navigationSequence))return false;const normalized=html.replace(/^<h2>([^<]+)<\/h2>/,(_,title)=>pageHeader(title,PAGE_SUBTITLES[title]||'Gestão administrativa')).replaceAll('>Publicar<','>Exibir no catálogo público<');const target=document.querySelector('#content');target.innerHTML=normalized;hydrateTables();bindMoneyInputs(target);localizeDom(target);queueMicrotask(bindSystemActions);return true}
function applyBrand(p){const b=p?.brand||{};if(b.theme_primary)document.documentElement.style.setProperty('--primary',b.theme_primary);if(b.theme_accent)document.documentElement.style.setProperty('--accent',b.theme_accent);document.title=(b.company_display_name||'UStracker')+' — UStracker';const fav=b.assets?.favicon;if(fav){let l=document.querySelector('#dynamicFavicon');if(!l){l=document.createElement('link');l.id='dynamicFavicon';l.rel='icon';document.head.appendChild(l)}l.href=fav+'?v='+Date.now()}}
const DIAGNOSTIC_TABLES=new Set(['auditDT','stationsDT','adminsDT','backupsDT']);
function dt(items,id){const rows=items||[];const technical=k=>!DIAGNOSTIC_TABLES.has(id)&&(k==='id'||k.endsWith('_id'));const keys=rows.length?Object.keys(rows[0]).filter(k=>!['notes','address','before_json','after_json'].includes(k)&&!technical(k)).sort((a,b)=>(b==='code')-(a==='code')).slice(0,12):[];const isDateKey=key=>key.endsWith('_on')||key.endsWith('_at')||['created_at','updated_at','paid_on','due_on','start_on','end_on','sold_on','installed_on'].includes(key);const columns=keys.map(key=>({key,label:key==='code'?'Código':labelPtBR(key),format:key==='code'?value=>value?`<span class="ui-code">${esc(value)}</span>`:'—':key.endsWith('_cents')?value=>formatBRL(Number(value||0)):(key==='size'||key==='size_bytes')?value=>{const n=Number(value||0);return n>=1048576?`${(n/1048576).toFixed(1).replace('.',',')} MB`:`${Math.max(1,Math.round(n/1024))} KB`}:isDateKey(key)?value=>esc(formatDateBR(value,key.endsWith('_at'))):value=>esc(valuePtBR(value))}));tableStore.set(id,createTableController({columns,rows}));return `<div id="${id}" class="data-table"></div>`}
function hydrateTables(){for(const id of tableStore.keys()){if(document.querySelector('#'+CSS.escape(id)))renderDT(id)}}
function renderDT(id){const box=document.querySelector('#'+CSS.escape(id));const controller=tableStore.get(id);if(box&&controller)mountTableController(box,controller)}
function select(items,value='id',label='legal_name',blank=false){return `${blank?'<option value="">—</option>':''}${(items||[]).map(x=>`<option value="${esc(x[value])}">${esc(x[label]??x[value])}</option>`).join('')}`}
function field(label,name,type='text',value=''){const credentialLabels={password:'Senha ou PIN (mínimo 4 caracteres)',current_password:'Senha ou PIN atual',new_password:'Nova senha ou PIN (mínimo 4 caracteres)'};const displayLabel=type==='password'&&credentialLabels[name]?credentialLabels[name]:label;const hint=HELP[current]?.fields?.[name];return `<div class="field"><label>${displayLabel}${hint?` <button type="button" class="ui-help-trigger" title="${esc(hint)}" aria-label="Ajuda sobre ${esc(displayLabel)}">?</button>`:''}</label><input name="${name}" type="${type}" value="${esc(value)}" autocomplete="${name==='password'?'current-password':'off'}">${hint?`<span class="ui-field-hint">${esc(hint)}</span>`:''}</div>`}
function moneyField(label,name,valueCents=null,required=false){return renderMoneyInput({label,name,valueCents,required})}
function openSubscriptionWorkflow(model,{onSuccess,onCancel}={}){
  const drawer=openDrawer({title:'Nova assinatura (plano mensal)',subtitle:'Escolha o plano e os veículos que ele cobre',content:renderSubscriptionWorkflow(model)});
  if(onCancel)drawer.querySelectorAll('[data-close-overlay]').forEach(button=>button.onclick=async()=>{closeOverlay();await onCancel()});
  bindSubscriptionWorkflow(drawer,{model,searchClients:searchClientEntities,onSubmit:async payload=>{
    await api('/subscriptions',{method:'POST',body:JSON.stringify(payload)});
    closeOverlay();toast({message:'Assinatura criada.'});await onSuccess?.();
  },onError:error=>toast({type:'error',message:error.message})});
  return drawer;
}
async function boot(){document.querySelector('.test-banner')?.remove();const state=await session.bootstrap();const pub=state.publicData,st=state.setupStatus;applyBrand(pub);if(state.state==='setup')return setupScreen();if(state.state==='login')return loginScreen(st,pub);renderShell();await show(allowedPages(nav.map(([key])=>key))[0]||'dashboard')}
// 2.2.0 — computador novo: só o Adm Global ativa (traz os dados da empresa ou cria o Administrador da empresa).
async function setupScreen(){let info={};try{info=await apiClient.request('/cloud/bootstrap')}catch{}
  if(info.activation)return activationScreen();
  setupFirstScreen(info)}
function activationScreen(note=''){app.innerHTML=`<section class="auth"><h1>Ativar este computador</h1><p>Este computador ainda não foi ativado. A <b>primeira entrada</b> em qualquer computador é feita pelo <b>Adm Global</b> (o dono do sistema).</p><p class="muted">Se a empresa já usa o UStracker, os dados chegam da nuvem e este computador vira mais um Servidor. Se é a primeira instalação, você entra direto no sistema e cria o Administrador local em <b>Sistema</b>. Depois disso, cada pessoa entra com o próprio usuário.</p>${note?msg(note,'notice'):''}<form id="activate"><div class="row">${field('Acesso do Adm Global','name')}${field('PIN','password','password')}</div><div class="actions"><button class="ui-btn ui-btn-primary">Continuar</button></div></form><div id="activateOut"></div></section>`;
  document.querySelector('#activate').onsubmit=async e=>{e.preventDefault();const creds=formData(e.target);const out=document.querySelector('#activateOut');try{await getCsrf();const r=await api('/auth/activate',{method:'POST',body:JSON.stringify(creds)});if(r.challenge)return activationChallenge(creds,r.challenge);await activationDone(r)}catch(err){out.innerHTML=activationError(err)}}}
function activationError(err){if(err?.status===422&&err?.data?.error==='INVALID')return loginError(err);if(err?.status===429)return loginError(err);return msg(messagePtBR(err?.message||'Não foi possível ativar agora.'),'error')}
function activationChallenge(creds,challenge){app.innerHTML=`<section class="auth"><h1>Verificação de segurança</h1><p>Para continuar, responda:</p><form id="challenge"><div class="field"><label>${esc(challenge.question)}</label><input name="answer" type="password" autocomplete="off" required></div><div class="actions"><button class="ui-btn ui-btn-primary">Ativar</button><button type="button" class="ui-btn ui-btn-subtle" id="challengeBack">Voltar</button></div></form><div id="challengeOut"></div></section>`;
  document.querySelector('#challengeBack').onclick=()=>activationScreen();
  document.querySelector('#challenge').onsubmit=async e=>{e.preventDefault();const out=document.querySelector('#challengeOut');const button=e.target.querySelector('button');button.disabled=true;out.innerHTML=msg('Conferindo o acesso e buscando os dados da empresa… pode levar alguns minutos.','notice');try{await getCsrf();const full={...creds,answer:formData(e.target).answer,question_id:challenge.id};const r=await api('/auth/activate',{method:'POST',body:JSON.stringify(full)});await activationDone(r,full)}catch(err){out.innerHTML=activationError(err);e.target.reset()}finally{button.disabled=false}}}
async function activationDone(r,full=null){
  if(r.needs_decision)return oldCloudScreen(r,full);
  if(r.needs_admin_login){me=null;return boot()}
  await enterSystem(r);
  if(r.new_company){if(r.old_cloud_saved)toast({type:'info',message:'A nuvem tinha dados antigos não validados pelo Adm Global. Uma cópia foi guardada em Documentos › UStracker_backup_old › '+String(r.old_cloud_saved).split(/[\\/]/).pop()+' e a empresa recomeçou limpa.'});if(r.cloud?.error)toast({type:'error',message:'Computador ativado, mas o envio para a nuvem falhou agora; o sistema tenta de novo sozinho.'});else toast({type:'success',message:'Computador ativado. Crie o Administrador local em Sistema.'});return show('system')}
  toast({type:'success',message:'Pronto! Este computador foi ativado e já tem os dados da empresa.'})}
// 2.3.1 — the company cloud has data the Adm Global never validated: never restart on its own.
function oldCloudScreen(r,full){const c=r.cloud_data||{},n=c.counts||{};const when=c.saved_at?new Date(c.saved_at).toLocaleString('pt-BR'):'—';
  app.innerHTML=`<section class="auth"><h1>A nuvem da empresa já tem dados</h1><p>Os dados foram salvos por uma versão antiga e ainda <b>não foram validados pelo Adm Global</b>. Nada foi apagado.</p>
  <div class="panel"><p>Clientes: <b>${esc(n.clients??0)}</b> · Veículos: <b>${esc(n.vehicles??0)}</b> · Assinaturas: <b>${esc(n.subscriptions??0)}</b> · Recebimentos: <b>${esc(n.payments??0)}</b></p><p class="muted">Último salvamento: ${esc(when)}</p></div>
  <h3>Manter os dados (recomendado)</h3><p>Entre <b>uma vez</b> com o usuário e a senha do Administrador da empresa. Isso valida os dados; depois o Adm Global entra direto em qualquer computador.</p>
  <div class="actions"><button class="ui-btn ui-btn-primary" id="oldCloudLogin">Entrar com o Administrador da empresa</button></div>
  <h3>Recomeçar a empresa do zero</h3><p class="muted">Use só se esses dados não servem mais. Uma cópia vai antes para Documentos › UStracker_backup_old; a nuvem recomeça vazia. Bloqueado se outro computador salvou nas últimas 24 horas.</p>
  <form id="oldCloudRestart"><div class="row">${field('Digite RECOMEÇAR para confirmar','confirm')}</div><div class="actions"><button class="danger">Recomeçar a empresa</button></div></form><div id="oldCloudOut"></div></section>`;
  document.querySelector('#oldCloudLogin').onclick=()=>{me=null;boot()};
  document.querySelector('#oldCloudRestart').onsubmit=async e=>{e.preventDefault();const out=document.querySelector('#oldCloudOut');const word=formData(e.target).confirm;
    if(word!=='RECOMEÇAR'){out.innerHTML=msg('Digite RECOMEÇAR (em maiúsculas) para confirmar.','error');return}
    if(!full){out.innerHTML=msg('Entre de novo com o Adm Global para recomeçar.','error');return}
    const button=e.target.querySelector('button');button.disabled=true;out.innerHTML=msg('Guardando a cópia e recomeçando a empresa…','notice');
    try{await getCsrf();const res=await api('/auth/activate',{method:'POST',body:JSON.stringify({...full,restart:'RECOMEÇAR'})});await activationDone(res)}
    catch(err){out.innerHTML=err?.data?.error==='RECENT'?msg('Bloqueado: outro computador salvou na nuvem nas últimas 24 horas. Use o Administrador da empresa.','error'):msg(messagePtBR(err?.message||'Não foi possível recomeçar.'),'error')}
    finally{button.disabled=false}}}
function setupFirstScreen(info={}){app.innerHTML=`<section class="auth"><h1>UStracker — Configuração inicial</h1><p>Crie o Administrador 1 (o acesso principal do sistema).</p>${info.available?`<p class="muted">${info.reachable===false?'Não foi possível falar com a nuvem agora; os dados serão enviados quando a conexão voltar.':'Os dados serão guardados automaticamente na nuvem da empresa.'}</p>`:''}<form id="setup"><div class="row">${field('Nome','name')}${field('Senha (mínimo 4 caracteres)','password','password')}</div><div class="actions"><button>Iniciar configuração</button></div></form><div id="setupOut"></div></section>`;document.querySelector('#setup').onsubmit=async e=>{e.preventDefault();try{await getCsrf();const r=await api('/auth/bootstrap',{method:'POST',body:JSON.stringify(formData(e.target))});await showRecoveryKey(r.recovery_key);boot()}catch(err){document.querySelector('#setupOut').innerHTML=msg(err.message,'error')}}}
function enrollmentScreen(tickets){app.innerHTML=`<section class="auth"><h1>Administrador 1 criado</h1><p>Pronto para usar. <b>Opcional:</b> cadastre agora mais dois administradores de reserva (os códigos valem 15 minutos), ou clique em “Ir para login”. Usuários do dia a dia (Operador, Gerente) são criados depois em Sistema › Usuários.</p>${tickets.map((t,i)=>`<form class="enroll" data-ticket="${esc(t)}"><h3>Administrador ${i+2}</h3><div class="ticket">${esc(t)}</div><div class="row">${field('Nome','name')}${field('Senha','password','password')}</div><div class="actions"><button>Registrar Admin ${i+2}</button></div><div class="out"></div></form>`).join('')}<button id="goLogin" class="secondary">Ir para login</button></section>`;document.querySelectorAll('.enroll').forEach(f=>f.onsubmit=async e=>{e.preventDefault();try{await getCsrf();const p=formData(f);p.ticket=f.dataset.ticket;await api('/auth/enroll',{method:'POST',body:JSON.stringify(p)});f.querySelector('.out').innerHTML=msg('Administrador registrado.')}catch(err){f.querySelector('.out').innerHTML=msg(err.message,'error')}});document.querySelector('#goLogin').onclick=()=>boot()}
// C-05 — Administrator only (Sistema › Nuvem › Avançado): replace this computer's data with a cloud's.
function bindCloudRestoreEntry(){
  document.querySelectorAll('[data-cloud-restore-admin]').forEach(button=>button.onclick=()=>{
    const drawer=openDrawer({title:'Restaurar da nuvem',subtitle:'Traz de volta todos os dados guardados no seu Google Drive.',content:renderCloudRestoreForm()});
    const form=drawer.querySelector('#cloudRestoreForm');const out=form.querySelector('[data-cloud-restore-out]');
    bindActionForm(form,{key:'cloud-restore',action:async()=>{await getCsrf();const p=formData(form);out.innerHTML=msg('Baixando da nuvem… pode levar alguns minutos.','notice');
      const r=await api('/cloud/restore',{method:'POST',body:JSON.stringify({url:p.url,secret:p.secret,confirm:'RESTAURAR DA NUVEM'})});
      out.innerHTML=msg(`Pronto! Ponto de ${formatDateBR(r.created_at,true)} recuperado (${r.files_downloaded} fotos/anexos). Entre com seu usuário e senha.`,'success');
      setTimeout(()=>{closeOverlay();me=null;boot()},2500)},notify:toast});
  });
}
async function enterSystem(r){csrf=r.csrf;me=r;renderShell();await show(allowedPages(nav.map(([key])=>key))[0]||'dashboard');if(r.backup_warning)toast({type:'error',message:messagePtBR('Backup automático: '+r.backup_warning)});if(r.recovery_key)await showRecoveryKey(r.recovery_key)}
function loginError(err){if(err?.status===409||err?.status===503)return msg(messagePtBR(err?.message||''),'error');if(/locked/i.test(err?.message||'')&&err?.status!==429)return msg(err.message,'error');if(err?.status===429)return msg(`Acesso bloqueado por segurança. Tente de novo em ${err.data?.retry_minutes||30} minutos.`,'error');return msg('Usuário ou senha inválidos.','error')+(err?.data?.hint?`<p class="muted login-hint">${esc(err.data.hint)}</p>`:'')}
function loginScreen(st,pub){app.innerHTML=renderLoginScreen(st,pub);
  document.querySelector('[data-recover-open]')?.addEventListener('click',recoverScreen);
  document.querySelector('#login').onsubmit=async e=>{e.preventDefault();const creds=formData(e.target);try{await getCsrf();const r=await api('/auth/login',{method:'POST',body:JSON.stringify(creds)});if(r.challenge)return challengeScreen(creds,r.challenge,st,pub);await enterSystem(r)}catch(err){document.querySelector('#loginOut').innerHTML=loginError(err)}}}
// G-04 — segunda etapa do Adm Global: pergunta (a resposta é o mesmo PIN). Erros mostram pistas.
function challengeScreen(creds,challenge,st,pub){app.innerHTML=`<section class="auth"><h1>Verificação de segurança</h1><p>Para continuar, responda:</p><form id="challenge"><div class="field"><label>${esc(challenge.question)}</label><input name="answer" type="password" autocomplete="off" required></div><div class="actions"><button class="ui-btn ui-btn-primary">Continuar</button><button type="button" class="ui-btn ui-btn-subtle" id="challengeBack">Voltar</button></div></form><div id="challengeOut"></div></section>`;
  document.querySelector('#challengeBack').onclick=()=>loginScreen(st,pub);
  document.querySelector('#challenge').onsubmit=async e=>{e.preventDefault();try{await getCsrf();const r=await api('/auth/login',{method:'POST',body:JSON.stringify({...creds,answer:formData(e.target).answer,question_id:challenge.id})});await enterSystem(r)}catch(err){document.querySelector('#challengeOut').innerHTML=loginError(err);e.target.reset()}}}
// G-04 — Adm Local esqueceu a senha: Chave de Recuperação.
function recoverScreen(){app.innerHTML=`<section class="auth"><h1>Recuperar acesso do Administrador</h1><p>Digite a <b>Chave de Recuperação</b> (guardada quando o sistema foi configurado) e escolha uma senha nova.</p><form id="recover"><div class="row">${field('Chave de Recuperação','code')}${field('Nova senha (mínimo 4)','new_password','password')}</div><div class="actions"><button class="ui-btn ui-btn-primary">Redefinir senha</button><button type="button" class="ui-btn ui-btn-subtle" id="recoverBack">Voltar</button></div></form><div id="recoverOut"></div></section>`;
  document.querySelector('#recoverBack').onclick=()=>boot();
  document.querySelector('#recover').onsubmit=async e=>{e.preventDefault();try{await getCsrf();await api('/auth/recover',{method:'POST',body:JSON.stringify(formData(e.target))});document.querySelector('#recoverOut').innerHTML=msg('Senha redefinida. Entre com a senha nova.','success');setTimeout(boot,1800)}catch(err){document.querySelector('#recoverOut').innerHTML=msg(err?.status===429||/locked/.test(err?.message||'')?err.message:'Chave de Recuperação inválida.','error')}}}
const nav=[['dashboard','Visão geral'],['clients','Clientes'],['mobility','Frotas/Veículos'],['catalog','Planos/Produtos'],['commercial','Comercial'],['finance','Financeiro'],['files','Fotos/Arquivos'],['reports','Relatórios'],['system','Sistema']];
// G-05 — atualização pela nuvem: faixa (normal, instala ao fechar) ou bloqueio (crítica).
let updateTimer=null;
async function updateTick(){clearTimeout(updateTimer);updateTimer=setTimeout(updateTick,10*60*1000);if(!me)return;let st;try{st=await apiClient.request('/update/status')}catch{return}renderUpdate(st)}
function renderUpdate(st){document.querySelector('.update-banner')?.remove();document.querySelector('.update-block')?.remove();if(!st?.available)return;
  const notes=st.notes?`<span class="muted">${esc(st.notes)}</span>`:'';
  const button=st.can_apply?'<button type="button" class="ui-btn ui-btn-primary" data-update-now>Atualizar agora</button>':'';
  if(st.level==='critical'){const block=document.createElement('div');block.className='update-block';block.innerHTML=`<section class="auth"><h1>Atualização obrigatória</h1><p>A versão <b>${esc(st.version)}</b> corrige um problema importante. É preciso atualizar para continuar usando o sistema.</p>${notes}<div class="actions">${button}</div><div data-update-out></div></section>`;document.body.append(block)}
  else{const bar=document.createElement('div');bar.className='update-banner';bar.setAttribute('role','status');bar.innerHTML=`<span>Versão <b>${esc(st.version)}</b> disponível — será instalada quando o sistema for fechado.</span>${button}`;document.body.append(bar)}
  document.querySelectorAll('[data-update-now]').forEach(b=>b.onclick=()=>applyUpdateNow(st))}
async function applyUpdateNow(st){if(!await confirmDialog(`Atualizar agora para a versão ${st.version}? O sistema fecha e reabre sozinho em alguns segundos.`,{title:'Atualizar agora',okLabel:'Atualizar'}))return;
  try{await api('/update/apply-now',{method:'POST',body:'{}'})}catch(err){toast({type:'error',message:err.message});return}
  document.querySelector('.update-banner')?.remove();document.querySelector('.update-block')?.remove();const wait=document.createElement('div');wait.className='update-block';wait.innerHTML='<section class="auth"><h1>Atualizando…</h1><p>Instalando a versão nova. O sistema reabre sozinho, não feche esta janela.</p></section>';document.body.append(wait);
  waitNewVersion(st.current||'',st.version)}
async function waitNewVersion(previous,target){const until=Date.now()+180000;let wasDown=false;while(Date.now()<until){await new Promise(r=>setTimeout(r,1500));try{const r=await fetch('/api/v1/health',{cache:'no-store'});if(!r.ok){wasDown=true;continue}const h=await r.json();if(h.version&&h.version!==previous){location.reload();return}if(wasDown){toast({type:'error',message:`A atualização não foi aplicada; o sistema continua na versão ${previous}.`});document.querySelector('.update-block')?.remove();return}}catch{wasDown=true}}
  document.querySelector('.update-block')?.remove();toast({type:'error',message:'O sistema demorou para voltar. Feche e abra o UStracker.'})}
function testBanner(){document.querySelector('.test-banner')?.remove();if(me?.environment!=='test')return;const bar=document.createElement('div');bar.className='test-banner';bar.setAttribute('role','status');bar.textContent='AMBIENTE DE TESTE — nada aqui vai para a nuvem';document.body.prepend(bar)}
function renderShell(){setAccess(me);watchPermissions();syncVersion=null;setTimeout(syncTick,3000);const pages=allowedPages(nav.map(([key])=>key));renderAppShell({me,nav:nav.filter(([key])=>pages.includes(key)).map(([key,label])=>key==='system'&&!isAdmin()?[key,'Lixeira']:[key,label]),onNavigate:show,onSearch:async query=>{const d=await api('/search?q='+encodeURIComponent(query));tableStore.clear();content(pageHeader('Pesquisa','Resultados da busca global')+dt(d.items,'searchTable'))},onHelp:()=>{const help=helpFor(current);openDrawer({title:help.title,subtitle:'Ajuda contextual',content:`<p>${esc(help.body)}</p>${HELP[current]?.fields?`<dl>${Object.entries(HELP[current].fields).map(([key,value])=>`<dt><strong>${esc(key.replaceAll('_',' '))}</strong></dt><dd>${esc(value)}</dd>`).join('')}</dl>`:''}`})},onUser:()=>{content(pageHeader('Minha conta','Sessão atual')+`<div class="panel"><strong>${esc(me.name)}</strong><p class="muted">Perfil: ${esc(sessionProfileLabel(me))}</p><p class="muted">Ambiente: ${esc(me.environment==='production'?'Real':'Teste')}</p></div><div class="panel"><h3>Trocar minha senha</h3><form id="myPasswordForm"><div class="row"><div class="field"><label>Senha atual</label><input type="password" name="current_password" required autocomplete="current-password"></div><div class="field"><label>Nova senha (mínimo 4)</label><input type="password" name="new_password" minlength="4" required autocomplete="new-password"></div></div><div class="actions"><button class="ui-btn ui-btn-primary">Trocar senha</button></div></form></div>`);const form=document.querySelector('#myPasswordForm');bindActionForm(form,{key:'my-password',action:()=>api('/auth/change-password',{method:'POST',body:JSON.stringify(formData(form))}),refresh:async()=>{toast({type:'success',message:'Senha trocada. Entre de novo com a nova senha.'});await boot()},notify:toast})},onLogout:async()=>{await session.logout();await boot()},onShutdown:requestSystemShutdown});testBanner();clearTimeout(updateTimer);updateTimer=setTimeout(updateTick,4000)}
function bindClientJourney(drawer,profile,clientId){
  const reopen=focus=>async()=>{closeOverlay();await openClientProfile(clientId,{focus})};
  bindClientProfileUi(drawer);
  drawer.querySelectorAll('[data-open-commercial]').forEach(button=>button.onclick=()=>{closeOverlay();history.replaceState(null,'','#commercial/'+button.dataset.openCommercial+(button.dataset.code?'/'+encodeURIComponent(button.dataset.code):''));show('commercial')});
  const vehicleForm=drawer.querySelector('#clientVehicleForm');
  if(vehicleForm){
    const typeSelect=vehicleForm.querySelector('[name=type]');const customField=vehicleForm.querySelector('.custom-type-field');
    typeSelect.onchange=()=>{customField.hidden=typeSelect.value!=='__custom__';customField.querySelector('input').required=!customField.hidden};
    bindPlateCheck(vehicleForm);
    bindActionForm(vehicleForm,{key:`client-vehicle:${clientId}`,action:async()=>{const payload=buildVehiclePayload({...formData(vehicleForm),client_id:clientId});await createVehicle(payload)},refresh:reopen('mobility'),successMessage:'Veículo cadastrado. Próximo passo: plano ou compra.',notify:toast});
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
// AJ-08 — one simple "Mover veículo" dialog used by Mobilidade, Ficha da Frota and Ficha do Cliente.
function openMoveVehicle(vehicle,{onDone=()=>{}}={}){
  const today=localToday();
  const drawer=openDrawer({title:'Mover veículo',subtitle:[vehicle.code,vehicle.plate].filter(Boolean).join(' · ')||'Veículo',content:renderMoveVehicleForm(vehicle,{today})});
  const form=drawer.querySelector('#moveVehicleForm');const fleetSelect=form.querySelector('[name=fleet_id]');const warning=form.querySelector('[data-move-warning]');
  const groupName={CAR:'Carros',TRUCK:'Caminhões',BOAT:'Embarcações',AIRCRAFT:'Aeronaves',OTHER:'Outros',MIXED:'Misto'};
  let clientId=vehicle.client_id||'';
  const category=vehicle.category||({Carro:'CAR','Caminhão':'TRUCK','Embarcação':'BOAT',Aeronave:'AIRCRAFT'}[vehicle.type]||'');
  const load=async id=>{
    clientId=id||'';warning.hidden=!clientId||clientId===vehicle.client_id;
    if(!clientId){fleetSelect.innerHTML='<option value="">Selecione o cliente</option>';fleetSelect.disabled=true;return}
    const rows=(await api('/fleets?client_id='+encodeURIComponent(clientId)+'&limit=100')).items||[];
    // Only fleets that accept this vehicle's category can be chosen (group "Misto" accepts all).
    const fits=row=>!category||(row.vehicle_group||'MIXED')==='MIXED'||row.vehicle_group===category;
    const others=rows.filter(row=>row.id!==vehicle.fleet_id);
    fleetSelect.innerHTML='<option value="">Particular (sem frota)</option>'+others.map(row=>`<option value="${esc(row.id)}"${fits(row)?'':' disabled'}>${esc(row.name)} · ${esc(groupName[row.vehicle_group||'MIXED'])}${fits(row)?'':' (não aceita este tipo)'}</option>`).join('');
    fleetSelect.disabled=false;
    const firstFit=others.findIndex(fits);
    if(!vehicle.fleet_id&&clientId===vehicle.client_id&&firstFit>=0)fleetSelect.selectedIndex=firstFit+1;
  };
  bindEntityAutocomplete(form,{search:searchClientEntities,onSelection:client=>load(client?.id||'').catch(error=>toast({type:'error',message:error.message}))});
  load(clientId).catch(error=>toast({type:'error',message:error.message}));
  bindActionForm(form,{key:`vehicle-move:${vehicle.id}`,action:async()=>{if(!clientId)throw new Error('Selecione o cliente de destino.');const result=await api('/vehicles/'+encodeURIComponent(vehicle.id)+'/move',{method:'POST',body:JSON.stringify({client_id:clientId,fleet_id:fleetSelect.value||'',effective_from:form.effective_from.value||today})});closeOverlay();if(result.removed_from_subscriptions?.length)toast({type:'info',message:'Removido das assinaturas: '+result.removed_from_subscriptions.join(', ')});return result},refresh:onDone,successMessage:'Veículo movido.',notify:toast});
  return drawer;
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
  bindActionForm(signatureForm,{key:`client-signature:${clientId}`,action:async()=>{const input=signatureForm.querySelector('[name=file]');const subscriptionId=signatureForm.querySelector('[name=subscription_id]')?.value;if(!subscriptionId||!input.files?.[0])throw new Error('Selecione a assinatura e o arquivo.');const body=new FormData();body.append('file',input.files[0]);await apiForm('/attachments/subscription/'+encodeURIComponent(subscriptionId),body)},refresh,successMessage:'Contrato assinado anexado.',notify:toast});
  bindClientJourney(drawer,profile,clientId,options);
  const newSubscription=drawer.querySelector('[data-client-new-subscription]');
  const journeySubscription=drawer.querySelector('[data-journey-subscription]');
  if(journeySubscription&&newSubscription)journeySubscription.onclick=()=>newSubscription.click();
  if(newSubscription)newSubscription.onclick=async()=>{const catalog=await api('/catalog');openSubscriptionWorkflow({context:'CLIENT_PROFILE',clientId,clients:[profile.client],catalog:catalog.items||[],vehicles:profile.vehicles||[],fleets:profile.fleets||[],vehicleMedia:profile.vehicle_media||{}},{onSuccess:()=>openClientProfile(clientId,{focus:'commercial'}),onCancel:()=>openClientProfile(clientId)})};
  drawer.querySelectorAll('.cp [data-open-vehicle-transfer]').forEach(button=>button.onclick=()=>{const vehicle=(profile.vehicles||[]).find(row=>row.id===button.dataset.openVehicleTransfer);if(!vehicle)return;const fleet=(profile.fleets||[]).find(row=>row.id===vehicle.fleet_id);const tab=drawer.querySelector('.cp')?.dataset.cpActive;openMoveVehicle({...vehicle,client_id:clientId,client_name:profile.client?.legal_name,fleet_name:fleet?.name},{onDone:()=>openClientProfile(clientId,{tab})})});
  // AJ-12 — pay from the profile (client and, from a row, the subscription come pre-selected).
  drawer.querySelectorAll('[data-client-payment]').forEach(button=>button.onclick=()=>{const tab=drawer.querySelector('.cp')?.dataset.cpActive;openPaymentDialog({api,search:searchClientEntities,client:{id:clientId,display_name:profile.client?.legal_name},subscriptionId:button.dataset.subscriptionId||'',notify:toast,onSuccess:()=>openClientProfile(clientId,{tab})})});
  return drawer;
}
async function show(page){if(page==='fleets'||page==='vehicles')page='mobility';{const base={subscriptions:'commercial',purchases:'commercial',charges:'commercial',credits:'commercial',payments:'finance',expenses:'finance',fiscal:'finance',media:'files'}[page]||page;const ok=allowedPages(nav.map(([key])=>key));if(!ok.includes(base)&&ok.length)page=ok[0]}const lease=++navigationSequence;navigationStarted();pageReload=()=>show(page);systemNavigationLease=page==='system'?lease:null;current=page;tableStore.clear();document.querySelectorAll('[data-page]').forEach(b=>b.classList.toggle('active',b.dataset.page===page));try{const fn={dashboard:()=>dashboardPage('',lease),clients:()=>clientsPage(lease),mobility:()=>mobilityPage({},lease),catalog:()=>catalogPage(lease),commercial:()=>commercialPage(lease),subscriptions:()=>commercialPage(lease),purchases:()=>commercialPage(lease),charges:()=>commercialPage(lease),credits:()=>commercialPage(lease),finance:()=>financePage(lease),payments:()=>financePage(lease),expenses:()=>financePage(lease),fiscal:()=>financePage(lease),files:()=>filesPage(lease),media:()=>filesPage(lease),reports:()=>reportsPage(lease),system:()=>(isAdmin()?systemPage(lease):trashOnlyPage(lease))}[page];if(fn)await fn()}catch(e){content(`<div class="error">${esc(e.message)}</div>`,lease)}finally{if(lease===navigationSequence)navigationFinished()}}
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
  archiveButton.onclick=async()=>{const ids=controller.view().selectedIds;if(!ids.length||!await confirmDialog(`Excluir ${ids.length} cliente(s)? Eles vão para a Lixeira junto com suas frotas e veículos e podem ser restaurados em até 14 dias. O histórico financeiro é mantido.`,{title:'Excluir clientes',okLabel:'Excluir',danger:true}))return;return runDomAction({key:'client-archive',scope:archiveButton,action:()=>api('/clients/archive',{method:'POST',body:JSON.stringify({client_ids:ids})}),refresh:async result=>{const blocked=(result.blocked||[]).map(item=>{const row=d.items.find(client=>client.id===item.id);return `${row?.legal_name||item.id}: ${(item.reasons||[]).join(', ')}`});toast({type:blocked.length?'error':'success',message:`${result.archived_ids?.length||0} cliente(s) arquivado(s).${blocked.length?' Bloqueados: '+blocked.join(' | '):''}`});await show('clients')},notify:toast})};
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
    bindPlateCheck(form);
    bindActionForm(form,{key:'vehicle-create',action:async()=>{const payload=buildVehiclePayload(formData(form));await createVehicle(payload);closeOverlay()},refresh:()=>mobilityPage(filters),successMessage:'Veículo cadastrado.',notify:toast});
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

  const openTransfer=vehicle=>openMoveVehicle(vehicle,{onDone:()=>mobilityPage(filters)});

  const openFleetProfile=async fleetId=>{
    const profile=await api('/fleets/'+encodeURIComponent(fleetId)+'/profile');
    const companies=await api('/clients/'+encodeURIComponent(profile.fleet.client_id)+'/companies');
    const drawer=openDrawer({title:'Ficha da Frota',subtitle:[profile.fleet.name,profile.fleet.code].filter(Boolean).join(' · '),content:renderFleetProfile(profile,{companies:companies.items||[]})});
    drawer.querySelector('.ui-drawer').classList.add('r2-profile-wide');
    const edit=drawer.querySelector('#fleetEditForm');
    bindActionForm(edit,{key:`fleet-edit:${fleetId}`,action:async()=>{const payload=formData(edit);payload.expected_revision=Number(payload.expected_revision);await api('/fleets/'+encodeURIComponent(fleetId),{method:'PATCH',body:JSON.stringify(payload)});closeOverlay()},refresh:()=>mobilityPage(filters),successMessage:'Frota atualizada.',notify:toast});
    const addVehicle=drawer.querySelector('[data-add-vehicle-fleet]');
    if(addVehicle)addVehicle.onclick=()=>{closeOverlay();openVehicleDrawer({client_id:profile.fleet.client_id,client_name:profile.fleet.client_name||profile.company?.legal_name,fleet_id:fleetId})};
    drawer.querySelectorAll('[data-open-vehicle-transfer]').forEach(button=>button.onclick=()=>{const vehicle=profile.vehicles.find(row=>row.id===button.dataset.openVehicleTransfer);if(vehicle)openTransfer({...vehicle,client_id:vehicle.client_id||profile.fleet.client_id,client_name:vehicle.client_name||profile.fleet.client_name,fleet_id:fleetId,fleet_name:profile.fleet.name})});
  };

  document.querySelector('#newVehicle').onclick=()=>openVehicleDrawer();
  document.querySelector('#newFleet').onclick=openFleetDrawer;
  document.querySelectorAll('[data-open-fleet]').forEach(button=>button.onclick=()=>openFleetProfile(button.dataset.openFleet).catch(error=>toast({type:'error',message:error.message})));
  document.querySelectorAll('[data-open-vehicle-transfer]').forEach(button=>button.onclick=()=>{const vehicle=(data.particulars||[]).find(row=>row.id===button.dataset.openVehicleTransfer);if(vehicle)openTransfer(vehicle)});
}

async function catalogPage(lease=null){
  const d=await api('/catalog');
  if(!content(renderCatalogPage(d,{costs:can('catalog.costs')}),lease))return;
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
      openActionMenu(button,filterMenu(subscriptionMenuItems(sub)).map(item=>({...item,onClick:handlers[item.key]})));
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
  let active=(location.hash.match(/^#finance\/(payments|expenses|fiscal)$/)?.[1])||legacyTab;{const perm={payments:'finance.view',expenses:'expenses.view',fiscal:'fiscal.view'};if(!can(perm[active]))active=['payments','expenses','fiscal'].find(tab=>can(perm[tab]))||'payments'}
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
    document.querySelectorAll('[data-expense-delete]').forEach(button=>bindActionButton(button,{key:'expense-delete:'+button.dataset.expenseDelete,confirm:'Excluir esta despesa? Ela fica 14 dias na Lixeira (Sistema › Lixeira) e pode ser restaurada.',action:()=>api('/expenses/'+encodeURIComponent(button.dataset.expenseDelete),{method:'DELETE'}),refresh:reload,successMessage:'Despesa excluída.',notify:toast}));
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
}

function reportsPage(lease=null){const names=['clients','vehicles','charges','payments','credits','expenses'];const labels={clients:'Clientes',vehicles:'Veículos',charges:'Mensalidades (cobranças)',payments:'Recebimentos',credits:'Créditos',expenses:'Despesas'};if(!content(`<h2>Relatórios</h2><div class="panel"><p>Baixe em CSV ou Excel (XLSX). Os arquivos são protegidos contra fórmulas maliciosas.</p><div class="report-grid">${names.map(n=>`<div class="card"><strong>${esc(labels[n]||n)}</strong><div class="actions"><button data-report="${n}" data-ext="csv" class="ui-btn ui-btn-secondary">CSV</button><button data-report="${n}" data-ext="xlsx" class="ui-btn ui-btn-primary">Excel</button></div></div>`).join('')}</div></div>`,lease))return;document.querySelectorAll('[data-report]').forEach(b=>b.onclick=()=>runDomAction({key:'report:'+b.dataset.report+b.dataset.ext,scope:b,action:()=>downloadReport(b.dataset.report,b.dataset.ext),notify:toast}))}
async function downloadReport(name,ext){const r=await fetch(`/api/v1/reports/${name}.${ext}`);if(!r.ok)throw new Error('Falha no relatório');const a=document.createElement('a');a.href=URL.createObjectURL(await r.blob());a.download=`${name}.${ext}`;a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000)}
function organizeSystemPage(runtime){
  const root=document.querySelector('#content');if(!root||root.querySelector('.system-tabs'))return;
  const tabs=document.createElement('div');tabs.className='system-tabs';tabs.innerHTML='<button type="button" class="active" data-system-tab="admin">Administração</button><button type="button" data-system-tab="users">Usuários</button><button type="button" data-system-tab="cloud">Nuvem</button><button type="button" data-system-tab="trash">Lixeira</button><button type="button" data-system-tab="development">Desenvolvimento</button>';
  const admin=document.createElement('section');admin.className='system-panel';admin.dataset.systemPanel='admin';
  const development=document.createElement('section');development.className='system-panel';development.dataset.systemPanel='development';development.hidden=true;
  const advanced=new Set(['Recovery / transferência','Recuperação / transferência','Auditoria','Integrações futuras','Integrações planejadas']);
  [...root.querySelectorAll(':scope > .panel')].forEach(panel=>(advanced.has(panel.querySelector('h3')?.textContent?.trim())?development:admin).appendChild(panel));
  const runtimePanel=document.createElement('div');runtimePanel.className='panel';runtimePanel.innerHTML=`<h3>Runtime e atualização</h3><dl class="runtime-grid"><dt>Versão</dt><dd>${esc(runtime?.version||'—')}</dd><dt>Schema</dt><dd>${esc(runtime?.schema_version||'—')}</dd><dt>Ambiente</dt><dd>${esc(runtime?.environment||'—')}</dd><dt>APP_ROOT</dt><dd>${esc(runtime?.app_root||'—')}</dd><dt>DATA_ROOT</dt><dd>${esc(runtime?.data_root||'—')}</dd><dt>BACKUP_ROOT</dt><dd>${esc(runtime?.backup_root||'—')}</dd><dt>Última atualização</dt><dd>${esc(runtime?.update?.state||'Nenhuma registrada')}</dd></dl><p class="muted">Pacotes .usup são verificados por assinatura e checksum pelo atualizador externo antes da troca transacional.</p>`;development.prepend(runtimePanel);
  const cloudSection=document.createElement('section');cloudSection.className='system-panel';cloudSection.dataset.systemPanel='cloud';cloudSection.hidden=true;
  const trashSection=document.createElement('section');trashSection.className='system-panel';trashSection.dataset.systemPanel='trash';trashSection.hidden=true;
  const usersSection=document.createElement('section');usersSection.className='system-panel';usersSection.dataset.systemPanel='users';usersSection.hidden=true;
  const header=root.querySelector('.ui-page-header');header?.after(tabs,admin,usersSection,cloudSection,trashSection,development);
  const sections={admin,users:usersSection,cloud:cloudSection,trash:trashSection,development};
  const loaders={users:()=>loadUsersTab(usersSection),cloud:()=>loadCloudTab(cloudSection),trash:()=>loadTrashTab(trashSection)};
  const select=name=>{tabs.querySelectorAll('button').forEach(item=>item.classList.toggle('active',item.dataset.systemTab===name));Object.entries(sections).forEach(([key,el])=>{el.hidden=key!==name});loaders[name]?.()};
  tabs.querySelectorAll('[data-system-tab]').forEach(button=>button.onclick=()=>{history.replaceState(null,'','#system/'+button.dataset.systemTab);select(button.dataset.systemTab)});
  const wanted=location.hash.match(/^#system\/(users|cloud|trash|development)$/)?.[1];if(wanted)select(wanted);
}
async function loadPlacaPanel(section,status){
  const data=await apiClient.request('/cloud/placa');const host=document.createElement('div');host.innerHTML=renderPlacaPanel(data,status);section.append(host);
  const form=host.querySelector('#placaForm');const out=host.querySelector('[data-placa-out]');
  bindActionForm(form,{key:'placa-publish',notify:toast,action:async()=>{const p=formData(form);const r=await api('/cloud/placa/publish',{method:'POST',body:JSON.stringify({form:p.form,placa_url:p.placa_url,github:{repo:p.repo,path:p.path,branch:p.branch,token:p.token}})});
      const json=JSON.stringify(r.placa,null,2);const href='data:application/json;charset=utf-8,'+encodeURIComponent(json);
      out.innerHTML=r.published?msg(`Placa versão ${r.seq} publicada no GitHub. Os Servidores seguem em até alguns minutos.`,'success')
        :msg(`Placa versão ${r.seq} pronta. Salve o arquivo no GitHub (substitua o placa.json) e informe o endereço público acima.`,'notice')+`<p><a class="ui-btn ui-btn-secondary" download="placa.json" href="${href}">Baixar placa.json</a></p>`;
      return r},successMessage:'Placa publicada.'});
  bindActionButton(host.querySelector('[data-placa-check]'),{key:'placa-check',notify:toast,action:()=>api('/cloud/placa/check',{method:'POST',body:'{}'}),refresh:()=>loadCloudTab(section),successMessage:'Placa conferida.'});
}
async function loadCloudTab(section){
  section.innerHTML='<div class="panel"><p class="muted">Carregando…</p></div>';
  let status;try{status=await apiClient.request('/cloud/status')}catch(error){section.innerHTML=`<div class="error">${esc(error.message)}</div>`;return}
  section.innerHTML=renderCloudPanel(status);
  if(isGlobal()&&me?.environment==='production')loadPlacaPanel(section,status).catch(()=>{});
  if(isGlobal())bindCloudRestoreEntry();else section.querySelectorAll('.cloud-advanced,#cloudConnectForm,.more-options,[data-cloud-points],[data-cloud-disconnect],[data-cloud-force],.cloud-steps').forEach(el=>el.remove());
  const reload=()=>loadCloudTab(section);
  const form=section.querySelector('#cloudConnectForm');
  if(form)bindActionForm(form,{key:'cloud-connect',action:async()=>{const p=formData(form);let r=await api('/cloud/connect',{method:'POST',body:JSON.stringify({url:p.url,secret:p.secret})});
    if(r.needs_choice){const choice=await openDialog({title:'A nuvem já tem dados',body:`<p>Esta nuvem já tem dados de outra instalação (versão ${esc(r.head?.generation)}, ${esc(formatDateBR(r.head?.created_at,true))}).</p><p class="muted">Para trazer os dados da nuvem para este computador, use Sistema › Nuvem › Avançado › “Restaurar da nuvem” (Administrador).</p>`,actions:[{label:'Não mudar nada',value:null},{label:'Substituir a nuvem por este computador',kind:'danger',value:'replace'}]});if(choice!=='replace')return;r=await api('/cloud/connect',{method:'POST',body:JSON.stringify({url:p.url,secret:p.secret,mode:'replace'})})}
    return r},refresh:reload,successMessage:'Nuvem conectada e dados enviados.',notify:toast});
  const sync=section.querySelector('[data-cloud-sync]');if(sync)bindActionButton(sync,{key:'cloud-sync',action:()=>api('/cloud/sync',{method:'POST',body:'{}'}),refresh:reload,successMessage:'Dados enviados para a nuvem.',notify:toast});
  const force=section.querySelector('[data-cloud-force]');if(force)bindActionButton(force,{key:'cloud-force',confirm:'Substituir o conteúdo da nuvem pelos dados deste computador? A versão da outra máquina deixa de ser a atual (fica nos pontos de restauração por 14 dias).',action:()=>api('/cloud/sync',{method:'POST',body:JSON.stringify({force:true,confirm:'SUBSTITUIR NUVEM'})}),refresh:reload,successMessage:'Nuvem atualizada com este computador.',notify:toast});
  const disconnect=section.querySelector('[data-cloud-disconnect]');if(disconnect)bindActionButton(disconnect,{key:'cloud-disconnect',confirm:'Parar de enviar para a nuvem? O que já está lá continua guardado.',action:()=>api('/cloud/disconnect',{method:'POST',body:'{}'}),refresh:reload,successMessage:'Envio para a nuvem desligado.',notify:toast});
  const kit=section.querySelector('[data-cloud-kit]');if(kit)kit.onclick=()=>openDrawer({title:'Kit de recuperação',content:renderRecoveryKit(status)});
  const pointsButton=section.querySelector('[data-cloud-points]');
  if(pointsButton)bindActionButton(pointsButton,{key:'cloud-points',action:async()=>{const box=section.querySelector('[data-cloud-points-box]');const r=await api('/cloud/points');box.innerHTML=renderPointsTable(r.items||[]);
    box.querySelectorAll('[data-cloud-restore-point]').forEach(button=>bindActionButton(button,{key:'cloud-point:'+button.dataset.cloudRestorePoint,confirm:'Voltar todos os dados para este ponto? O estado atual é guardado antes num backup local.',action:()=>api('/cloud/points/'+encodeURIComponent(button.dataset.cloudRestorePoint)+'/restore',{method:'POST',body:JSON.stringify({confirm:'RESTAURAR PONTO'})}),refresh:reload,successMessage:'Dados restaurados para o ponto escolhido.',notify:toast}))},notify:toast});
  if(status.running||status.pending_changes){clearTimeout(section._poll);section._poll=setTimeout(()=>{if(section.isConnected&&!section.hidden)loadCloudTab(section)},15000)}
}
// U-02 — Sistema › Usuários (administradores): usuários e pacotes de acesso.
async function loadUsersTab(section){
  section.innerHTML='<div class="panel"><p class="muted">Carregando…</p></div>';
  let data;try{data=await apiClient.request('/users')}catch(error){section.innerHTML=`<div class="error">${esc(error.message)}</div>`;return}
  section.innerHTML=renderUsersTab(data);
  bindUsersTab(section,{data,api,toast,confirmDialog,openDrawer,closeOverlay,bindActionForm,bindActionButton,reload:()=>loadUsersTab(section)});
}
// U-05 — pacote sem o menu Sistema mas com Lixeira: só a Lixeira.
async function trashOnlyPage(lease=null){
  if(!content(pageHeader('Lixeira','Itens excluídos nos últimos 14 dias')+'<section id="trashOnly"></section>',lease))return;
  await loadTrashTab(document.querySelector('#trashOnly'));
}
async function loadTrashTab(section){
  section.innerHTML='<div class="panel"><p class="muted">Carregando…</p></div>';
  const data=await apiClient.request('/trash');
  section.innerHTML=renderTrashPanel(data.items||[]);
  section.querySelectorAll('[data-trash-restore]').forEach(button=>bindActionButton(button,{key:'trash-restore:'+button.dataset.trashRestore,action:()=>api('/trash/'+encodeURIComponent(button.dataset.trashRestore)+'/restore',{method:'POST',body:'{}'}),refresh:()=>loadTrashTab(section),successMessage:'Item restaurado.',notify:toast}));
}
function bindSystemActions(){
  const settingsForm=document.querySelector('#settingsForm');if(!settingsForm)return;
  api('/system/runtime').then(organizeSystemPage).catch(()=>organizeSystemPage(null));
  bindActionForm(settingsForm,{key:'settings-save',action:()=>api('/settings',{method:'PUT',body:JSON.stringify(formData(settingsForm))}),refresh:()=>show('system'),successMessage:'Configurações salvas.',notify:toast});
  const brandForm=document.querySelector('#brandForm');bindActionForm(brandForm,{key:'branding-upload',action:async()=>{const fd=new FormData(brandForm),kind=fd.get('kind'),file=fd.get('file');const body=new FormData();body.append('file',file);await apiForm('/branding/'+kind,body)},refresh:()=>location.reload(),successMessage:'Identidade visual atualizada.',notify:toast});
  bindActionButton(document.querySelector('#backup'),{key:'backup-create',action:()=>api('/backups',{method:'POST',body:'{}'}),refresh:()=>show('system'),successMessage:'Backup criado.',notify:toast});
  const restoreForm=document.querySelector('#restoreForm');if(restoreForm)restoreForm.onsubmit=async event=>{event.preventDefault();if(!await confirmDialog('Restaurar este backup e substituir o ambiente atual?',{title:'Restaurar backup',okLabel:'Restaurar',danger:true}))return;return runDomAction({key:'backup-restore',scope:restoreForm,action:async()=>{const body=new FormData();body.append('file',new FormData(restoreForm).get('file'));await apiForm('/backups/restore',body)},refresh:()=>show('dashboard'),successMessage:'Backup restaurado.',notify:toast})};
  const recoveryForm=document.querySelector('#recoveryForm');bindActionForm(recoveryForm,{key:'recovery-export',action:async()=>{const payload=formData(recoveryForm);payload.transfer=payload.transfer==='true';return {result:await api('/recovery/export',{method:'POST',body:JSON.stringify(payload)}),transfer:payload.transfer}},refresh:({result,transfer})=>{document.querySelector('#recoveryOut').innerHTML=msg(`Recovery criado: ${result.name}`,'notice')+`<a class="download-link" href="/api/v1/recovery/${encodeURIComponent(result.name)}">Baixar ${esc(result.name)}</a>`;if(transfer)me.station={...(me.station||{}),is_writer:0}},successMessage:'Recovery criado.',notify:toast});
  bindActionForm(document.querySelector('#claimForm'),{key:'station-claim',action:()=>api('/stations/claim',{method:'POST',body:JSON.stringify({confirm:'ASSUMIR ESCRITA'})}),refresh:()=>location.reload(),successMessage:'Escrita assumida.',notify:toast});
  const emergencyForm=document.querySelector('#emergencyForm');if(emergencyForm)emergencyForm.onsubmit=async event=>{event.preventDefault();if(!await confirmDialog('Use apenas se a estação escritora anterior foi retirada de operação. Continuar?',{title:'Assumir gravação',okLabel:'Continuar',danger:true}))return;const reason=formData(emergencyForm).reason;return runDomAction({key:'station-emergency',scope:emergencyForm,action:()=>api('/stations/emergency-takeover',{method:'POST',body:JSON.stringify({confirm:'ASSUMIR EMERGENCIA',reason})}),refresh:()=>location.reload(),successMessage:'Escrita de emergência assumida.',notify:toast})};
  const resetForm=document.querySelector('#resetForm');bindActionForm(resetForm,{key:'admin-reset',confirm:'Redefinir esta posição administrativa? O acesso atual dela deixará de funcionar.',action:async()=>{const payload=formData(resetForm);return api('/auth/reset-admin/'+payload.slot,{method:'POST',body:JSON.stringify({reason:payload.reason})})},refresh:result=>{document.querySelector('#adminOut').innerHTML=msg('Ticket: '+result.ticket,'notice')},successMessage:'Administrador preparado para recadastro.',notify:toast});
  const passwordForm=document.querySelector('#pwdForm');bindActionForm(passwordForm,{key:'password-change',action:()=>api('/auth/change-password',{method:'POST',body:JSON.stringify(formData(passwordForm))}),refresh:()=>{me=null;return boot()},successMessage:'Senha alterada.',notify:toast});
  for(const [id,target] of [['enterTest','test'],['leaveTest','production']]){const button=document.querySelector('#'+id);if(button)bindActionButton(button,{key:'env-'+target,action:async()=>{const r=await api('/session/environment',{method:'POST',body:JSON.stringify({environment:target})});csrf=r.csrf;me=r;renderShell();await show(target==='test'?'system':(allowedPages(nav.map(([key])=>key))[0]||'dashboard'));return r},successMessage:target==='test'?'Você entrou no banco de Teste.':'De volta ao Real.',notify:toast})}
  if(document.querySelector('#resetTest'))bindActionButton(document.querySelector('#resetTest'),{key:'sandbox-reset',confirm:'Apagar TODOS os dados do ambiente de TESTE? O ambiente Real não é afetado.',action:()=>api('/sandbox/reset',{method:'POST',body:JSON.stringify({confirm:'LIMPAR TESTES'})}),refresh:()=>show('dashboard'),successMessage:'Ambiente de testes limpo.',notify:toast});
}
// G-04 — Adm Local (um só) e Adm Global (o dono). Painéis do Sistema.
const isGlobal=()=>!!me?.is_global;
const qs=sel=>document.querySelector(sel)||{};
function renderAdminPanels(st){
  if(isGlobal())return `<div class="panel adm-global-panel"><h3>Adm Global</h3><p class="muted">Você entrou como <b>Adm Global</b>. Estas ações valem só para esta instalação.</p>
    <h4>Adm Local</h4>${st.local_admin?`<p>Adm Local: <b>${esc((st.admins||[]).find(a=>a.status==='ENROLLED')?.name||'—')}</b></p><form id="localPwdForm"><div class="row">${field('Nova senha do Adm Local','new_password','password')}</div><div class="actions"><button class="ui-btn ui-btn-secondary">Redefinir senha do Adm Local</button></div></form>
    <div class="actions"><button type="button" id="newRecoveryKey" class="ui-btn ui-btn-secondary">Gerar nova Chave de Recuperação</button></div>`:`<p class="muted">Esta instalação ainda não tem Administrador local. Crie agora o acesso do dia a dia da empresa.</p><form id="localAdminCreateForm"><div class="row">${field('Usuário do Adm Local','name')}${field('Senha (mínimo 4 caracteres)','password','password')}${field('Repita a senha','confirm','password')}</div><div class="actions"><button class="ui-btn ui-btn-primary">Criar Adm Local</button></div></form>`}
    <h4>Seu acesso</h4><div class="actions" style="margin-bottom:12px"><button type="button" id="globalPass" class="ui-btn ui-btn-primary">Gerar passe de 1 dia (pendrive)</button></div>
    <form id="globalPinForm"><div class="row">${field('Novo PIN','new_pin','password')}</div><div class="actions"><button class="ui-btn ui-btn-subtle">Trocar meu PIN</button></div></form><div id="globalOut"></div></div>`;
  const admin=(st.admins||[]).find(a=>a.status==='ENROLLED');
  return `<div class="panel"><h3>Administrador</h3><p>Adm Local: <b>${esc(admin?.name||'—')}</b>. Esqueceu a senha? Use a <b>Chave de Recuperação</b> na tela de entrada.</p></div>`+
    (st.global_configured?'':`<div class="panel adm-global-setup"><h3>Configurar Adm Global (primeira vez)</h3><p class="muted">Só para o dono do sistema. Escolha um nome de acesso que ninguém usa e um PIN (4 dígitos ou mais). O PIN não fica salvo em lugar nenhum.</p><form id="globalSetupForm"><div class="row">${field('Nome de acesso','login')}${field('PIN','pin','password')}${field('Repita o PIN','pin_confirm','password')}</div><div class="actions"><button class="ui-btn ui-btn-primary">Configurar</button></div></form><div id="globalSetupOut"></div></div>`);
}
function showRecoveryKey(code,title='Chave de Recuperação'){return openDialog({title,body:`<p>Guarde esta chave <b>fora do computador</b> (papel ou cofre de senhas). Com ela o Administrador redefine a senha se esquecer. Ela aparece só agora.</p><p class="recovery-key"><code>${esc(code)}</code></p>`,actions:[{label:'Já guardei',value:true,kind:'primary'}]})}
function bindAdminPanels(){
  const createForm=document.querySelector('#localAdminCreateForm');
  bindActionForm(createForm,{key:'local-admin-create',action:async()=>{const p=formData(createForm);if(p.password!==p.confirm)throw new Error('As senhas não conferem.');const r=await api('/admin-local/create',{method:'POST',body:JSON.stringify({name:p.name,password:p.password})});await showRecoveryKey(r.recovery_key,'Chave de Recuperação do Adm Local');return r},refresh:()=>show('system'),successMessage:'Adm Local criado.',notify:toast});
  bindActionForm(document.querySelector('#localPwdForm'),{key:'local-pwd',action:()=>api('/admin-local/password',{method:'POST',body:JSON.stringify(formData(document.querySelector('#localPwdForm')))}),successMessage:'Senha do Adm Local redefinida.',notify:toast});
  bindActionButton(document.querySelector('#newRecoveryKey'),{key:'new-recovery',confirm:'Gerar uma nova Chave de Recuperação? A anterior deixa de valer.',action:async()=>{const r=await api('/admin-local/recovery-key',{method:'POST',body:'{}'});await showRecoveryKey(r.recovery_key,'Nova Chave de Recuperação do Adm Local');return r},notify:toast});
  bindActionButton(document.querySelector('#globalPass'),{key:'global-pass',action:async()=>{const r=await api('/global/pass',{method:'POST',body:'{}'});const a=document.createElement('a');a.href='data:application/json;charset=utf-8,'+encodeURIComponent(JSON.stringify(r.pass,null,2));a.download=r.file||'passe-adm-global.json';a.click();return r},successMessage:'Passe gerado (válido por 1 dia). Copie o arquivo para a pasta Trust do UStracker na máquina sem internet.',notify:toast});
  const saveJson=(obj,name)=>{const a=document.createElement('a');a.href='data:application/json;charset=utf-8,'+encodeURIComponent(JSON.stringify(obj,null,2));a.download=name;a.click()};
  bindActionForm(document.querySelector('#globalPinForm'),{key:'global-pin',action:async()=>{const r=await api('/global/pin',{method:'POST',body:JSON.stringify(formData(document.querySelector('#globalPinForm')))});if(r.token)saveJson(r.token,r.file||'token-mestre.json');return r},successMessage:'Novo PIN preparado: o arquivo token-mestre.json foi baixado. Ele passa a valer quando for publicado no acesso-UStracker.',notify:toast});
  bindActionForm(document.querySelector('#globalSetupForm'),{key:'global-setup',action:async()=>{const r=await api('/global/setup',{method:'POST',body:JSON.stringify(formData(document.querySelector('#globalSetupForm')))});if(r.token)saveJson(r.token,r.file||'token-mestre.json');return r},refresh:()=>show('system'),successMessage:'Adm Global configurado. Falta publicar o Token Mestre.',notify:toast});
}
async function systemPage(){const [st,sets,baks,ints,stations,audit]=await Promise.all([api('/auth/setup-status'),api('/settings'),api('/backups'),(isGlobal()?api('/integrations'):Promise.resolve({})),api('/stations'),(isGlobal()?api('/audit?limit=100'):Promise.resolve({items:[]}))]);content(`<h2>Sistema</h2>${renderAdminPanels(st)}${isGlobal()?'<div id="adminOut"></div>':`<div class="panel"><h3>Minha senha</h3><form id="pwdForm"><div class="row">${field('Senha atual','current_password','password')}${field('Nova senha','new_password','password')}</div><div class="actions"><button>Trocar minha senha</button></div></form><div id="adminOut"></div></div>`}<div class="panel"><h3>Branding e configuração</h3><form id="settingsForm"><div class="row">${field('Empresa','company_display_name','text',sets.company_display_name||'')}${field('Telefone','contact_phone','text',sets.contact_phone||'')}${field('E-mail','contact_email','email',sets.contact_email||'')}${field('Endereço público','address_display','text',sets.address_display||'')}${field('Cor primária','theme_primary','color',sets.theme_primary||'#155eef')}${field('Cor destaque','theme_accent','color',sets.theme_accent||'#0f9f6e')}${field('Retenção backups','backup_retention','number',sets.backup_retention||'14')}</div><div class="actions"><button>Salvar configurações</button></div></form><form id="brandForm"><div class="row"><div class="field"><label>Tipo</label><select name="kind"><option>logo</option><option>favicon</option><option>icon</option></select></div><div class="field"><label>Imagem</label><input name="file" type="file" accept="image/*"></div></div><div class="actions"><button>Enviar branding</button></div></form></div><div class="panel"><h3>Backup</h3><div class="actions"><button id="backup">Criar backup cifrado</button></div>${isGlobal()?`<form id="restoreForm"><div class="field"><label>Restaurar .usbk</label><input name="file" type="file" accept=".usbk" required></div><div class="actions"><button class="danger">Restaurar backup</button></div></form>`:''}${dt(baks.items,'backupsDT')}</div>${isGlobal()?`<div class="panel"><h3>Recovery / transferência</h3><form id="recoveryForm"><div class="row">${field('Passphrase (12+ caracteres)','passphrase','password')}<label><input name="transfer" type="checkbox" value="true"> Preparar transferência e desarmar esta escritora</label></div><div class="actions"><button>Gerar .usre</button></div></form><div id="recoveryOut"></div></div>`:''}<div class="panel"><h3>Servidores</h3><p class="muted">Cada computador com o UStracker é um Servidor. Todos usam o mesmo banco na nuvem; a vez de gravar passa sozinha entre eles.</p>${dt(stations.items,'stationsDT')}${isGlobal()?`<form id="claimForm"><div class="actions"><button>ASSUMIR ESCRITA pendente</button></div></form><form id="emergencyForm"><div class="row">${field('Motivo da emergência','reason')}</div><div class="actions"><button class="danger">ASSUMIR EMERGÊNCIA</button></div></form>`:''}</div>${isGlobal()?`<div class="panel"><h3>Auditoria</h3><div class="actions"><button id="verifyAudit">Verificar cadeia</button></div><div id="auditOut"></div>${dt(audit.items,'auditDT')}</div><div class="panel"><h3>Integrações futuras</h3><pre>${esc(JSON.stringify(ints,null,2))}</pre></div>`:''}${`<div class="panel test-env-panel"><h3>Banco de Teste</h3>${me.environment==='test'?`<p>Você está no <b>banco de Teste</b>: local, só deste computador, nada aqui vai para a nuvem nem aparece no Real.</p><div class="actions"><button id="leaveTest" class="ui-btn ui-btn-primary">Voltar ao Real</button><button id="resetTest" class="danger">LIMPAR TESTES</button></div>`:`<p class="muted">Área de treino só do Administrador. Fica neste computador, nunca vai para a nuvem e não aparece para Gerentes e Operadores.</p><div class="actions"><button id="enterTest" class="ui-btn ui-btn-secondary">Entrar no banco de Teste</button></div>`}</div>`}<div class="panel"><h3>Sessão</h3><div class="actions"><button id="logout" class="secondary">Sair</button><button id="shutdown" class="danger">Encerrar sistema</button></div></div>`);qs('#settingsForm').onsubmit=async e=>{e.preventDefault();await api('/settings',{method:'PUT',body:JSON.stringify(formData(e.target))});show('system')};qs('#brandForm').onsubmit=async e=>{e.preventDefault();const fd=new FormData(e.target),kind=fd.get('kind'),file=fd.get('file');const body=new FormData();body.append('file',file);await apiForm('/branding/'+kind,body);location.reload()};qs('#backup').onclick=async()=>{await api('/backups',{method:'POST',body:'{}'});show('system')};qs('#restoreForm').onsubmit=async e=>{e.preventDefault();if(!await confirmDialog('Restaurar este backup e substituir o ambiente atual?',{title:'Restaurar backup',okLabel:'Restaurar',danger:true}))return;const fd=new FormData();fd.append('file',new FormData(e.target).get('file'));await apiForm('/backups/restore',fd);show('dashboard')};qs('#recoveryForm').onsubmit=async e=>{e.preventDefault();const p=formData(e.target);p.transfer=p.transfer==='true';const r=await api('/recovery/export',{method:'POST',body:JSON.stringify(p)});qs('#recoveryOut').innerHTML=msg(`Recovery criado: ${r.name}`,'notice')+`<a class="download-link" href="/api/v1/recovery/${encodeURIComponent(r.name)}">Baixar ${esc(r.name)}</a>`;if(p.transfer){me.station={...(me.station||{}),is_writer:0};toast({message:'Estação atual alterada para somente leitura.'})}};qs('#claimForm').onsubmit=async e=>{e.preventDefault();await api('/stations/claim',{method:'POST',body:JSON.stringify({confirm:'ASSUMIR ESCRITA'})});location.reload()};qs('#emergencyForm').onsubmit=async e=>{e.preventDefault();const reason=formData(e.target).reason;if(!await confirmDialog('Use apenas se a estação escritora anterior foi retirada de operação. Continuar?',{title:'Assumir gravação',okLabel:'Continuar',danger:true}))return;await api('/stations/emergency-takeover',{method:'POST',body:JSON.stringify({confirm:'ASSUMIR EMERGENCIA',reason})});location.reload()};qs('#verifyAudit').onclick=async()=>{const r=await api('/audit/verify');qs('#auditOut').innerHTML=msg(r.ok?`Cadeia íntegra (${r.events} eventos)`:`Cadeia quebrada no evento ${r.broken_at_id}`,r.ok?'success':'error')};qs('#resetFormX').onsubmit=async e=>{e.preventDefault();const p=formData(e.target);try{const r=await api('/auth/reset-admin/'+p.slot,{method:'POST',body:JSON.stringify({reason:p.reason})});qs('#adminOut').innerHTML=msg('Ticket: '+r.ticket,'notice')}catch(err){qs('#adminOut').innerHTML=msg(err.message,'error')}};qs('#pwdForm').onsubmit=async e=>{e.preventDefault();await api('/auth/change-password',{method:'POST',body:JSON.stringify(formData(e.target))});me=null;boot()};if(qs('#resetTest'))qs('#resetTest').onclick=async()=>{await api('/sandbox/reset',{method:'POST',body:JSON.stringify({confirm:'LIMPAR TESTES'})});show('dashboard')};qs('#logout').onclick=async()=>{await api('/auth/logout',{method:'POST',body:'{}'});me=null;boot()};qs('#shutdown').onclick=async()=>{await api('/system/shutdown',{method:'POST',body:'{}'});content('<div class="success">Sistema encerrado com segurança.</div>')};bindAdminPanels()}
document.addEventListener?.('click',e=>{if(e.target?.id==='shutdown'){e.preventDefault();e.stopImmediatePropagation();requestSystemShutdown().catch(err=>toast({type:'error',message:err.message}))}},true);
const nativeAlert=globalThis.alert?.bind(globalThis);if(nativeAlert)globalThis.alert=message=>nativeAlert(messagePtBR(message));observePtBR(document.body);localizeDom(document.body);loadIconSet().then(boot).catch(e=>app.innerHTML=`<section class="auth"><div class="error">${esc(messagePtBR(e.message))}</div></section>`);
