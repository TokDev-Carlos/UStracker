import { api as defaultApi } from './api.js';

export function createSession({ api = defaultApi, onUserChange } = {}) {
  let user = null;
  const notify = onUserChange || (() => {});
  const setUser = nextUser => {
    user = nextUser;
    notify(user);
    return user;
  };
  const clear = () => {
    api.clearCsrf?.();
    return setUser(null);
  };

  api.onUnauthorized?.(clear);

  const bootstrap = async () => {
    const publicData = await api.request('/public');
    const setupStatus = await api.request('/auth/setup-status');
    if (setupStatus.enrolled === 0) {
      clear();
      return { state: 'setup', publicData, setupStatus };
    }
    try {
      const authenticatedUser = await api.request('/auth/me');
      api.syncCsrfFromCookie?.();
      setUser(authenticatedUser);
      return { state: 'authenticated', publicData, setupStatus, user: authenticatedUser };
    } catch (error) {
      if (error?.status === 401) return { state: 'login', publicData, setupStatus };
      throw error;
    }
  };

  const authenticate = authenticatedUser => {
    if (authenticatedUser?.csrf) api.setCsrf?.(authenticatedUser.csrf);
    return setUser(authenticatedUser);
  };
  const logout = async () => {
    const result = await api.request('/auth/logout', { method: 'POST', body: '{}' });
    clear();
    return result;
  };

  return {
    bootstrap,
    refresh: bootstrap,
    authenticate,
    logout,
    clear,
    get user() { return user; },
  };
}
