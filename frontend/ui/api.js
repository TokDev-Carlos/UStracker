import { messagePtBR } from './pt-br.js';

export class ApiError extends Error {
  constructor(status, message) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

const isMutation = method => !['GET', 'HEAD', 'OPTIONS'].includes(method.toUpperCase());
const responseData = async response => {
  const contentType = response.headers?.get?.('content-type') || '';
  return contentType.includes('json') ? response.json() : response.text();
};
const errorMessage = data => {
  const message = typeof data === 'string' ? data : data?.detail?.code || data?.detail || data?.error || JSON.stringify(data);
  return messagePtBR(message);
};
const cookieValue = (documentRef, name) => (documentRef?.cookie || '')
  .split('; ')
  .find(cookie => cookie.startsWith(`${name}=`))
  ?.split('=')[1] || '';

export function createApi({ fetchImpl, documentRef, operationId, csrfState } = {}) {
  let csrf = '';
  let unauthorizedHandler = () => {};
  const mutationsInFlight = new Map();
  const fetchFor = () => fetchImpl || globalThis.fetch;
  const documentFor = () => documentRef || globalThis.document;
  const getCsrf = () => csrfState?.get?.() ?? csrf;
  const setCsrf = value => {
    if (csrfState?.set) csrfState.set(value || '');
    else csrf = value || '';
  };
  const newOperationId = () => operationId?.()
    || globalThis.crypto?.randomUUID?.()
    || `op-${Date.now()}-${Math.random().toString(16).slice(2)}`;

  const request = (path, options = {}) => {
    const method = (options.method || 'GET').toUpperCase();
    const mutationKey = isMutation(method) ? `${method} ${path} ${typeof options.body === 'string' ? options.body : ''}` : '';
    if (mutationKey && mutationsInFlight.has(mutationKey)) return mutationsInFlight.get(mutationKey);
    const promise = (async () => {
      const headers = { 'Content-Type': 'application/json', ...(options.headers || {}) };
      if (isMutation(method) && getCsrf()) {
        headers['X-CSRF-Token'] = getCsrf();
        if (!headers['X-Operation-ID']) headers['X-Operation-ID'] = newOperationId();
      }
      const response = await fetchFor()(`/api/v1${path}`, { ...options, method, headers });
      const data = await responseData(response);
      if (response.status === 401) {
        setCsrf('');
        unauthorizedHandler();
        throw new ApiError(401, 'Sessão encerrada');
      }
      if (!response.ok) throw new ApiError(response.status, errorMessage(data));
      return data;
    })();
    if (mutationKey) {
      mutationsInFlight.set(mutationKey, promise);
      promise.finally(() => mutationsInFlight.delete(mutationKey)).catch(() => {});
    }
    return promise;
  };

  const acquireCsrf = async () => {
    const response = await fetchFor()('/api/v1/auth/csrf');
    const data = await responseData(response);
    if (!response.ok) throw new ApiError(response.status, errorMessage(data));
    setCsrf(data.csrf);
    return getCsrf();
  };

  const requestForm = (path, form, method = 'POST') => {
    const mutationKey = `${method.toUpperCase()} ${path} FORM`;
    if (mutationsInFlight.has(mutationKey)) return mutationsInFlight.get(mutationKey);
    const promise = (async () => {
      const response = await fetchFor()(`/api/v1${path}`, {
        method,
        headers: { 'X-CSRF-Token': getCsrf(), 'X-Operation-ID': newOperationId() },
        body: form,
      });
      const data = await responseData(response);
      if (response.status === 401) {
        setCsrf('');
        unauthorizedHandler();
        throw new ApiError(401, 'Sessão encerrada');
      }
      if (!response.ok) throw new ApiError(response.status, errorMessage(data));
      return data;
    })();
    mutationsInFlight.set(mutationKey, promise);
    promise.finally(() => mutationsInFlight.delete(mutationKey)).catch(() => {});
    return promise;
  };

  const client = (path, options) => request(path, options);
  return Object.assign(client, {
    request,
    requestForm,
    acquireCsrf,
    syncCsrfFromCookie: () => {
      setCsrf(cookieValue(documentFor(), 'us_csrf'));
      return getCsrf();
    },
    setCsrf,
    getCsrf,
    clearCsrf: () => setCsrf(''),
    onUnauthorized: handler => { unauthorizedHandler = handler || (() => {}); },
  });
}

export const api = createApi();

