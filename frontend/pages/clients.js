import { formatBRL } from '../ui/formatters.js';

const esc = value => String(value ?? '').replace(/[&<>'"]/g, character => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;'
}[character]));

export function renderClientEditor(row = {}) {
  const type = row.document_type || 'CPF';
  const options = ['CPF', 'RG', 'CNH'].map(value => `<option value="${value}" ${type === value ? 'selected' : ''}>${value}</option>`).join('');
  return `<form id="clientDrawerForm">
    <div class="row">
      <div class="field"><label>Nome*</label><input name="legal_name" value="${esc(row.legal_name || '')}" required></div>
      <div class="field"><label>Tipo de documento*</label><select name="document_type">${options}</select></div>
      <div class="field"><label>Documento*</label><input name="document" value="${esc(row.document || '')}" required></div>
      <div class="field"><label>E-mail</label><input name="email" type="email" value="${esc(row.email || '')}"></div>
      <div class="field"><label>Telefone</label><input name="phone" value="${esc(row.phone || '')}"></div>
      <div class="field"><label>Nome Fantasia ou Razão Social (opcional)</label><input name="company_legal_name" value=""></div>
      <div class="field"><label>CNPJ <span class="muted">(não obrigatório)</span></label><input name="company_document" value=""></div>
    </div>
    <p class="muted">Informe ao menos e-mail ou telefone.</p>
  </form>`;
}

export function clientTableDefinition(onView = () => {}) {
  return {
    selectionMode: 'multiple',
    columns: [
      { key: 'legal_name', label: 'Cliente' },
      { key: 'primary_company', label: 'Empresa principal' },
      { key: 'primary_contact', label: 'Contato principal' },
      { key: 'vehicles_count', label: 'Veículos' },
      { key: 'generated_value_cents', label: 'Valor Gerado', format: value => formatBRL(Number(value || 0)) },
      { key: 'status', label: 'Status' },
    ],
    actions: [{ key: 'view', label: 'Abrir Ficha', icon: 'view', onClick: onView }],
  };
}

export function buildClientCreatePayload(values = {}) {
  const payload = { ...values };
  const documentType = String(payload.document_type || '').trim();
  const document = String(payload.document || '').trim();
  const companyLegalName = String(payload.company_legal_name || '').trim();
  const companyDocument = String(payload.company_document || '').trim();
  if (document) payload.documents = [{ type: documentType || 'RG', number: document, is_primary: true }];
  if (companyLegalName) payload.companies = [{ legal_name: companyLegalName, document: companyDocument || null, is_primary: true }];
  delete payload.document_type;
  delete payload.company_legal_name;
  delete payload.company_document;
  delete payload.trade_name;
  delete payload.public_name;
  return payload;
}
