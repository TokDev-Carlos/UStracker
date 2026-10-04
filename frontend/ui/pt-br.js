import { ERROR_MESSAGES } from './pt-br-errors.js';
const TERMS = Object.freeze({
  Dashboard: 'Visão geral', ACTIVE: 'ATIVO', INACTIVE: 'INATIVO', BLOCKED: 'BLOQUEADO',
  CANCELLED: 'CANCELADO', PAUSED: 'PAUSADA', ENDED: 'ENCERRADA', OPEN: 'ABERTO', CLOSED: 'FECHADO',
  PENDING: 'PENDENTE', PENDING_ENROLLMENT: 'CADASTRO PENDENTE', ENROLLED: 'CADASTRADO',
  PAID: 'PAGO', OVERDUE: 'VENCIDA', REVERSED: 'ESTORNADO', PLAN: 'PLANO', ITEM: 'ITEM',
  FEE: 'TAXA', INTEREST: 'JUROS', PENALTY: 'MULTA', DISCOUNT: 'DESCONTO', OTHER: 'OUTRO',
  production: 'Produção', test: 'Testes', clients: 'Clientes', fleets: 'Frotas', vehicles: 'Veículos',
  catalog: 'Planos e itens', subscriptions: 'Assinaturas', charges: 'Cobranças', payments: 'Recebimentos',
  credits: 'Créditos', expenses: 'Despesas', fiscal: 'Fiscal', media: 'Fotos', reports: 'Relatórios',
  system: 'Sistema', logo: 'Logotipo', favicon: 'Ícone do navegador', icon: 'Ícone do aplicativo',
  code: 'Código', name: 'Nome', category: 'Categoria', kind: 'Tipo', price: 'Preço', cost: 'Custo',
  public: 'Catálogo público', 'billing interval months': 'Periodicidade em meses',
  'Branding e configuração': 'Identidade visual e configuração',
  Backup: 'Cópia de segurança', Status: 'Situação',
  'Criar backup cifrado': 'Criar cópia de segurança cifrada',
  'Restaurar backup': 'Restaurar cópia de segurança',
  'Recovery / transferência': 'Recuperação / transferência',
  'Passphrase (12+ caracteres)': 'Frase secreta (12+ caracteres)',
  'Slot para reset': 'Posição administrativa para redefinição',
  'Resetar slot': 'Redefinir posição administrativa',
  'Ir para login': 'Ir para acesso',
  'Crie o Administrador 1. Serão emitidos dois tickets de uso único para os Administradores 2 e 3.': 'Crie o Administrador 1. Serão emitidos dois códigos temporários de uso único para os Administradores 2 e 3.',
  'Os tickets expiram em 15 minutos.': 'Os códigos temporários expiram em 15 minutos.',
  'Alterar status': 'Alterar situação',
  'Enviar branding': 'Enviar identidade visual',
  'Laboratório Test': 'Laboratório de testes',
  'CSV e XLSX com neutralização de formula injection.': 'CSV e XLSX com proteção contra injeção de fórmulas.',
  'Integrações futuras': 'Integrações planejadas', 'Tipo de entidade': 'Tipo de registro',
  'ID da entidade': 'Identificador do registro',
});

const COLUMN_LABELS = Object.freeze({
  id: 'Identificador', slot: 'Posição', name: 'Nome', legal_name: 'Razão social/Nome',
  trade_name: 'Nome fantasia', public_name: 'Nome público', document: 'Documento', email: 'E-mail',
  phone: 'Telefone', status: 'Situação', lifecycle_status: 'Situação', revision: 'Revisão',
  client_id: 'Cliente', fleet_id: 'Frota', vehicle_id: 'Veículo', subscription_id: 'Assinatura',
  charge_id: 'Cobrança', catalog_id: 'Item do catálogo', sector_or_unit: 'Setor/Unidade',
  plate: 'Placa', type: 'Tipo', tracker_serial_imei: 'Serial/IMEI', installed_on: 'Data de instalação',
  code: 'Código', category: 'Categoria', kind: 'Tipo', price_cents: 'Preço', cost_cents: 'Custo',
  amount_cents: 'Valor', adjustment_cents: 'Ajustes', balance_cents: 'Saldo',
  expected_amount_cents: 'Valor previsto', billing_interval_months: 'Periodicidade (meses)',
  due_day: 'Dia de vencimento', competence: 'Competência', start_on: 'Início', end_on: 'Fim',
  due_on: 'Vencimento', paid_on: 'Data do pagamento', method: 'Forma de pagamento',
  description: 'Descrição', supplier: 'Fornecedor', public: 'Catálogo público',
  entity_type: 'Tipo de registro', entity_id: 'Identificador do registro', created_at: 'Criado em',
  updated_at: 'Atualizado em', at: 'Data/hora', action: 'Ação', actor_slot: 'Administrador',
  external_ref: 'Referência externa', retain_original: 'Manter original', environment: 'Ambiente',
  size: 'Tamanho', modified_at: 'Modificado em', file: 'Arquivo', path: 'Local', role: 'Perfil', is_writer: 'Gravação',
});

const MESSAGES = Object.freeze({
  'invalid credentials': 'Credenciais inválidas.',
  'invalid environment': 'Ambiente inválido.',
  'admin name is required': 'O nome do administrador é obrigatório.',
  'admin name already in use': 'Este nome de administrador já está em uso.',
  'bootstrap already completed': 'A configuração inicial já foi concluída.',
  'invalid enrollment ticket': 'Código temporário de cadastro inválido.',
  'expired enrollment ticket': 'O código temporário de cadastro expirou.',
  'PIN must have at least 4 digits': 'O PIN deve ter pelo menos 4 dígitos.',
  'password must have at least 10 characters': 'A senha deve ter pelo menos 10 caracteres.',
  'secret must have at least 4 characters': 'O PIN ou a senha deve ter pelo menos 4 caracteres.',
  'invalid money value': 'Valor monetário inválido.',
  'money must be finite': 'O valor monetário deve ser finito.',
  'money supports at most 2 decimal places': 'O valor aceita no máximo duas casas decimais.',
  'empty money value': 'Informe um valor monetário.',
  'ambiguous money value': 'O formato do valor monetário é ambíguo.',
  'logical code not found': 'Código não encontrado.',
  'logical code does not match entity type': 'O código informado não corresponde ao tipo de entidade selecionado.',
  'logical code is immutable': 'O código lógico é imutável.',
  'vehicle category does not match fleet group': 'O tipo do veículo não corresponde ao grupo da frota. Escolha outra frota ou use uma frota "Misto".',
  'fleet has vehicles of another category': 'A frota tem veículos de outro tipo. Use "Misto" ou mova esses veículos antes.',
  'invalid fleet group': 'Grupo de frota inválido.',
  'invalid vehicle group': 'Grupo de veículo inválido.',
  'vehicle_id or fleet_id required': 'Informe o veículo ou a frota.',
  'client not found': 'Cliente não encontrado.',
  'target client not found': 'Cliente de destino não encontrado.',
  'fleet does not belong to client': 'A frota não pertence ao cliente.',
  'fleet does not belong to target client': 'A frota não pertence ao cliente de destino.',
  'invalid status': 'Situação inválida.',
  'invalid kind': 'Tipo inválido.',
  'invalid lifecycle_status': 'Situação da assinatura inválida.',
  'invalid adjustment kind': 'Tipo de ajuste inválido.',
  'adjustment amount cannot be zero': 'O valor do ajuste não pode ser zero.',
  'adjustment reason required': 'Informe o motivo do ajuste.',
  'payment not reversible': 'Este recebimento não pode ser estornado.',
  'disbursement not reversible': 'Este desembolso não pode ser estornado.',
  'unknown report': 'Relatório desconhecido.',
  'image exceeds 20 MiB': 'A imagem excede 20 MiB.',
  'animated images are not supported': 'Imagens animadas não são compatíveis.',
  'image exceeds 40 MP': 'A imagem excede 40 megapixels.',
  INTEGRATION_NOT_IMPLEMENTED: 'Integração ainda não implementada.',
});

export const labelPtBR = key => COLUMN_LABELS[key] || String(key ?? '').replaceAll('_', ' ');
export const valuePtBR = value => TERMS[String(value ?? '')] || String(value ?? '');

export function messagePtBR(value) {
  const message = String(value ?? '');
  if (MESSAGES[message]) return MESSAGES[message];
  if (ERROR_MESSAGES[message]) return ERROR_MESSAGES[message];
  const fleetLimit = message.match(/^fleet active vehicle limit reached \((\d+)\)$/);
  if (fleetLimit) return `A frota atingiu o limite de ${fleetLimit[1]} veículos ativos.`;
  if (message.startsWith('Backup automático: ')) return `Cópia de segurança automática: ${messagePtBR(message.slice(19))}`;
  const lock = message.match(/^login temporarily locked; try again in (\d+) seconds$/);
  if (lock) return `Acesso temporariamente bloqueado; tente novamente em ${lock[1]} segundo(s).`;
  const revision = message.match(/^revision conflict: current=(\d+)$/);
  if (revision) return `Conflito de edição: a revisão atual é ${revision[1]}.`;
  return message;
}

export function textPtBR(value) {
  const original = String(value ?? '');
  const trimmed = original.trim();
  const translated = TERMS[trimmed];
  if (translated) return original.replace(trimmed, translated);
  return original
    .replace(/ · production\b/g, ' · Produção')
    .replace(/ · test\b/g, ' · Testes')
    .replace(/Ticket:/g, 'Código temporário:')
    .replace(/Registrar Admin\b/g, 'Registrar administrador')
    .replace(/Recovery criado:/g, 'Pacote de recuperação criado:')
    .replace(/"tracking"/g, '"rastreamento"')
    .replace(/"fiscal_official"/g, '"fiscal_oficial"')
    .replace(/"enabled"/g, '"habilitada"')
    .replace(/"implemented"/g, '"implementada"')
    .replace(/: false/g, ': não')
    .replace(/: true/g, ': sim');
}

export function localizeDom(root) {
  if (!root) return;
  const documentRef = root.ownerDocument || globalThis.document;
  root.querySelectorAll?.('option').forEach(option => {
    if (!option.hasAttribute('value')) option.setAttribute('value', option.value);
  });
  const walker = documentRef.createTreeWalker(root, globalThis.NodeFilter?.SHOW_TEXT ?? 4);
  const nodes = [];
  while (walker.nextNode()) nodes.push(walker.currentNode);
  nodes.forEach(node => { node.nodeValue = textPtBR(node.nodeValue); });
  root.querySelectorAll?.('option').forEach(option => { option.textContent = valuePtBR(option.textContent); });
  ['placeholder', 'title', 'aria-label'].forEach(attribute => root.querySelectorAll?.(`[${attribute}]`).forEach(element => {
    element.setAttribute(attribute, textPtBR(element.getAttribute(attribute)));
  }));
}

export function observePtBR(root) {
  if (!root || !globalThis.MutationObserver) return null;
  const observer = new MutationObserver(records => records.forEach(record => record.addedNodes.forEach(node => {
    if (node.nodeType === 1) localizeDom(node);
    else if (node.nodeType === 3) node.nodeValue = textPtBR(node.nodeValue);
  })));
  observer.observe(root, { childList: true, subtree: true });
  return observer;
}
