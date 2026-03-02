/* ─── Auth page logic ─────────────────────────────────── */

// ── Toast ──────────────────────────────────────────────
function showToast(msg, type = 'error') {
  const c = document.getElementById('toast-container');
  const t = document.createElement('div');
  t.className = `toast ${type}`;
  t.textContent = msg;
  c.appendChild(t);
  setTimeout(() => t.remove(), 4000);
}

// ── Token helpers (shared with other pages via auth-helpers) ────
const Auth = {
  getToken()  { return localStorage.getItem('cc_token'); },
  setToken(t) { localStorage.setItem('cc_token', t); },
  getUser()   { try { return JSON.parse(localStorage.getItem('cc_user')); } catch { return null; } },
  setUser(u)  { localStorage.setItem('cc_user', JSON.stringify(u)); },
  clear()     { localStorage.removeItem('cc_token'); localStorage.removeItem('cc_user'); },
  isLoggedIn(){ return !!this.getToken(); },
  headers()   {
    const h = { 'Content-Type': 'application/json' };
    const t = this.getToken();
    if (t) h['Authorization'] = `Bearer ${t}`;
    return h;
  },
};

// ── Redirect if already logged in ─────────────────────
if (Auth.isLoggedIn()) {
  window.location.href = '/';
}

// ── Tab switching ─────────────────────────────────────
const tabs = document.querySelectorAll('[data-tab]');
const loginForm  = document.getElementById('login-form');
const signupForm = document.getElementById('signup-form');
const tabLogin   = document.getElementById('tab-login');
const tabSignup  = document.getElementById('tab-signup');

function switchTab(tab) {
  if (tab === 'login') {
    loginForm.classList.remove('hidden');
    signupForm.classList.add('hidden');
    tabLogin.classList.add('active');
    tabSignup.classList.remove('active');
  } else {
    signupForm.classList.remove('hidden');
    loginForm.classList.add('hidden');
    tabSignup.classList.add('active');
    tabLogin.classList.remove('active');
  }
}

tabs.forEach(el => {
  el.addEventListener('click', () => switchTab(el.dataset.tab));
});

// Check URL hash for initial tab
if (window.location.hash === '#signup') switchTab('signup');

// ── Password toggle ───────────────────────────────────
document.querySelectorAll('.password-toggle').forEach(btn => {
  btn.addEventListener('click', () => {
    const input = document.getElementById(btn.dataset.target);
    const isPass = input.type === 'password';
    input.type = isPass ? 'text' : 'password';
    btn.querySelector('.eye-open').classList.toggle('hidden', !isPass);
    btn.querySelector('.eye-closed').classList.toggle('hidden', isPass);
  });
});

// ── Login ─────────────────────────────────────────────
loginForm.addEventListener('submit', async (e) => {
  e.preventDefault();
  const email    = document.getElementById('login-email').value.trim();
  const password = document.getElementById('login-password').value;
  const btn      = document.getElementById('login-btn');
  const spinner  = document.getElementById('login-spinner');

  if (!email || !password) { showToast('Please fill in all fields'); return; }

  btn.disabled = true;
  spinner.classList.remove('hidden');
  btn.querySelector('.btn-text').textContent = 'Signing in…';

  try {
    const res = await fetch('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    });
    const data = await res.json();

    if (!res.ok) {
      throw new Error(data.message || 'Login failed');
    }

    Auth.setToken(data.token);
    Auth.setUser(data.user);
    showToast('Welcome back!', 'success');

    // Redirect to original page or home
    const redirect = new URLSearchParams(window.location.search).get('redirect') || '/';
    setTimeout(() => { window.location.href = redirect; }, 500);

  } catch (err) {
    showToast(err.message);
    btn.disabled = false;
    spinner.classList.add('hidden');
    btn.querySelector('.btn-text').textContent = 'Login';
  }
});

// ── Signup ────────────────────────────────────────────
signupForm.addEventListener('submit', async (e) => {
  e.preventDefault();
  const name     = document.getElementById('signup-name').value.trim();
  const email    = document.getElementById('signup-email').value.trim();
  const password = document.getElementById('signup-password').value;
  const confirm  = document.getElementById('signup-confirm').value;
  const btn      = document.getElementById('signup-btn');
  const spinner  = document.getElementById('signup-spinner');

  if (!name || !email || !password || !confirm) { showToast('Please fill in all fields'); return; }
  if (password.length < 8) { showToast('Password must be at least 8 characters'); return; }
  if (password !== confirm) { showToast('Passwords do not match'); return; }

  btn.disabled = true;
  spinner.classList.remove('hidden');
  btn.querySelector('.btn-text').textContent = 'Creating account…';

  try {
    const res = await fetch('/api/auth/register', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, email, password }),
    });
    const data = await res.json();

    if (!res.ok) {
      throw new Error(data.message || 'Registration failed');
    }

    Auth.setToken(data.token);
    Auth.setUser(data.user);
    showToast('Account created! Welcome!', 'success');

    const redirect = new URLSearchParams(window.location.search).get('redirect') || '/';
    setTimeout(() => { window.location.href = redirect; }, 500);

  } catch (err) {
    showToast(err.message);
    btn.disabled = false;
    spinner.classList.add('hidden');
    btn.querySelector('.btn-text').textContent = 'Create Account';
  }
});
