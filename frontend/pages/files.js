import { formatDateBR } from '../ui/formatters.js';
import { codeTag } from '../ui/logical-codes.js';
import { renderEntityAutocomplete } from '../ui/entity-autocomplete.js';
const esc=s=>String(s??'').replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
const TYPE_LABEL={client:'Cliente',vehicle:'Veículo',fleet:'Frota',subscription:'Assinatura'};

/** R14 — record choices for one client (value = "type:id"); labels use logical codes, never UUIDs. */
export function entityChoices(profile={}){
  const client=profile.client||{};
  const rows=[];
  if(client.id)rows.push({value:`client:${client.id}`,label:`Cliente · ${client.legal_name||''} · ${client.code||''}`});
  for(const v of profile.vehicles||[])rows.push({value:`vehicle:${v.id}`,label:`Veículo · ${v.category_label||v.type||''} · ${[v.brand,v.model,v.plate].filter(Boolean).join(' ')} · ${v.code||''}`});
  for(const f of profile.fleets||[])rows.push({value:`fleet:${f.id}`,label:`Frota · ${f.name||''} · ${f.code||''}`});
  for(const s of profile.subscriptions||[])rows.push({value:`subscription:${s.id}`,label:`Assinatura · ${s.code||''}`});
  return rows;
}

export function renderFilesPage(data={}){
 const media=(data.media||[]).map(x=>`<tr><td>${esc(TYPE_LABEL[x.entity_type]||x.entity_type)}</td><td>${codeTag(x.entity_code)||'<span class="muted">—</span>'}</td><td>${esc(x.mime)}</td><td>${formatDateBR(x.created_at,true)}</td><td><button type="button" class="ui-btn ui-btn-danger" data-remove-media="${esc(x.id)}">Remover</button></td></tr>`).join('')||'<tr><td colspan="5" class="muted">Nenhuma foto.</td></tr>';
 const attachments=(data.attachments||[]).map(x=>`<tr><td>${esc(x.filename||'Link')}</td><td>${esc(TYPE_LABEL[x.entity_type]||x.entity_type)} ${codeTag(x.entity_code)}</td><td>${esc(x.origin==='LINK'?'Link':'Arquivo')}</td><td>${esc(x.mime||'')}</td><td>${formatDateBR(x.created_at,true)}</td><td>${x.origin==='LINK'?`<a href="${esc(x.url)}" target="_blank" rel="noopener">Abrir</a>`:`<a href="/api/v1/attachments/${esc(x.id)}">Baixar</a>`}</td></tr>`).join('')||'<tr><td colspan="6" class="muted">Nenhum anexo.</td></tr>';
 const hidden='<input type="hidden" name="entity_type"><input type="hidden" name="entity_id">';
 return `<h2>Fotos/Arquivos</h2>
 <div class="panel files-target"><h3>1. Escolha o registro</h3><form id="filesTargetForm"><div class="row">${renderEntityAutocomplete({name:'client_id',label:'Cliente',required:true})}<div class="field"><label>Registro</label><select name="target" disabled><option value="">Selecione o cliente primeiro</option></select></div></div></form><p class="muted" data-files-target-label>Nenhum registro selecionado.</p></div>
 <div class="panel"><h3>2. Foto operacional</h3><form id="mediaForm" data-auto-upload>${hidden}<label><input type="checkbox" name="retain_original" value="true"> Reter original cifrado</label><div class="actions"><label class="ui-btn ui-btn-primary ui-file-action is-disabled" data-needs-target="media">Escolher e enviar foto<input name="file" type="file" accept="image/jpeg,image/png,image/webp" required disabled></label></div></form><table class="compact-table"><thead><tr><th>Tipo</th><th>Código</th><th>MIME</th><th>Data</th><th>Ação</th></tr></thead><tbody>${media}</tbody></table></div>
 <div class="panel"><h3>3. Anexos e comprovantes</h3><p class="muted">Arquivos permitidos: JPG, PNG, WebP e PDF. Conteúdo executável é bloqueado.</p><form id="attachmentUploadForm" data-auto-upload>${hidden}<div class="actions"><label class="ui-btn ui-btn-primary ui-file-action is-disabled" data-needs-target="attachment">Escolher e enviar arquivo<input type="file" name="file" accept=".jpg,.jpeg,.png,.webp,.pdf" required disabled></label></div></form><form id="attachmentLinkForm">${hidden}<div class="row"><div class="field"><label>Link</label><input type="url" name="url" placeholder="https://..." required></div></div><div class="actions"><button disabled data-needs-target="attachment">Salvar Link</button></div></form><table class="compact-table"><thead><tr><th>Arquivo</th><th>Vinculado a</th><th>Origem</th><th>MIME</th><th>Data</th><th>Ação</th></tr></thead><tbody>${attachments}</tbody></table></div>`;
}
