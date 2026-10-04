import { confirmDialog } from './dialog.js';

const normalizeError = error => error?.message || 'Não foi possível concluir a ação.';
const defaultConfirm = (text, options = {}) => (globalThis.document?.body ? confirmDialog(text, { danger: options.danger !== false, okLabel: 'Confirmar' }) : (globalThis.confirm ? globalThis.confirm(text) : false));

export function createActionRunner({ onState = () => {} } = {}) {
  const inFlight = new Map();
  const generations = new Map();
  const publish = (key, status, extra = {}, callback = () => {}) => {
    const state = { key, status, ...extra };
    onState(state);
    callback(state);
  };
  const run = (key, task, callbacks = {}) => {
    if (inFlight.has(key)) return inFlight.get(key);
    publish(key, 'LOADING', {}, callbacks.onState);
    let execution;
    try { execution = task(); } catch (error) { execution = Promise.reject(error); }
    const promise = Promise.resolve(execution)
      .then(value => {
        publish(key, 'SUCCESS', { value }, callbacks.onState);
        callbacks.onSuccess?.(value);
        return value;
      }, error => {
        publish(key, 'ERROR', { error }, callbacks.onState);
        callbacks.onError?.(error);
        throw error;
      })
      .finally(() => {
        inFlight.delete(key);
        publish(key, 'IDLE', {}, callbacks.onState);
      });
    inFlight.set(key, promise);
    return promise;
  };
  const latest = (key, task, callbacks = {}) => {
    const generation = (generations.get(key) || 0) + 1;
    generations.set(key, generation);
    publish(key, 'LOADING', { generation }, callbacks.onState);
    return Promise.resolve().then(task).then(value => {
      if (generations.get(key) === generation) {
        publish(key, 'SUCCESS', { generation, value }, callbacks.onState);
        callbacks.onSuccess?.(value);
        publish(key, 'IDLE', { generation }, callbacks.onState);
      }
      return value;
    }, error => {
      if (generations.get(key) === generation) {
        publish(key, 'ERROR', { generation, error }, callbacks.onState);
        callbacks.onError?.(error);
        publish(key, 'IDLE', { generation }, callbacks.onState);
      }
      throw error;
    });
  };
  return { run, latest, isRunning: key => inFlight.has(key) };
}

const defaultRunner = createActionRunner();
const domInFlight = new Map();

export function runDomAction({
  key, scope, action, refresh, successMessage, notify = () => {}, runner = defaultRunner, confirm: confirmText = '',
  confirmFn = defaultConfirm, danger = true,
} = {}) {
  if (domInFlight.has(key)) return domInFlight.get(key);
  // R19: destructive actions declare `confirm`; cancelling performs no request and no notification.
  // V-05: the question is an in-app dialog (async) instead of the browser's confirm().
  if (confirmText && typeof confirmFn === 'function') {
    const asking = Promise.resolve(confirmFn(confirmText, { danger })).then(ok => ok
      ? (domInFlight.delete(key), runDomAction({ key, scope, action, refresh, successMessage, notify, runner }))
      : { ok: false, cancelled: true });
    domInFlight.set(key, asking);
    asking.finally(() => { if (domInFlight.get(key) === asking) domInFlight.delete(key); });
    return asking;
  }
  const controls = [
    ...(scope?.matches?.('button, input[type="submit"]') ? [scope] : []),
    ...(scope?.querySelectorAll?.('button, input[type="submit"]') || []),
  ];
  const disabledBefore = controls.map(control => control.disabled);
  controls.forEach(control => { control.disabled = true; });
  scope?.setAttribute?.('aria-busy', 'true');
  const promise = runner.run(key, async () => {
    const value = await action();
    await refresh?.(value);
    return value;
  }).then(value => {
    if (successMessage) notify({ type: 'success', message: successMessage });
    return { ok: true, value };
  }, error => {
    notify({ type: 'error', message: normalizeError(error) });
    return { ok: false, error };
  }).finally(() => {
    controls.forEach((control, index) => { if (control?.isConnected !== false) control.disabled = disabledBefore[index]; });
    scope?.removeAttribute?.('aria-busy');
    domInFlight.delete(key);
  });
  domInFlight.set(key, promise);
  return promise;
}

export function bindActionForm(form, options = {}) {
  if (!form) return null;
  form.onsubmit = event => {
    event.preventDefault();
    return runDomAction({ ...options, key: options.key || form.id || 'form-action', scope: form });
  };
  return form;
}

export function bindActionButton(button, options = {}) {
  if (!button) return null;
  button.onclick = event => {
    event?.preventDefault?.();
    return runDomAction({ ...options, key: options.key || button.id || 'button-action', scope: options.scope || button });
  };
  return button;
}
