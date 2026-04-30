/* ─── User Credit Dashboard ───────────────────────────── */

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

  // Set greeting
  const user = Auth.getUser();
  if (user && user.name) {
    document.getElementById('user-greeting').textContent =
      `Hey ${user.name}, here's your story generation credit usage`;
  }

  await loadAll();
})();

async function loadAll() {
  const btn = document.getElementById('refresh-btn');
  if (btn) btn.classList.add('loading');
  try {
    await Promise.all([loadOverview(), loadHistory(), loadStories()]);
    if (btn) showToast('Data refreshed');
  } catch (e) {
    console.error('Load failed:', e);
  } finally {
    if (btn) btn.classList.remove('loading');
  }
}

// ── Overview Stats ─────────────────────────────────────
async function loadOverview() {
  try {
    const res = await fetch('/api/credits/my', { headers: Auth.headers() });
    if (!res.ok) throw new Error('Failed to load');
    const data = await res.json();
    renderStats(data);
    renderBreakdown(data);
  } catch (e) {
    console.error('Overview error:', e);
  }
}

function renderStats(data) {
  const row = document.getElementById('stats-row');
  const flux = data.by_api.flux2pro || {};
  const claude = data.by_api.claude || {};
  const totalCalls = (flux.total_calls || 0) + (claude.total_calls || 0);
  const totalStories = Math.max(claude.successes || 0, 0);
  const totalImages = flux.successes || 0;

  row.innerHTML = `
    <div class="stat-card purple">
      <div class="stat-icon purple">
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
          <rect x="2" y="5" width="20" height="14" rx="2"/><line x1="2" y1="10" x2="22" y2="10"/>
        </svg>
      </div>
      <div class="stat-label">My Total Credits</div>
      <div class="stat-value">$${data.total_used.toFixed(2)}</div>
      <div class="stat-sub">${totalCalls} API calls made</div>
    </div>

    <div class="stat-card amber">
      <div class="stat-icon amber">
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
          <path d="M4 19.5v-15A2.5 2.5 0 0 1 6.5 2H20v20H6.5a2.5 2.5 0 0 1 0-5H20"/>
        </svg>
      </div>
      <div class="stat-label">Stories Created</div>
      <div class="stat-value">${totalStories}</div>
      <div class="stat-sub">$${(claude.total_credits || 0).toFixed(2)} in story generation</div>
    </div>

    <div class="stat-card blue">
      <div class="stat-icon blue">
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
          <rect x="3" y="3" width="18" height="18" rx="2" ry="2"/>
          <circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/>
        </svg>
      </div>
      <div class="stat-label">Images Generated</div>
      <div class="stat-value">${totalImages}</div>
      <div class="stat-sub">$${(flux.total_credits || 0).toFixed(2)} in Flux 2 Pro</div>
    </div>

    <div class="stat-card green">
      <div class="stat-icon green">
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
          <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/>
        </svg>
      </div>
      <div class="stat-label">Success Rate</div>
      <div class="stat-value">${totalCalls > 0 ? Math.round(((flux.successes || 0) + (claude.successes || 0)) / totalCalls * 100) : 0}%</div>
      <div class="stat-sub">${(flux.failures || 0) + (claude.failures || 0)} failures</div>
    </div>
  `;
}

// ── Breakdown ──────────────────────────────────────────
function renderBreakdown(data) {
  const el = document.getElementById('api-breakdown');
  const apis = data.by_api;
  if (!Object.keys(apis).length) {
    el.innerHTML = `<div class="empty-state"><p>No credits used yet</p><p class="hint">Create a story to start!</p></div>`;
    return;
  }

  const labels = { flux2pro: 'Image Generation (Flux 2 Pro)', claude: 'Story Text (Claude)' };
  const colors = { flux2pro: 'purple', claude: 'blue' };

  let html = '';
  for (const [name, info] of Object.entries(apis)) {
    const successPct = info.total_calls > 0
      ? Math.round(info.successes / info.total_calls * 100) : 0;
    const colorCls = colors[name] || 'amber';
    html += `
      <div style="margin-bottom:1.25rem;padding:1rem;background:rgba(124,58,237,.02);border-radius:var(--radius-sm)">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:.5rem">
          <span style="font-weight:700;font-size:.9rem">${labels[name] || name}</span>
          <span class="credit-num" style="font-size:1.1rem">$${(info.total_credits || 0).toFixed(2)}</span>
        </div>
        <div style="display:flex;gap:1.5rem;font-size:.8rem;color:var(--muted-fg)">
          <span>${info.total_calls} calls</span>
          <span>${info.successes} successful</span>
          <span>${info.failures} failed</span>
        </div>
        <div class="progress-bar" style="margin-top:.5rem;height:.35rem">
          <div class="progress-bar-fill${colorCls === 'blue' ? '' : ''}" style="width:${successPct}%"></div>
        </div>
      </div>`;
  }
  el.innerHTML = html;
}

// ── History Chart ──────────────────────────────────────
async function loadHistory() {
  try {
    const res = await fetch('/api/credits/my/history?days=14', { headers: Auth.headers() });
    const { history } = await res.json();
    renderHistoryChart(history);
  } catch (e) {
    console.error('History error:', e);
  }
}

function renderHistoryChart(history) {
  const container = document.getElementById('history-chart');
  if (!history.length) {
    container.innerHTML = `<div class="empty-state"><p>No usage history yet</p><p class="hint">Create your first story!</p></div>`;
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
    const shortDate = date.slice(5);
    barsHtml += `
      <div class="chart-bar-col">
        <div style="display:flex;gap:2px;align-items:flex-end;height:100%">
          <div class="chart-bar flux" style="height:${Math.max(fluxH, 2)}px"
               data-tooltip="Images: $${(d.flux2pro || 0).toFixed(3)}"></div>
          <div class="chart-bar claude" style="height:${Math.max(claudeH, 2)}px"
               data-tooltip="Stories: $${(d.claude || 0).toFixed(3)}"></div>
        </div>
        <div class="chart-bar-label">${shortDate}</div>
      </div>`;
  });

  container.innerHTML = `<div class="chart-bar-group">${barsHtml}</div>`;
}

// ── Story Credits Table ────────────────────────────────
async function loadStories() {
  try {
    const res = await fetch('/api/credits/my/stories', { headers: Auth.headers() });
    const { stories } = await res.json();
    renderStoriesTable(stories);
  } catch (e) {
    console.error('Stories error:', e);
  }
}

function renderStoriesTable(stories) {
  const tbody = document.getElementById('stories-tbody');
  if (!stories.length) {
    tbody.innerHTML = `<tr><td colspan="4"><div class="empty-state"><p>No stories yet</p><p class="hint"><a href="/create" style="color:var(--primary);font-weight:700">Create your first story</a></p></div></td></tr>`;
    return;
  }

  tbody.innerHTML = stories.map(s => {
    const date = s.created_at ? new Date(s.created_at).toLocaleDateString() : '—';
    return `
      <tr>
        <td>
          <div class="story-credit-title">${escHtml(s.story_title || 'Untitled Story')}</div>
          <div class="story-credit-child">for ${escHtml(s.child_name || 'Unknown')}</div>
        </td>
        <td>${date}</td>
        <td>${s.api_calls || 0}</td>
        <td class="credit-num">$${(s.credits_used || 0).toFixed(3)}</td>
      </tr>`;
  }).join('');
}

// ── Helpers ────────────────────────────────────────────
function escHtml(s) {
  const d = document.createElement('div');
  d.textContent = s || '';
  return d.innerHTML;
}
