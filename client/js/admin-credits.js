/* ─── Admin Credit Dashboard ──────────────────────────── */

const Auth = {
  getToken()  { return localStorage.getItem('cc_token'); },
  getUser()   { try { return JSON.parse(localStorage.getItem('cc_user')); } catch { return null; } },
  isLoggedIn(){ return !!this.getToken(); },
  headers()   {
    const h = { 'Content-Type': 'application/json' };
    const t = this.getToken();
    if (t) h['Authorization'] = `Bearer ${t}`;
    return h;
  },
};

// ── Toast ──────────────────────────────────────────────
function showToast(msg, type = 'success') {
  const c = document.getElementById('toast-container');
  const t = document.createElement('div');
  t.className = `toast ${type}`;
  t.textContent = msg;
  c.appendChild(t);
  setTimeout(() => t.remove(), 4000);
}

// ── Init ───────────────────────────────────────────────
(async function init() {
  if (!Auth.isLoggedIn()) {
    document.getElementById('dashboard').style.display = 'none';
    document.getElementById('login-required').style.display = '';
    return;
  }
  // Check admin access
  try {
    const res = await fetch('/api/admin/credits/overview', { headers: Auth.headers() });
    if (res.status === 403) {
      document.getElementById('dashboard').style.display = 'none';
      document.getElementById('access-denied').style.display = '';
      return;
    }
    if (res.status === 401) {
      document.getElementById('dashboard').style.display = 'none';
      document.getElementById('login-required').style.display = '';
      return;
    }
    const data = await res.json();
    renderStats(data);
    renderBudget(data);
    renderApiBreakdown(data);
  } catch (e) {
    console.error('Failed to load admin overview:', e);
  }

  loadHistory();
  loadUsers();
  loadConfig();
  loadFeedback();
  loadPerformance();
})();

async function loadAll() {
  const btn = document.getElementById('refresh-btn');
  btn.classList.add('loading');
  try {
    const res = await fetch('/api/admin/credits/overview', { headers: Auth.headers() });
    const data = await res.json();
    renderStats(data);
    renderBudget(data);
    renderApiBreakdown(data);
    await Promise.all([loadHistory(), loadUsers(), loadFeedback(), loadPerformance()]);
    showToast('Dashboard refreshed');
  } catch (e) {
    showToast('Refresh failed', 'error');
  } finally {
    btn.classList.remove('loading');
  }
}

// ── Stat Cards ─────────────────────────────────────────
function renderStats(data) {
  const row = document.getElementById('stats-row');
  const flux = data.by_api.flux2pro || {};
  const claude = data.by_api.claude || {};
  const totalCalls = (flux.total_calls || 0) + (claude.total_calls || 0);
  const successRate = totalCalls > 0
    ? Math.round(((flux.successes || 0) + (claude.successes || 0)) / totalCalls * 100) : 0;

  row.innerHTML = `
    <div class="stat-card purple">
      <div class="stat-icon purple">
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
          <rect x="2" y="5" width="20" height="14" rx="2"/><line x1="2" y1="10" x2="22" y2="10"/>
        </svg>
      </div>
      <div class="stat-label">Total Credits Used</div>
      <div class="stat-value">$${data.total_used.toFixed(2)}</div>
      <div class="stat-sub">${totalCalls} total API calls</div>
    </div>

    <div class="stat-card green">
      <div class="stat-icon green">
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
          <line x1="12" y1="1" x2="12" y2="23"/><path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/>
        </svg>
      </div>
      <div class="stat-label">Remaining Balance</div>
      <div class="stat-value">$${data.remaining.toFixed(2)}</div>
      <div class="stat-sub">${data.usage_percent.toFixed(1)}% of budget used</div>
    </div>

    <div class="stat-card amber">
      <div class="stat-icon amber">
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
          <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/>
        </svg>
      </div>
      <div class="stat-label">Flux 2 Pro</div>
      <div class="stat-value">${flux.total_calls || 0}</div>
      <div class="stat-sub">$${(flux.total_credits || 0).toFixed(2)} credits · ${flux.successes || 0} success</div>
    </div>

    <div class="stat-card blue">
      <div class="stat-icon blue">
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
          <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>
        </svg>
      </div>
      <div class="stat-label">Claude</div>
      <div class="stat-value">${claude.total_calls || 0}</div>
      <div class="stat-sub">$${(claude.total_credits || 0).toFixed(2)} credits · ${claude.successes || 0} success</div>
    </div>

    <div class="stat-card rose">
      <div class="stat-icon rose">
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
          <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/>
        </svg>
      </div>
      <div class="stat-label">Success Rate</div>
      <div class="stat-value">${successRate}%</div>
      <div class="stat-sub">${(flux.failures || 0) + (claude.failures || 0)} failures total</div>
    </div>
  `;
}

// ── Budget Bar ─────────────────────────────────────────
function renderBudget(data) {
  const section = document.getElementById('budget-section');
  section.style.display = '';
  document.getElementById('budget-used-label').textContent = `$${data.total_used.toFixed(2)} used`;
  document.getElementById('budget-total-label').textContent = `$${data.total_budget.toFixed(2)} budget`;
  const fill = document.getElementById('budget-fill');
  const pct = Math.min(data.usage_percent, 100);
  fill.style.width = pct + '%';
  fill.className = 'progress-bar-fill' +
    (pct >= 90 ? ' danger' : pct >= 70 ? ' warning' : '');
}

// ── API Breakdown ──────────────────────────────────────
function renderApiBreakdown(data) {
  const el = document.getElementById('api-breakdown');
  const apis = data.by_api;
  if (!Object.keys(apis).length) {
    el.innerHTML = `<div class="empty-state"><p>No API usage recorded yet</p></div>`;
    return;
  }

  let html = '';
  for (const [name, info] of Object.entries(apis)) {
    const successPct = info.total_calls > 0
      ? Math.round(info.successes / info.total_calls * 100) : 0;
    const colorCls = name === 'flux2pro' ? 'purple' : name === 'claude' ? 'blue' : 'amber';
    html += `
      <div style="margin-bottom:1.25rem;padding:1rem;background:rgba(124,58,237,.02);border-radius:var(--radius-sm)">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:.5rem">
          <span class="badge badge-${colorCls}" style="font-size:.75rem">${name.toUpperCase()}</span>
          <span class="credit-num" style="font-size:1.1rem">$${(info.total_credits || 0).toFixed(2)}</span>
        </div>
        <div style="display:flex;gap:1.5rem;font-size:.8rem;color:var(--muted-fg)">
          <span>${info.total_calls} calls</span>
          <span>${info.successes} ok</span>
          <span>${info.failures} fail</span>
          <span>${successPct}% success</span>
        </div>
        <div class="progress-bar" style="margin-top:.5rem;height:.35rem">
          <div class="progress-bar-fill" style="width:${successPct}%"></div>
        </div>
      </div>`;
  }
  el.innerHTML = html;
}

// ── History Chart ──────────────────────────────────────
async function loadHistory() {
  try {
    const res = await fetch('/api/admin/credits/history?days=14', { headers: Auth.headers() });
    const { history } = await res.json();
    renderHistoryChart(history);
  } catch (e) {
    console.error('Failed to load history:', e);
  }
}

function renderHistoryChart(history) {
  const container = document.getElementById('history-chart');
  if (!history.length) {
    container.innerHTML = `<div class="empty-state"><p>No usage history yet</p><p class="hint">Generate some stories to see data here</p></div>`;
    return;
  }

  // Group by date
  const byDate = {};
  history.forEach(h => {
    if (!byDate[h.date]) byDate[h.date] = {};
    byDate[h.date][h.api_name] = h.credits;
  });

  const dates = Object.keys(byDate).sort();
  const maxCredits = Math.max(...dates.map(d => {
    const v = byDate[d];
    return (v.flux2pro || 0) + (v.claude || 0);
  }), 0.01);

  let barsHtml = '';
  dates.forEach(date => {
    const d = byDate[date];
    const fluxH = ((d.flux2pro || 0) / maxCredits * 170);
    const claudeH = ((d.claude || 0) / maxCredits * 170);
    const shortDate = date.slice(5); // MM-DD
    barsHtml += `
      <div class="chart-bar-col">
        <div style="display:flex;gap:2px;align-items:flex-end;height:100%">
          <div class="chart-bar flux" style="height:${Math.max(fluxH, 2)}px"
               data-tooltip="Flux: $${(d.flux2pro || 0).toFixed(3)}"></div>
          <div class="chart-bar claude" style="height:${Math.max(claudeH, 2)}px"
               data-tooltip="Claude: $${(d.claude || 0).toFixed(3)}"></div>
        </div>
        <div class="chart-bar-label">${shortDate}</div>
      </div>`;
  });

  container.innerHTML = `<div class="chart-bar-group">${barsHtml}</div>`;
}

// ── User Table ─────────────────────────────────────────
async function loadUsers() {
  try {
    const res = await fetch('/api/admin/credits/by-user', { headers: Auth.headers() });
    const { users } = await res.json();
    renderUsersTable(users);
  } catch (e) {
    console.error('Failed to load users:', e);
  }
}

function renderUsersTable(users) {
  const tbody = document.getElementById('users-tbody');
  if (!users.length) {
    tbody.innerHTML = `<tr><td colspan="6"><div class="empty-state"><p>No user activity yet</p></div></td></tr>`;
    return;
  }

  tbody.innerHTML = users.map(u => {
    const initial = (u.user_name || 'A')[0].toUpperCase();
    const lastAct = u.last_activity ? new Date(u.last_activity).toLocaleDateString() : '—';
    return `
      <tr>
        <td>
          <div class="user-cell">
            <div class="user-avatar-sm">${initial}</div>
            <div>
              <div class="user-name">${escHtml(u.user_name)}</div>
              <div class="user-email">${escHtml(u.email)}</div>
            </div>
          </div>
        </td>
        <td>${u.total_calls}</td>
        <td><span class="badge badge-success">${u.successes}</span></td>
        <td class="credit-num">$${(u.total_credits || 0).toFixed(2)}</td>
        <td>${u.active_days}</td>
        <td>${lastAct}</td>
      </tr>`;
  }).join('');
}

// ── Config ─────────────────────────────────────────────
async function loadConfig() {
  try {
    const res = await fetch('/api/admin/credits/config', { headers: Auth.headers() });
    const config = await res.json();
    document.getElementById('cfg-budget').value = config.total_budget || 1000;
    document.getElementById('cfg-flux-cost').value = config.flux2pro_cost_per_image || 0.05;
    document.getElementById('cfg-claude-cost').value = config.claude_cost_per_call || 0.01;
  } catch (e) {
    console.error('Failed to load config:', e);
  }
}

async function saveConfig() {
  try {
    const body = {
      total_budget: parseFloat(document.getElementById('cfg-budget').value),
      flux2pro_cost_per_image: parseFloat(document.getElementById('cfg-flux-cost').value),
      claude_cost_per_call: parseFloat(document.getElementById('cfg-claude-cost').value),
    };
    const res = await fetch('/api/admin/credits/config', {
      method: 'PUT',
      headers: Auth.headers(),
      body: JSON.stringify(body),
    });
    if (res.ok) {
      showToast('Configuration saved');
      loadAll();
    } else {
      const data = await res.json();
      showToast(data.message || 'Save failed', 'error');
    }
  } catch (e) {
    showToast('Save failed', 'error');
  }
}

// ── Helpers ────────────────────────────────────────────
function escHtml(s) {
  const d = document.createElement('div');
  d.textContent = s || '';
  return d.innerHTML;
}

// ── User Feedback ──────────────────────────────────────
async function loadFeedback() {
  try {
    const res = await fetch('/api/admin/feedback', { headers: Auth.headers() });
    if (!res.ok) return;
    const data = await res.json();
    renderFeedbackStats(data);
    renderFeedbackByCondition(data.by_condition || []);
    renderFeedbackTable(data.recent || []);
  } catch (e) {
    console.error('Failed to load feedback:', e);
  }
}

function renderFeedbackStats(data) {
  const o = data.overall || {};
  const total = o.total_reviews || 0;
  const avg = o.avg_rating ? o.avg_rating.toFixed(1) : '—';
  const helpfulYes = o.helpful_yes || 0;
  const helpfulNo = o.helpful_no || 0;
  const helpfulPct = (helpfulYes + helpfulNo) > 0
    ? Math.round(helpfulYes / (helpfulYes + helpfulNo) * 100) : 0;

  document.getElementById('feedback-stats-row').innerHTML = `
    <div class="stat-card purple">
      <div class="stat-icon purple">
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
          <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
        </svg>
      </div>
      <div class="stat-label">Total Reviews</div>
      <div class="stat-value">${total}</div>
      <div class="stat-sub">feedback submissions</div>
    </div>
    <div class="stat-card amber">
      <div class="stat-icon amber">
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
          <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>
        </svg>
      </div>
      <div class="stat-label">Average Rating</div>
      <div class="stat-value">${avg} <span style="font-size:.9rem;color:var(--muted-fg)">/ 5</span></div>
      <div class="stat-sub">star rating average</div>
    </div>
    <div class="stat-card green">
      <div class="stat-icon green">
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
          <path d="M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.28a2 2 0 0 0 2-1.7l1.38-9a2 2 0 0 0-2-2.3H14z"/><path d="M3 14h4"/>
        </svg>
      </div>
      <div class="stat-label">Helpful Rate</div>
      <div class="stat-value">${helpfulPct}%</div>
      <div class="stat-sub">${helpfulYes} yes · ${helpfulNo} no</div>
    </div>
  `;
}

function renderFeedbackByCondition(conditions) {
  const el = document.getElementById('feedback-by-condition');
  if (!conditions.length) {
    el.innerHTML = '';
    return;
  }
  let html = '<h3 style="font-size:1rem;margin-bottom:.75rem;color:var(--foreground)">Ratings by Condition</h3><div style="display:flex;flex-wrap:wrap;gap:.75rem">';
  conditions.forEach(c => {
    const stars = c.avg_rating ? c.avg_rating.toFixed(1) : '—';
    html += `
      <div style="padding:.6rem 1rem;background:rgba(124,58,237,.03);border-radius:.75rem;border:1px solid rgba(124,58,237,.1)">
        <span style="font-weight:700;font-size:.85rem">${escHtml(c.condition)}</span>
        <span style="margin-left:.5rem;color:var(--muted-fg);font-size:.8rem">${stars} ★ (${c.reviews} reviews)</span>
      </div>`;
  });
  el.innerHTML = html + '</div>';
}

function renderFeedbackTable(recent) {
  const tbody = document.getElementById('feedback-tbody');
  if (!recent.length) {
    tbody.innerHTML = '<tr><td colspan="7"><div class="empty-state"><p>No feedback yet</p></div></td></tr>';
    return;
  }
  tbody.innerHTML = recent.map(r => {
    const date = r.created_at ? new Date(r.created_at).toLocaleDateString() : '—';
    const stars = r.star_rating ? '★'.repeat(r.star_rating) + '☆'.repeat(5 - r.star_rating) : '—';
    const helpful = r.is_helpful === 1 ? '👍' : r.is_helpful === 0 ? '👎' : '—';
    return `<tr>
      <td style="font-weight:600">${escHtml(r.story_title || '—')}</td>
      <td><span class="badge badge-purple">${escHtml(r.condition || '—')}</span></td>
      <td style="color:#f59e0b;letter-spacing:1px">${stars}</td>
      <td>${r.emoji_reaction || '—'}</td>
      <td>${helpful}</td>
      <td style="max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${escHtml(r.comment || '—')}</td>
      <td>${date}</td>
    </tr>`;
  }).join('');
}

// ── Performance Monitoring ─────────────────────────────
async function loadPerformance() {
  const btn = document.getElementById('perf-refresh-btn');
  if (btn) btn.classList.add('loading');
  try {
    const res = await fetch('/api/admin/stats', { headers: Auth.headers() });
    if (!res.ok) return;
    const data = await res.json();
    const perf = data.performance || {};
    renderPerfStats(perf);
    renderPerfGeneration(perf.generation_avg || {});
    renderPerfErrors(perf.errors || {});
    renderPerfRecent(perf.recent_generations || []);
  } catch (e) {
    console.error('Failed to load performance:', e);
  } finally {
    if (btn) btn.classList.remove('loading');
  }
}

function renderPerfStats(perf) {
  document.getElementById('perf-stats-row').innerHTML = `
    <div class="stat-card green">
      <div class="stat-icon green">
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>
        </svg>
      </div>
      <div class="stat-label">Uptime</div>
      <div class="stat-value">${escHtml(perf.uptime_human || '—')}</div>
      <div class="stat-sub">${(perf.uptime_seconds || 0).toLocaleString()}s total</div>
    </div>
    <div class="stat-card blue">
      <div class="stat-icon blue">
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
          <rect x="2" y="3" width="20" height="14" rx="2" ry="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/>
        </svg>
      </div>
      <div class="stat-label">Memory Usage</div>
      <div class="stat-value">${perf.memory_mb || 0} MB</div>
      <div class="stat-sub">Python ${escHtml(perf.python_version || '—')}</div>
    </div>
    <div class="stat-card purple">
      <div class="stat-icon purple">
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
          <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>
        </svg>
      </div>
      <div class="stat-label">Total Requests</div>
      <div class="stat-value">${(perf.total_requests || 0).toLocaleString()}</div>
      <div class="stat-sub">since server start</div>
    </div>
    <div class="stat-card ${perf.error_rate_pct > 5 ? 'rose' : 'amber'}">
      <div class="stat-icon ${perf.error_rate_pct > 5 ? 'rose' : 'amber'}">
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
          <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>
        </svg>
      </div>
      <div class="stat-label">Error Rate</div>
      <div class="stat-value">${perf.error_rate_pct || 0}%</div>
      <div class="stat-sub">${(perf.errors || {}).total || 0} errors total</div>
    </div>
  `;
}

function renderPerfGeneration(avg) {
  const el = document.getElementById('perf-gen-stats');
  if (!avg.sample_size) {
    el.innerHTML = '<div class="empty-state" style="padding:1.5rem"><p>No generation data yet</p></div>';
    return;
  }
  el.innerHTML = `
    <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:.75rem">
      <div style="padding:1rem;background:rgba(59,130,246,.05);border-radius:.75rem;text-align:center">
        <div style="font-size:.75rem;font-weight:700;text-transform:uppercase;color:var(--muted-fg);margin-bottom:.25rem">Claude</div>
        <div style="font-size:1.5rem;font-weight:700;color:#3b82f6">${avg.claude_ms}ms</div>
      </div>
      <div style="padding:1rem;background:rgba(124,58,237,.05);border-radius:.75rem;text-align:center">
        <div style="font-size:.75rem;font-weight:700;text-transform:uppercase;color:var(--muted-fg);margin-bottom:.25rem">Flux</div>
        <div style="font-size:1.5rem;font-weight:700;color:#7c3aed">${avg.flux_ms}ms</div>
      </div>
      <div style="padding:1rem;background:rgba(16,185,129,.05);border-radius:.75rem;text-align:center">
        <div style="font-size:.75rem;font-weight:700;text-transform:uppercase;color:var(--muted-fg);margin-bottom:.25rem">Total</div>
        <div style="font-size:1.5rem;font-weight:700;color:#10b981">${avg.total_ms}ms</div>
      </div>
    </div>
    <div style="text-align:center;margin-top:.5rem;font-size:.8rem;color:var(--muted-fg)">Based on ${avg.sample_size} samples</div>
  `;
}

function renderPerfErrors(errors) {
  const el = document.getElementById('perf-errors');
  const byType = errors.by_type || {};
  const types = Object.entries(byType);
  if (!types.length) {
    el.innerHTML = '<div class="empty-state" style="padding:1.5rem"><p>No errors recorded</p></div>';
    return;
  }
  el.innerHTML = types.map(([type, count]) => `
    <div style="display:flex;justify-content:space-between;align-items:center;padding:.5rem .75rem;background:rgba(239,68,68,.03);border-radius:.5rem;margin-bottom:.5rem">
      <span style="font-weight:600;font-size:.85rem">${escHtml(type)}</span>
      <span class="badge badge-danger">${count}</span>
    </div>
  `).join('');
}

function renderPerfRecent(recent) {
  const tbody = document.getElementById('perf-recent-tbody');
  if (!recent.length) {
    tbody.innerHTML = '<tr><td colspan="4"><div class="empty-state"><p>No recent generations</p></div></td></tr>';
    return;
  }
  tbody.innerHTML = recent.map(r => {
    const time = r.timestamp ? new Date(r.timestamp * 1000).toLocaleString() : '—';
    return `<tr>
      <td>${r.claude_ms}ms</td>
      <td>${r.flux_ms}ms</td>
      <td style="font-weight:700">${r.total_ms}ms</td>
      <td>${time}</td>
    </tr>`;
  }).join('');
}
