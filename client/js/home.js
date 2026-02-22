/* ─── Home page ───────────────────────────────────────── */

let activeTab   = 'all';
let pendingDel  = null;   // story id pending deletion
let allStories  = [];
let favStories  = [];

// ── Toast ──────────────────────────────────────────────
function showToast(msg, type = 'success') {
  const c = document.getElementById('toast-container');
  const t = document.createElement('div');
  t.className = `toast ${type}`;
  t.textContent = msg;
  c.appendChild(t);
  setTimeout(() => t.remove(), 3000);
}

// ── Fetch ──────────────────────────────────────────────
async function loadStories() {
  const grid = document.getElementById('stories-grid');
  grid.innerHTML = skeletons(6);
  try {
    const [allRes, favRes] = await Promise.all([
      fetch('/api/stories'),
      fetch('/api/stories/favorites'),
    ]);
    allStories = await allRes.json();
    favStories = await favRes.json();
    render();
  } catch {
    grid.innerHTML = '<p style="color:var(--destructive);padding:2rem;text-align:center">Failed to load stories.</p>';
  }
}

function skeletons(n) {
  return Array.from({length: n}).map(() => `<div class="skeleton"></div>`).join('');
}

// ── Render ─────────────────────────────────────────────
function render() {
  const stories = activeTab === 'all' ? allStories : favStories;
  const grid    = document.getElementById('stories-grid');
  const count   = document.getElementById('stories-count');

  if (count) count.textContent = `${stories.length} ${stories.length === 1 ? 'story' : 'stories'}`;

  // tab button styles
  const tabAll = document.getElementById('tab-all');
  const tabFav = document.getElementById('tab-fav');
  tabAll.className = `tab-btn${activeTab === 'all' ? ' active-all' : ''}`;
  tabFav.className = `tab-btn${activeTab === 'favorites' ? ' active-fav' : ''}`;

  if (!stories.length) {
    grid.innerHTML = emptyState();
    return;
  }
  grid.innerHTML = stories.map(s => cardHtml(s)).join('');

  // attach events
  grid.querySelectorAll('.story-card-link').forEach(el => {
    el.addEventListener('click', (e) => {
      if (e.target.closest('.card-del-btn')) return;
      window.location.href = `/story/${el.dataset.id}`;
    });
  });
  grid.querySelectorAll('.card-del-btn').forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      e.preventDefault();
      pendingDel = Number(btn.dataset.id);
      // Show story title in modal
      const story = allStories.find(s => s.id === pendingDel) || favStories.find(s => s.id === pendingDel);
      const nameEl = document.getElementById('modal-story-name');
      if (nameEl && story) nameEl.textContent = `"${story.storyTitle}"`;
      document.getElementById('delete-modal').classList.remove('hidden');
    });
  });
}

function cardHtml(s) {
  const pages = typeof s.pages === 'string' ? JSON.parse(s.pages) : (s.pages || []);
  const preview = pages[0] ? pages[0].text : '';
  const img   = pages[0] && pages[0].imageUrl ? pages[0].imageUrl : '';
  const fav   = s.isFavorite;

  return `
  <div class="story-card story-card-link" data-id="${s.id}" style="cursor:pointer">
    <div class="card-img-wrap">
      ${img
        ? `<img class="card-img" src="${img}" alt="${escHtml(s.storyTitle)}" loading="lazy" />`
        : `<div class="card-img" style="background:linear-gradient(135deg,#c4b5fd,#fbcfe8,#bfdbfe);width:100%;height:100%"></div>`
      }
      <div class="card-overlay">
        <span class="card-overlay-text">
          <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24"
            fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/>
          </svg>
          Read Story
        </span>
      </div>
      ${fav ? `
        <div class="card-fav-badge">
          <svg viewBox="0 0 24 24" fill="currentColor">
            <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>
          </svg>
        </div>` : ''}
      <button class="card-del-btn" data-id="${s.id}" title="Delete story">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"
          stroke-linecap="round" stroke-linejoin="round">
          <polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/>
          <path d="M10 11v6"/><path d="M14 11v6"/><path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2"/>
        </svg>
      </button>
    </div>
    <div class="card-body">
      <h3 class="card-title line-clamp-2">${escHtml(s.storyTitle)}</h3>
      <p class="card-desc line-clamp-3">${escHtml(preview)}</p>
      <div class="card-meta">
        <div class="card-age-badge">${escHtml(String(s.age || '?'))}</div>
        <div>
          <p class="card-meta-label">${escHtml(s.childName)}</p>
          <p style="font-size:.8rem;color:var(--muted-fg)">${escHtml(s.condition || '')}</p>
        </div>
      </div>
    </div>
  </div>`;
}

function emptyState() {
  if (activeTab === 'favorites') {
    return `
    <div class="empty-state empty-fav" style="grid-column:1/-1">
      <div class="empty-icon">
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor">
          <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>
        </svg>
      </div>
      <h3>No Favourites Yet</h3>
      <p>Star a story while reading to save it here for easy access later.</p>
    </div>`;
  }
  return `
  <div class="empty-state" style="grid-column:1/-1">
    <div class="empty-icon">
      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor"
        stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M4 19.5v-15A2.5 2.5 0 0 1 6.5 2H20v20H6.5a2.5 2.5 0 0 1 0-5H20"/>
      </svg>
    </div>
    <h3>No Stories Yet!</h3>
    <p>Create your first personalised story for a special hero. It only takes a minute!</p>
    <a href="/create" class="btn btn-primary btn-lg">
      <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none"
        stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
        <path d="M12 5v14M5 12h14"/>
      </svg>
      Create First Story
    </a>
  </div>`;
}

// ── Delete ─────────────────────────────────────────────
async function deleteStory(id) {
  try {
    const res = await fetch(`/api/stories/${id}`, { method: 'DELETE' });
    if (!res.ok) throw new Error();
    allStories = allStories.filter(s => s.id !== Number(id));
    favStories = favStories.filter(s => s.id !== Number(id));
    render();
    showToast('Story deleted', 'success');
  } catch {
    showToast('Could not delete story', 'error');
  }
}

function escHtml(str) {
  const d = document.createElement('div');
  d.textContent = str || '';
  return d.innerHTML;
}

// ── Init ───────────────────────────────────────────────
document.getElementById('tab-all').addEventListener('click', () => { activeTab = 'all'; render(); });
document.getElementById('tab-fav').addEventListener('click', () => { activeTab = 'favorites'; render(); });

document.getElementById('modal-cancel').addEventListener('click', () => {
  pendingDel = null;
  document.getElementById('delete-modal').classList.add('hidden');
});
document.getElementById('modal-confirm').addEventListener('click', async () => {
  document.getElementById('delete-modal').classList.add('hidden');
  if (pendingDel) await deleteStory(pendingDel);
  pendingDel = null;
});

loadStories();
