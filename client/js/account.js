/* ─── Account Settings Page ─────────────────────────────
 *  Handles:
 *    - Loading and displaying profile info
 *    - Updating display name
 *    - Changing password (with strength meter)
 *    - Sign out
 *    - Delete account (with confirmation modal)
 * ────────────────────────────────────────────────────── */

'use strict';

// ── Auth helpers ───────────────────────────────────────
const Auth = {
  getToken()  { return localStorage.getItem('cc_token'); },
  getUser()   { try { return JSON.parse(localStorage.getItem('cc_user')); } catch { return null; } },
  isLoggedIn(){ return !!this.getToken() && !!this.getUser(); },
  headers()   {
    return {
      'Content-Type': 'application/json',
      'Authorization': 'Bearer ' + this.getToken(),
    };
  },
  saveUser(u) { localStorage.setItem('cc_user', JSON.stringify(u)); },
  clear()     { localStorage.removeItem('cc_token'); localStorage.removeItem('cc_user'); },
};

// ── Toast ──────────────────────────────────────────────
function showToast(msg, type = 'success') {
  const c = document.getElementById('toast-container');
  const t = document.createElement('div');
  t.className = 'toast ' + type;
  t.textContent = msg;
  c.appendChild(t);
  setTimeout(() => t.remove(), 4000);
}

// ── Gate: login required ───────────────────────────────
if (!Auth.isLoggedIn()) {
  document.getElementById('dashboard').style.display = 'none';
  document.getElementById('login-required').style.display = '';
} else {
  init();
}

// ── Init ───────────────────────────────────────────────
async function init() {
  loadLocalUser();
  await loadRemoteProfile();
  loadStoryCount();
  wireProfileForm();
  wirePasswordForm();
  wirePasswordToggles();
  wireDeleteAccount();
  wireSignOut();
}

// ── Load from localStorage immediately (fast paint) ───
function loadLocalUser() {
  const u = Auth.getUser();
  if (!u) return;
  document.getElementById('stat-name').textContent  = u.name  || '—';
  document.getElementById('stat-email').textContent = u.email || '—';
  document.getElementById('email-display-val').textContent = u.email || '—';
  document.getElementById('input-name').value = u.name || '';
}

// ── Fetch fresh profile from server ───────────────────
async function loadRemoteProfile() {
  try {
    const res = await fetch('/api/auth/me', { headers: Auth.headers() });
    if (!res.ok) return;
    const user = await res.json();
    Auth.saveUser(user);

    document.getElementById('stat-name').textContent  = user.name  || '—';
    document.getElementById('stat-email').textContent = user.email || '—';
    document.getElementById('email-display-val').textContent = user.email || '—';
    document.getElementById('input-name').value = user.name || '';

    const joined = user.createdAt
      ? new Date(user.createdAt).toLocaleDateString('en-US', { month: 'short', year: 'numeric' })
      : '—';
    document.getElementById('stat-joined').textContent = joined;

    const lastLogin = user.lastLogin
      ? new Date(user.lastLogin).toLocaleString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
      : 'Never';
    document.getElementById('stat-last-login').textContent = lastLogin;

    // Hide password section for Google-only accounts
    if (user.isGoogleUser) {
      const pwSection = document.getElementById('pw-section');
      if (pwSection) {
        pwSection.innerHTML = `
          <h2>
            <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none"
              stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"
              style="vertical-align:middle;color:var(--primary);margin-right:.4rem">
              <rect x="3" y="11" width="18" height="11" rx="2" ry="2"/>
              <path d="M7 11V7a5 5 0 0 1 10 0v4"/>
            </svg>
            Password
          </h2>
          <div style="display:flex;align-items:center;gap:.875rem;margin-top:1rem;padding:1rem 1.25rem;
            background:rgba(56,189,248,.06);border:1.5px solid rgba(56,189,248,.2);border-radius:1rem">
            <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none"
              stroke="#38bdf8" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="flex-shrink:0">
              <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/>
              <line x1="12" y1="16" x2="12.01" y2="16"/>
            </svg>
            <p style="font-size:.9rem;color:var(--muted-fg);margin:0">
              Your account uses <strong style="color:var(--foreground)">Google Sign-In</strong>.
              Password-based login is not available for this account.
            </p>
          </div>`;
      }
    }
  } catch { /* network error — cached data is shown */ }
}

// ── Story count from credits API ───────────────────────
async function loadStoryCount() {
  try {
    const res = await fetch('/api/credits/my', { headers: Auth.headers() });
    if (!res.ok) return;
    const data = await res.json();
    const count = data.stories_generated != null ? data.stories_generated : 0;
    document.getElementById('stat-stories').textContent = count;
  } catch {
    document.getElementById('stat-stories').textContent = '—';
  }
}

// ── Profile form ───────────────────────────────────────
function wireProfileForm() {
  const btn = document.getElementById('btn-save-name');
  btn.addEventListener('click', async () => {
    const name = document.getElementById('input-name').value.trim();
    if (!name || name.length < 2) {
      showToast('Name must be at least 2 characters', 'error');
      return;
    }
    setLoading(btn, true, 'Saving...');
    try {
      const res = await fetch('/api/auth/profile', {
        method: 'PATCH',
        headers: Auth.headers(),
        body: JSON.stringify({ name }),
      });
      const data = await res.json();
      if (!res.ok) { showToast(data.message || 'Failed to update name', 'error'); return; }
      Auth.saveUser(data.user);
      document.getElementById('stat-name').textContent = data.user.name;
      showToast('Display name updated!', 'success');
    } catch {
      showToast('Network error — please try again', 'error');
    } finally {
      setLoading(btn, false, 'Save Changes');
    }
  });
}

// ── Password form ──────────────────────────────────────
function wirePasswordForm() {
  const newPwInput     = document.getElementById('input-new-pw');
  const confirmInput   = document.getElementById('input-confirm-pw');
  const matchHint      = document.getElementById('pw-match-hint');
  const strengthWrap   = document.getElementById('pw-strength-wrap');
  const strengthFill   = document.getElementById('pw-strength-fill');
  const strengthLabel  = document.getElementById('pw-strength-label');
  const btn            = document.getElementById('btn-change-pw');

  // Live strength meter
  newPwInput.addEventListener('input', () => {
    const pw = newPwInput.value;
    if (!pw) { strengthWrap.style.display = 'none'; return; }
    strengthWrap.style.display = 'flex';
    const score = passwordStrength(pw);
    const levels = [
      { pct: 25,  color: '#ef4444', label: 'Weak' },
      { pct: 50,  color: '#f59e0b', label: 'Fair' },
      { pct: 75,  color: '#3b82f6', label: 'Good' },
      { pct: 100, color: '#10b981', label: 'Strong' },
    ];
    const lvl = levels[Math.min(score - 1, 3)];
    strengthFill.style.width    = lvl.pct + '%';
    strengthFill.style.background = lvl.color;
    strengthLabel.textContent   = lvl.label;
    strengthLabel.style.color   = lvl.color;
  });

  // Live match check
  confirmInput.addEventListener('input', () => {
    const match = newPwInput.value === confirmInput.value;
    matchHint.style.display = confirmInput.value ? '' : 'none';
    matchHint.textContent   = match ? 'Passwords match' : 'Passwords do not match';
    matchHint.style.color   = match ? '#10b981' : '#ef4444';
    matchHint.style.fontWeight = '700';
  });

  btn.addEventListener('click', async () => {
    const currentPw = document.getElementById('input-current-pw').value;
    const newPw     = newPwInput.value;
    const confirmPw = confirmInput.value;

    if (!currentPw) { showToast('Enter your current password', 'error'); return; }
    if (newPw.length < 8) { showToast('New password must be at least 8 characters', 'error'); return; }
    if (newPw !== confirmPw) { showToast('Passwords do not match', 'error'); return; }

    setLoading(btn, true, 'Updating...');
    try {
      const res = await fetch('/api/auth/change-password', {
        method: 'POST',
        headers: Auth.headers(),
        body: JSON.stringify({ current_password: currentPw, new_password: newPw }),
      });
      const data = await res.json();
      if (!res.ok) { showToast(data.message || 'Failed to update password', 'error'); return; }
      showToast('Password updated successfully!', 'success');
      document.getElementById('input-current-pw').value = '';
      newPwInput.value = '';
      confirmInput.value = '';
      strengthWrap.style.display = 'none';
      matchHint.style.display = 'none';
    } catch {
      showToast('Network error — please try again', 'error');
    } finally {
      setLoading(btn, false, 'Update Password');
    }
  });
}

// ── Password toggle (show/hide) ────────────────────────
function wirePasswordToggles() {
  document.querySelectorAll('.pw-toggle').forEach(btn => {
    btn.addEventListener('click', () => {
      const input = document.getElementById(btn.dataset.target);
      const isText = input.type === 'text';
      input.type = isText ? 'password' : 'text';
      // Swap eye icon
      btn.querySelector('.eye-icon').innerHTML = isText
        ? '<path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/>'
        : '<path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94"/>' +
          '<path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19"/>' +
          '<line x1="1" y1="1" x2="23" y2="23"/>';
    });
  });
}

// ── Sign out ───────────────────────────────────────────
function wireSignOut() {
  document.getElementById('btn-logout-all').addEventListener('click', () => {
    Auth.clear();
    window.location.href = '/login';
  });
}

// ── Delete account modal ───────────────────────────────
function wireDeleteAccount() {
  const overlay    = document.getElementById('delete-modal');
  const openBtn    = document.getElementById('btn-delete-account');
  const cancelBtn  = document.getElementById('modal-cancel');
  const confirmBtn = document.getElementById('modal-confirm-delete');
  const pwInput    = document.getElementById('modal-pw-input');
  const spinner    = document.getElementById('modal-spinner');

  openBtn.addEventListener('click', () => {
    pwInput.value = '';
    overlay.style.display = 'flex';
    setTimeout(() => pwInput.focus(), 100);
  });

  cancelBtn.addEventListener('click', closeModal);

  overlay.addEventListener('click', (e) => {
    if (e.target === overlay) closeModal();
  });

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && overlay.style.display !== 'none') closeModal();
  });

  confirmBtn.addEventListener('click', async () => {
    const password = pwInput.value;
    if (!password) { showToast('Enter your password to confirm', 'error'); return; }

    spinner.style.display = '';
    confirmBtn.disabled = true;
    cancelBtn.disabled  = true;

    try {
      const res = await fetch('/api/auth/account', {
        method: 'DELETE',
        headers: Auth.headers(),
        body: JSON.stringify({ password }),
      });
      const data = await res.json();
      if (!res.ok) {
        showToast(data.message || 'Failed to delete account', 'error');
        return;
      }
      Auth.clear();
      showToast('Account deleted. Goodbye!', 'info');
      setTimeout(() => { window.location.href = '/login'; }, 1500);
    } catch {
      showToast('Network error — please try again', 'error');
    } finally {
      spinner.style.display = 'none';
      confirmBtn.disabled = false;
      cancelBtn.disabled  = false;
    }
  });

  function closeModal() {
    overlay.style.display = 'none';
    pwInput.value = '';
  }
}

// ── Password strength scorer (0-4) ────────────────────
function passwordStrength(pw) {
  let score = 0;
  if (pw.length >= 8)  score++;
  if (pw.length >= 12) score++;
  if (/[A-Z]/.test(pw) && /[a-z]/.test(pw)) score++;
  if (/[0-9]/.test(pw)) score++;
  if (/[^A-Za-z0-9]/.test(pw)) score++;
  // Clamp to 1-4
  return Math.max(1, Math.min(4, Math.ceil(score * 4 / 5)));
}

// ── Loading state helper ───────────────────────────────
function setLoading(btn, loading, label) {
  btn.disabled = loading;
  if (loading) {
    btn.dataset.originalHtml = btn.innerHTML;
    btn.innerHTML = `<span class="spinner" style="width:1rem;height:1rem;border-width:2px"></span>${label}`;
  } else {
    btn.innerHTML = btn.dataset.originalHtml || label;
  }
}
