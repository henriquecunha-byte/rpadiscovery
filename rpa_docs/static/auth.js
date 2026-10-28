/* UI contract only. Authentication is unavailable until the server provider is implemented. */
(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const authRoute = () => ['#login', '#forgot-password'].includes(location.hash);
  const state = {config: null, user: null, ready: false, busy: false, revision: 0, error: '', operation: 0};
  let requestController = null;
  let sessionRefresh = null;
  let returnRoute = /^#(new|history|settings|job=[a-zA-Z0-9_-]+)$/.test(location.hash) ? location.hash : '#new';
  let resolveReady;
  const ready = new Promise(resolve => { resolveReady = resolve; });
  const allowed = () => state.ready && !!state.config && (state.config.can_continue_local === true && state.config.mode === 'local' || state.config.enabled === true && !!state.user);
  const canAccess = () => allowed() && !authRoute();
  const emit = (reason, clear = false) => {
    state.revision++;
    window.dispatchEvent(new CustomEvent('discovery:authchange', {detail: {access: canAccess(), clear, reason}}));
  };

  async function request(path, body, signal = requestController?.signal) {
    const response = await fetch('/api/auth/' + path, {
      method: body === undefined ? 'GET' : 'POST', credentials: 'same-origin', cache: 'no-store',
      headers: body === undefined ? {} : {'Content-Type': 'application/json'},
      ...(body === undefined ? {} : {body: JSON.stringify(body)}), signal,
    });
    let data;
    try { data = await response.json(); } catch { throw new Error('O serviço de acesso não respondeu como esperado. Tente novamente.'); }
    if (!response.ok) {
      // Never display an arbitrary provider error that might echo credentials.
      const message = data?.code === 'auth_not_configured'
        ? 'O login ainda não está disponível. A integração com o Supabase precisa ser concluída.'
        : response.status === 401 ? 'E-mail ou senha inválidos. Confira os dados e tente novamente.'
        : response.status === 429 ? 'Muitas tentativas. Aguarde um pouco antes de tentar novamente.'
        : 'Não foi possível concluir a solicitação. Tente novamente em instantes.';
      throw new Error(message);
    }
    return data;
  }

  function status(message, isError = false) {
    $('authMessage').textContent = message;
    $('authMessage').className = isError ? 'notice error auth-message' : 'notice subtle auth-message';
    $('authMessage').hidden = !message;
  }
  function render() {
    const inAuth = authRoute() || !allowed();
    const recovery = location.hash === '#forgot-password';
    document.body.classList.toggle('auth-screen', inAuth);
    document.body.classList.remove('auth-loading');
    $('authView').hidden = !inAuth;
    document.querySelector('.skip-link').setAttribute('href', inAuth ? '#authMain' : '#main');
    $('loginForm').hidden = recovery;
    $('recoverForm').hidden = !recovery;
    $('authTitle').textContent = recovery ? 'Recuperar acesso' : 'Entrar no Discovery';
    $('authIntro').textContent = recovery ? 'Informe seu e-mail para solicitar a redefinição da senha.' : 'Acesse o ambiente de trabalho da sua equipe.';
    const enabled = state.ready && state.config?.enabled === true && !state.busy;
    $('loginFields').disabled = !enabled;
    $('recoverFields').disabled = !enabled;
    $('loginSubmit').textContent = state.busy ? 'Entrando…' : 'Entrar';
    $('recoverSubmit').textContent = state.busy ? 'Enviando…' : 'Enviar link de recuperação';
    $('loginForm').setAttribute('aria-busy', String(state.busy));
    $('recoverForm').setAttribute('aria-busy', String(state.busy));
    $('localAccess').hidden = !(state.ready && state.config?.mode === 'local' && state.config?.can_continue_local === true);
    $('continueLocal').disabled = state.busy;
    $('authAvailability').hidden = state.ready && state.config?.enabled === true && !state.error;
    $('authAvailability').classList.toggle('error', !!state.error);
    $('authAvailabilityTitle').textContent = state.error ? 'Não foi possível verificar o acesso' : !state.ready ? 'Verificando ambiente…' : 'Login em preparação';
    $('authAvailabilityText').textContent = state.error || (!state.ready ? 'Aguarde enquanto consultamos a configuração deste ambiente.' : state.config?.mode === 'local' ? 'O acesso por conta será ativado após a integração com o Supabase. Por enquanto, você pode continuar no ambiente local.' : 'Este ambiente exige autenticação. O acesso ficará bloqueado até a integração com o Supabase ser concluída.');
    $('retryAuth').hidden = !state.error;
    $('authAccountHint').textContent = 'O acesso será disponibilizado pela equipe. Não há cadastro público.';
    $('sessionLabel').textContent = state.user ? state.user.email || 'Conta conectada' : 'Modo local · sem autenticação';
    $('sessionLabel').title = $('sessionLabel').textContent;
    $('workspaceAccessMode').textContent = state.user ? 'Conta individual' : 'Ambiente local';
    $('workspacePrivacy').textContent = state.user ? 'Análises e arquivos desta conta.' : 'Sem separação de dados por pessoa.';
    $('logoutButton').textContent = state.user ? 'Sair' : 'Sair do modo local';
    $('logoutButton').disabled = state.busy;
    document.title = inAuth ? (recovery ? 'Recuperar acesso' : 'Entrar') + ' · Discovery · btime' : 'Discovery · btime';
  }

  function syncRoute() {
    state.operation++;
    requestController?.abort();
    state.busy = false;
    $('loginPassword').value = '';
    $('loginPassword').type = 'password';
    $('togglePassword').setAttribute('aria-pressed', 'false');
    $('togglePassword').textContent = 'Mostrar';
    status('');
    if (!authRoute() && !allowed()) {
      if (/^#(new|history|settings|job=[a-zA-Z0-9_-]+)$/.test(location.hash)) returnRoute = location.hash;
      history.replaceState(null, '', '#login');
    }
    render();
    emit('route');
    if (authRoute()) $('authTitle').focus({preventScroll: true});
  }

  async function initialize() {
    const operation = ++state.operation;
    requestController?.abort();
    requestController = new AbortController();
    state.ready = false;
    state.config = null;
    state.user = null;
    state.error = '';
    render();
    emit('checking');
    try {
      const config = await request('config');
      if (!['local', 'required'].includes(config.mode) || typeof config.enabled !== 'boolean') throw new Error('Configuração de acesso inválida. Verifique o servidor.');
      const session = await request('session');
      if (operation !== state.operation) return;
      state.config = config;
      state.user = config.enabled && session.authenticated === true && typeof session.user?.id === 'string' && session.user.id ? {id: session.user.id, email: typeof session.user.email === 'string' ? session.user.email : ''} : null;
    } catch (error) {
      if (operation !== state.operation) return;
      state.error = error.name === 'TypeError' ? 'O servidor está indisponível. Verifique a conexão e tente novamente.' : error.message;
    }
    state.ready = true;
    if (!location.hash) history.replaceState(null, '', '#login');
    syncRoute();
    resolveReady();
  }

  async function submit(event, recovery) {
    event.preventDefault();
    if (!state.config?.enabled || state.busy) return;
    const emailInput = $(recovery ? 'recoverEmail' : 'loginEmail');
    emailInput.value = emailInput.value.trim();
    if (!event.currentTarget.reportValidity()) return;
    const operation = ++state.operation;
    requestController?.abort();
    requestController = new AbortController();
    const body = {email: emailInput.value};
    if (!recovery) body.password = $('loginPassword').value;
    state.busy = true;
    status('');
    render();
    try {
      await request(recovery ? 'recover' : 'login', body);
      if (operation !== state.operation) return;
      if (recovery) {
        status('Se houver uma conta com esse e-mail, você receberá as instruções de recuperação.');
      } else {
        const session = await request('session');
        if (operation !== state.operation) return;
        if (!session.authenticated || typeof session.user?.id !== 'string' || !session.user.id) throw new Error('Não foi possível confirmar a sessão. Tente novamente.');
        state.user = {id: session.user.id, email: typeof session.user.email === 'string' ? session.user.email : ''};
        location.hash = returnRoute;
      }
    } catch (error) {
      if (operation === state.operation) status(error.name === 'TypeError' ? 'Não foi possível conectar. Verifique a rede e tente novamente.' : error.message, true);
    } finally {
      delete body.password;
      if (operation === state.operation) {
        $('loginPassword').value = '';
        state.busy = false;
        render();
      }
    }
  }

  function revoke(reason) {
    state.user = null;
    // A server auth rejection must never fall back to local access.
    if (state.config) state.config = {...state.config, can_continue_local: false, mode: 'required'};
    history.replaceState(null, '', '#login');
    syncRoute();
    emit(reason, true);
    status('Seu acesso precisa ser confirmado. Entre novamente ou verifique a configuração do ambiente.', true);
  }
  // Observe server-confirmed identity changes (for example, another browser tab).
  // Identity is never read from browser storage or sent as an authorization claim.
  function refreshSession() {
    if (sessionRefresh || !state.ready || !state.config?.enabled || !state.user || state.busy)
      return sessionRefresh;
    const checkedUser = state.user;
    sessionRefresh = (async () => {
      try {
        const session = await request('session', undefined, new AbortController().signal);
        if (state.user !== checkedUser) return;
        if (!session.authenticated || typeof session.user?.id !== 'string' || !session.user.id) {
          revoke('expired');
          return;
        }
        const user = {id: session.user.id, email: typeof session.user.email === 'string' ? session.user.email : ''};
        if (user.id !== state.user?.id || user.email !== state.user?.email) {
          state.user = user;
          render();
          emit('identity');
        }
      } catch (error) {
        if (state.user === checkedUser && error.name !== 'AbortError') revoke('session-unavailable');
      } finally {
        sessionRefresh = null;
      }
    })();
    return sessionRefresh;
  }
  window.DiscoveryAuth = {
    ready, canAccess, get revision() { return state.revision; },
    get accountKey() { return allowed() ? (state.user ? 'user:' + state.user.id : 'local') : null; },
    get canPersistLocal() { return state.ready && !state.user && state.config?.mode === 'local' && state.config.can_continue_local === true; },
    handleResponse(response, body) {
      const rejected = response.status === 401 || [403, 503].includes(response.status) && typeof body?.code === 'string' && body.code.startsWith('auth_');
      if (rejected) revoke('expired');
      return rejected;
    },
  };
  $('loginForm').addEventListener('submit', event => submit(event, false));
  $('recoverForm').addEventListener('submit', event => submit(event, true));
  $('togglePassword').addEventListener('click', () => {
    const reveal = $('loginPassword').type === 'password';
    $('loginPassword').type = reveal ? 'text' : 'password';
    $('togglePassword').textContent = reveal ? 'Ocultar' : 'Mostrar';
    $('togglePassword').setAttribute('aria-pressed', String(reveal));
  });
  $('continueLocal').addEventListener('click', () => {
    if (state.config?.mode === 'local' && state.config.can_continue_local === true) location.hash = returnRoute;
  });
  $('retryAuth').addEventListener('click', initialize);
  document.querySelector('.skip-link').addEventListener('click', event => {
    event.preventDefault();
    $(canAccess() ? 'main' : 'authMain').focus();
  });
  $('logoutButton').addEventListener('click', async () => {
    if (state.busy) return;
    const operation = ++state.operation;
    requestController?.abort();
    requestController = new AbortController();
    state.busy = true;
    state.user = null;
    history.replaceState(null, '', '#login');
    emit('logout', true);
    render();
    $('loginForm').reset();
    $('recoverForm').reset();
    $('authTitle').focus({preventScroll: true});
    try {
      await request('logout', {});
      if (operation === state.operation) status('Você saiu deste ambiente. As análises em andamento continuam no servidor.');
    } catch {
      if (operation === state.operation) status('Os dados foram ocultados neste navegador, mas não foi possível confirmar a saída no servidor. Tente novamente antes de compartilhar o dispositivo.', true);
    } finally {
      if (operation === state.operation) { state.busy = false; render(); emit('logout'); }
    }
  });
  window.addEventListener('hashchange', () => {
    // Do not abort the configuration request if the initial URL changes while it loads.
    if (state.ready) syncRoute();
  });
  window.addEventListener('focus', refreshSession);
  document.addEventListener('visibilitychange', () => { if (!document.hidden) refreshSession(); });
  initialize();
})();
