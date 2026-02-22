/* ─── Create story page ───────────────────────────────── */

const TRAITS = [
  { id: 'brave',      label: 'Brave',      icon: shieldIcon() },
  { id: 'kind',       label: 'Kind',        icon: heartIcon() },
  { id: 'curious',    label: 'Curious',     icon: lightbulbIcon() },
  { id: 'determined', label: 'Determined',  icon: zapIcon() },
  { id: 'helpful',    label: 'Helpful',     icon: handIcon() },
  { id: 'creative',   label: 'Creative',    icon: paletteIcon() },
  { id: 'smart',      label: 'Smart',       icon: bookIcon() },
  { id: 'cheerful',   label: 'Cheerful',    icon: smileIcon() },
  { id: 'friendly',   label: 'Friendly',    icon: usersIcon() },
  { id: 'patient',    label: 'Patient',     icon: starIcon() },
];

const selected = new Set();

// ── SVG icons ──────────────────────────────────────────
function shieldIcon() { return `<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>`; }
function heartIcon() { return `<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/></svg>`; }
function lightbulbIcon() { return `<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="9" y1="18" x2="15" y2="18"/><line x1="10" y1="22" x2="14" y2="22"/><path d="M15.09 14c.18-.98.65-1.74 1.41-2.5A4.65 4.65 0 0 0 18 8 6 6 0 0 0 6 8c0 1 .23 2.23 1.5 3.5A4.61 4.61 0 0 1 8.91 14"/></svg>`; }
function zapIcon() { return `<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>`; }
function handIcon() { return `<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 11V6a2 2 0 0 0-2-2v0a2 2 0 0 0-2 2v0"/><path d="M14 10V4a2 2 0 0 0-2-2v0a2 2 0 0 0-2 2v2"/><path d="M10 10.5V6a2 2 0 0 0-2-2v0a2 2 0 0 0-2 2v8"/><path d="M18 8a2 2 0 1 1 4 0v6a8 8 0 0 1-8 8h-2c-2.8 0-4.5-.86-5.99-2.34l-3.6-3.6a2 2 0 0 1 2.83-2.82L7 15"/></svg>`; }
function paletteIcon() { return `<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="13.5" cy="6.5" r=".5"/><circle cx="17.5" cy="10.5" r=".5"/><circle cx="8.5" cy="7.5" r=".5"/><circle cx="6.5" cy="12.5" r=".5"/><path d="M12 2C6.5 2 2 6.5 2 12s4.5 10 10 10c.926 0 1.648-.746 1.648-1.688 0-.437-.18-.835-.437-1.125-.29-.289-.438-.652-.438-1.125a1.64 1.64 0 0 1 1.668-1.668h1.996c3.051 0 5.555-2.503 5.555-5.554C21.965 6.012 17.461 2 12 2z"/></svg>`; }
function bookIcon() { return `<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 19.5v-15A2.5 2.5 0 0 1 6.5 2H20v20H6.5a2.5 2.5 0 0 1 0-5H20"/></svg>`; }
function smileIcon() { return `<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M8 13s1.5 2 4 2 4-2 4-2"/><line x1="9" y1="9" x2="9.01" y2="9"/><line x1="15" y1="9" x2="15.01" y2="9"/></svg>`; }
function usersIcon() { return `<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>`; }
function starIcon() { return `<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>`; }
function checkIcon() { return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>`; }

// ── Render trait grid ─────────────────────────────────
function renderTraits() {
  const grid = document.getElementById('traits-grid');
  grid.innerHTML = TRAITS.map(t => `
    <button type="button" class="trait-btn${selected.has(t.id) ? ' selected' : ''}" data-id="${t.id}">
      <div class="trait-icon">${t.icon}</div>
      <span class="trait-label">${t.label}</span>
      ${selected.has(t.id) ? `<span class="trait-check">${checkIcon()}</span>` : ''}
    </button>
  `).join('');

  grid.querySelectorAll('.trait-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const id = btn.dataset.id;
      if (selected.has(id)) selected.delete(id);
      else selected.add(id);
      updateTraitsField();
      renderTraits();
    });
  });
}

function updateTraitsField() {
  const arr = [...selected];
  document.getElementById('heroCharacteristics').value = arr.join(', ');
  const label = document.getElementById('traits-label');
  label.textContent = arr.length ? arr.join(', ') : 'none';
}

// ── Toast ──────────────────────────────────────────────
function showToast(msg, type = 'error') {
  const c = document.getElementById('toast-container');
  const t = document.createElement('div');
  t.className = `toast ${type}`;
  t.textContent = msg;
  c.appendChild(t);
  setTimeout(() => t.remove(), 4000);
}

// ── Form submit ────────────────────────────────────────
document.getElementById('create-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const form = e.target;

  const name  = form.childName.value.trim();
  const age   = parseInt(form.age.value, 10);
  const gender= form.gender.value;
  const cond  = form.condition.value.trim();
  const traits= form.heroCharacteristics.value.trim();

  if (!name) { showToast('Please enter the hero\'s name'); return; }
  if (!age || age < 2 || age > 14) { showToast('Age must be between 2 and 14'); return; }
  if (!gender) { showToast('Please select a gender'); return; }
  if (!cond) { showToast('Please describe the medical challenge'); return; }

  document.getElementById('loading-overlay').classList.remove('hidden');
  document.getElementById('submit-btn').disabled = true;

  try {
    const res = await fetch('/api/stories/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        childName: name, age, gender, condition: cond,
        heroCharacteristics: traits || 'brave, kind',
      }),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.error || `Server error ${res.status}`);
    }

    const story = await res.json();
    window.location.href = `/story/${story.id}`;
  } catch (err) {
    document.getElementById('loading-overlay').classList.add('hidden');
    document.getElementById('submit-btn').disabled = false;
    showToast(err.message || 'Something went wrong. Please try again.');
  }
});

// ── Init ───────────────────────────────────────────────
renderTraits();
