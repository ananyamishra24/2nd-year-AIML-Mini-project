/* ── Auth guard ───────────────────────────────────────────── */
const TOKEN = localStorage.getItem('cc_token');
if (!TOKEN) window.location.href = '/login';

/* ── Palette ─────────────────────────────────────────────── */
const PALETTE = [
  { cls:'br0', color:'#9b6dff', r:'155,109,255', fd:'4.3s', fl:'0s'   },
  { cls:'br1', color:'#f59e0b', r:'245,158,11',  fd:'3.9s', fl:'0.9s' },
  { cls:'br2', color:'#22d3ee', r:'34,211,238',  fd:'4.6s', fl:'1.7s' },
  { cls:'br3', color:'#f472b6', r:'244,114,182', fd:'4.1s', fl:'0.4s' },
  { cls:'br4', color:'#4ade80', r:'74,222,128',  fd:'4.5s', fl:'1.2s' },
  { cls:'br5', color:'#fb923c', r:'251,146,60',  fd:'3.7s', fl:'2.1s' },
];
const CHEEKS = [
  ['0s','0.4s','0.8s'],['0.5s','0.9s','1.3s'],['1s','1.4s','1.8s'],
  ['1.5s','1.9s','2.3s'],['0.3s','0.7s','1.1s'],['1.2s','1.6s','2s'],
];

let manageMode = false;
let pendingDeleteId = null;

/* ── Helpers ─────────────────────────────────────────────── */
function escHTML(s) { return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }
function escAttr(s) { return s.replace(/"/g,'&quot;').replace(/'/g,'&#39;'); }
function authHdr() { return { 'Authorization': 'Bearer ' + TOKEN }; }

/* ── Build profile card ───────────────────────────────────── */
function buildCard(child, idx) {
  const p   = PALETTE[idx % PALETTE.length];
  const cd  = CHEEKS[idx % CHEEKS.length];
  const del = (0.05 + idx * 0.1).toFixed(2) + 's';
  const hasCond = (child.medicalChallenge || '').trim() ||
                  (Array.isArray(child.conditions) && child.conditions.length > 0);

  const el = document.createElement('div');
  el.className = `profile ${p.cls}`;
  el.setAttribute('role', 'listitem');
  el.setAttribute('tabindex', '0');
  el.setAttribute('aria-label', child.name);
  el.style.cssText =
    `--char-color:${p.color};--char-r:${p.r};--fd:${p.fd};--fl:${p.fl};` +
    `opacity:0;transform:translateY(16px);` +
    `transition:opacity .38s ease ${del},transform .38s ease ${del};`;

  el.innerHTML = `
    <div class="char-wrap">
      <div class="fuzzy" aria-hidden="true">
        <div class="face">
          <div class="eyes"><div class="eye"></div><div class="eye"></div></div>
          <div class="mouth"></div>
        </div>
        <div class="cheeks">
          <div class="cheek-dot" style="--bd:2.6s;--bde:${cd[0]}"></div>
          <div class="cheek-dot" style="--bd:2.6s;--bde:${cd[1]}"></div>
          <div class="cheek-dot" style="--bd:2.6s;--bde:${cd[2]}"></div>
        </div>
        ${hasCond ? '<div class="hero-badge">Hero</div>' : ''}
      </div>

      <!-- Edit overlay (manage mode) — pencil opens the edit modal -->
      <div class="edit-overlay" aria-hidden="true">
        <button class="edit-center-btn" aria-label="Edit ${escAttr(child.name)}">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor"
            stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
            <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
            <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
          </svg>
        </button>
      </div>
    </div>
    <div class="profile-name">${escHTML(child.name)}</div>
  `;

  el.addEventListener('click', () => { if (!manageMode) selectChild(el, child); });
  el.addEventListener('keydown', e => {
    if ((e.key === 'Enter' || e.key === ' ') && !manageMode) { e.preventDefault(); selectChild(el, child); }
  });
  el.querySelector('.edit-center-btn').addEventListener('click', e => {
    e.stopPropagation();
    openEditModal(child);
  });

  requestAnimationFrame(() => { el.style.opacity = '1'; el.style.transform = 'translateY(0)'; });
  return el;
}

/* ── Build Add Hero card ──────────────────────────────────── */
function buildAddCard(del) {
  const el = document.createElement('div');
  el.className = 'add-profile';
  el.setAttribute('role', 'listitem');
  el.setAttribute('tabindex', '0');
  el.setAttribute('aria-label', 'Add new hero');
  el.style.cssText = `opacity:0;transform:translateY(16px);transition:opacity .38s ease ${del},transform .38s ease ${del};`;
  el.innerHTML = `
    <div class="add-box"><div class="add-plus" aria-hidden="true">+</div></div>
    <div class="add-name">Add Hero</div>
  `;
  el.addEventListener('click', openAddModal);
  el.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); openAddModal(); } });
  requestAnimationFrame(() => { el.style.opacity = '1'; el.style.transform = 'translateY(0)'; });
  return el;
}

/* ── Render ───────────────────────────────────────────────── */
function render(children) {
  const row = document.getElementById('profiles-row');
  const btn = document.getElementById('manage-btn');
  row.innerHTML = '';

  if (children.length === 0) {
    row.innerHTML = `
      <div class="empty-state">
        <div class="empty-icon">✨</div>
        <h2 class="empty-title">No heroes yet!</h2>
        <p class="empty-desc">Create your first story hero to start reading personalized adventures.</p>
        <button class="btn-cta" id="first-hero-btn">+ Create First Hero</button>
      </div>`;
    document.getElementById('first-hero-btn').addEventListener('click', openAddModal);
    btn.style.display = 'none';
    return;
  }

  children.forEach((c, i) => row.appendChild(buildCard(c, i)));
  row.appendChild(buildAddCard((0.05 + children.length * 0.1).toFixed(2) + 's'));
  btn.style.display = '';
}

/* ── Fetch children ───────────────────────────────────────── */
async function loadChildren() {
  try {
    const res  = await fetch('/api/children', { headers: authHdr() });
    if (res.status === 401) { window.location.href = '/login'; return; }
    const data = await res.json();
    render(Array.isArray(data) ? data : []);
  } catch {
    document.getElementById('profiles-row').innerHTML =
      '<p style="color:var(--muted-fg);text-align:center">Could not load profiles. <a href="" style="color:var(--primary)">Retry</a></p>';
  }
}

/* ── Select child — Netflix-style transition ─────────────── */
function selectChild(el, child) {
  localStorage.setItem('cc_active_child', JSON.stringify(child));

  document.querySelectorAll('.profile, .add-profile').forEach(p => {
    if (p !== el) { p.style.transition = 'opacity .32s ease, transform .32s ease'; p.style.opacity = '0'; p.style.transform = 'scale(.88)'; }
  });
  document.getElementById('heading').style.opacity = '0';
  document.getElementById('manage-btn').style.opacity = '0';

  el.classList.add('selecting');
  el.querySelector('.char-wrap').style.transition = 'transform .55s cubic-bezier(.34,1.4,.64,1)';
  el.querySelector('.char-wrap').style.transform = 'scale(1.28)';

  setTimeout(() => {
    el.style.opacity = '0';
    document.getElementById('loading-label').textContent = `${child.name}'s adventure is loading…`;
    document.getElementById('loading-overlay').classList.add('show');
    setTimeout(() => { window.location.href = '/'; }, 1500);
  }, 520);
}

/* ── Manage mode ──────────────────────────────────────────── */
const manageBtn = document.getElementById('manage-btn');
manageBtn.addEventListener('click', () => {
  manageMode = !manageMode;
  document.querySelectorAll('.profile:not(.add-profile)').forEach(p => {
    p.classList.toggle('manage-mode', manageMode);
    p.querySelector('.edit-overlay').setAttribute('aria-hidden', String(!manageMode));
  });
  const addCard = document.querySelector('.add-profile');
  if (addCard) addCard.style.opacity = manageMode ? '.15' : '.45';
  manageBtn.classList.toggle('active', manageMode);
  manageBtn.textContent = manageMode ? 'Done' : 'Manage Heroes';
});

/* ── Confirm delete ───────────────────────────────────────── */
document.getElementById('confirm-cancel').addEventListener('click', () => {
  document.getElementById('confirm-overlay').classList.remove('open');
  pendingDeleteId = null;
});
document.getElementById('confirm-delete').addEventListener('click', async () => {
  if (!pendingDeleteId) return;
  const id = pendingDeleteId; pendingDeleteId = null;
  document.getElementById('confirm-overlay').classList.remove('open');
  try {
    await fetch(`/api/children/${id}`, { method: 'DELETE', headers: authHdr() });
  } catch {}
  if (manageMode) manageBtn.click();
  await loadChildren();
});

/* ══════════════════════════════════════════════════════════
   ADD HERO MODAL (simple — name/age/gender/conditions only)
   ══════════════════════════════════════════════════════════ */
const addOverlay = document.getElementById('modal-overlay');

function openAddModal() {
  if (manageMode) manageBtn.click();
  addOverlay.classList.add('open');
  setTimeout(() => document.getElementById('hero-name').focus(), 50);
}
function closeAddModal() {
  addOverlay.classList.remove('open');
  ['hero-name','hero-age','hero-conditions'].forEach(id => { document.getElementById(id).value = ''; });
  document.getElementById('hero-gender').value = '';
  document.querySelectorAll('.form-error').forEach(e => e.classList.remove('show'));
}
document.getElementById('modal-cancel').addEventListener('click', closeAddModal);
addOverlay.addEventListener('click', e => { if (e.target === addOverlay) closeAddModal(); });
document.getElementById('modal-save').addEventListener('click', async () => {
  const nameEl  = document.getElementById('hero-name');
  const ageEl   = document.getElementById('hero-age');
  const nameErr = document.getElementById('name-error');
  const ageErr  = document.getElementById('age-error');
  const name = nameEl.value.trim();
  const age  = parseInt(ageEl.value, 10);
  let ok = true;
  nameErr.classList.remove('show'); ageErr.classList.remove('show');
  if (!name) { nameErr.classList.add('show'); ok = false; }
  if (!ageEl.value || isNaN(age) || age < 1 || age > 17) { ageErr.classList.add('show'); ok = false; }
  if (!ok) return;

  const btn  = document.getElementById('modal-save');
  const txt  = document.getElementById('save-text');
  const spin = document.getElementById('save-spinner');
  btn.disabled = true; txt.textContent = 'Saving'; spin.style.display = '';

  try {
    const res = await fetch('/api/children', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...authHdr() },
      body: JSON.stringify({
        name, age,
        gender: document.getElementById('hero-gender').value,
        conditions: document.getElementById('hero-conditions').value.trim()
                    ? [document.getElementById('hero-conditions').value.trim()] : [],
      }),
    });
    if (!res.ok) throw new Error();
    closeAddModal(); await loadChildren();
  } catch {
    nameErr.textContent = 'Something went wrong — please try again';
    nameErr.classList.add('show');
  } finally {
    btn.disabled = false; txt.textContent = 'Add Hero'; spin.style.display = 'none';
  }
});

/* ══════════════════════════════════════════════════════════
   HERO EDIT MODAL — full customization
   ══════════════════════════════════════════════════════════ */

/* ── (Traits removed — every kid is brave, kind, curious…) ── */

/* ── Character builder constants ───────────────────────── */
const SKIN_COLORS = {
  'light':'#FDDCB5','medium-light':'#E8B88A','medium':'#D4956B',
  'medium-brown':'#B07242','brown':'#8B5E3C','dark-brown':'#5C3A1E',
};
const HAIR_COLORS = {
  'black':'#1a1a2e','brown':'#6B3A2A','blonde':'#F2D16B',
  'red':'#C0392B','auburn':'#8B4513','white':'#E8E8E8',
};
const ACCESSORY_EMOJI = { 'cape':'🧣','shield':'🛡️','wand':'🪄','backpack':'🎒' };
const MEDICAL_EMOJI   = { 'none':'','arm cast':'💪','eye patch':'🏴‍☠️','wheelchair':'🦽','head bandana':'🎗️' };

let editChildId   = null;
const editHeroChar = {
  skin_tone:null, hair_style:null, hair_color:null,
  outfit:null, accessory:null, medical_detail:null, birth_marks:null,
};

const editOverlay = document.getElementById('edit-overlay');


function initEditSwatchGroup(id, field) {
  const c = document.getElementById(id);
  if (!c) return;
  c.querySelectorAll('.char-swatch').forEach(btn => {
    btn.addEventListener('click', () => {
      c.querySelectorAll('.char-swatch').forEach(b => b.classList.remove('selected'));
      btn.classList.add('selected');
      editHeroChar[field] = btn.dataset.value;
    });
  });
}
function initEditIconGroup(id, field) {
  const c = document.getElementById(id);
  if (!c) return;
  c.querySelectorAll('.char-icon-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      c.querySelectorAll('.char-icon-btn').forEach(b => b.classList.remove('selected'));
      btn.classList.add('selected');
      editHeroChar[field] = btn.dataset.value;
    });
  });
}

/* one-time: wire up the builder interactions */
initEditSwatchGroup('edit-skin-swatches',     'skin_tone');
initEditSwatchGroup('edit-hair-color-swatches','hair_color');
initEditIconGroup('edit-accessory-options',   'accessory');

/* Helper: icon group with optional custom free-text input */
function initIconGroupWithCustom(containerId, inputId, field) {
  const container   = document.getElementById(containerId);
  const customInput = document.getElementById(inputId);
  if (!container) return;

  container.querySelectorAll('.char-icon-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      container.querySelectorAll('.char-icon-btn').forEach(b => b.classList.remove('selected'));
      btn.classList.add('selected');
      if (btn.dataset.value === '__custom__') {
        customInput.style.display = '';
        customInput.focus();
        editHeroChar[field] = customInput.value.trim() || null;
      } else {
        customInput.style.display = 'none';
        editHeroChar[field] = btn.dataset.value;
      }
    });
  });

  customInput.addEventListener('input', () => {
    editHeroChar[field] = customInput.value.trim() || null;
  });
}

initIconGroupWithCustom('edit-hair-style-options', 'hair-custom-input',    'hair_style');
initIconGroupWithCustom('edit-outfit-options',     'outfit-custom-input',  'outfit');
initIconGroupWithCustom('edit-medical-options',    'medical-custom-input', 'medical_detail');

/* Birth marks free-text */
document.getElementById('edit-birth-marks').addEventListener('input', function () {
  editHeroChar.birth_marks = this.value.trim() || null;
});

/* ── Open edit modal, pre-populate fields ─────────────── */
function openEditModal(child) {
  editChildId = child.id;

  /* basic fields */
  document.getElementById('edit-name').value    = child.name || '';
  document.getElementById('edit-age').value     = child.age  || '';
  document.getElementById('edit-gender').value  = child.gender || '';
  document.getElementById('edit-medical').value = child.medicalChallenge || '';

  /* character builder — reset selections */
  Object.keys(editHeroChar).forEach(k => { editHeroChar[k] = null; });
  document.querySelectorAll('#edit-overlay .char-swatch, #edit-overlay .char-icon-btn')
    .forEach(b => b.classList.remove('selected'));
  ['hair-custom-input','outfit-custom-input','medical-custom-input'].forEach(id => {
    const el = document.getElementById(id);
    el.value = ''; el.style.display = 'none';
  });
  document.getElementById('edit-birth-marks').value = '';

  /* re-apply saved hero character */
  const hc = child.heroCharacter;
  if (hc && typeof hc === 'object') {
    Object.assign(editHeroChar, hc);
    /* highlight selected swatches/buttons */
    ['skin_tone','hair_color'].forEach(field => {
      if (!editHeroChar[field]) return;
      const swatchId = field === 'skin_tone' ? 'edit-skin-swatches' : 'edit-hair-color-swatches';
      const c = document.getElementById(swatchId);
      if (c) c.querySelectorAll('.char-swatch').forEach(b => {
        if (b.dataset.value === editHeroChar[field]) b.classList.add('selected');
      });
    });
    /* accessory — preset only */
    const accC = document.getElementById('edit-accessory-options');
    if (accC && editHeroChar.accessory) {
      accC.querySelectorAll('.char-icon-btn').forEach(b => {
        if (b.dataset.value === editHeroChar.accessory) b.classList.add('selected');
      });
    }

    /* fields with custom free-text fallback */
    [
      { field:'hair_style',    containerId:'edit-hair-style-options', inputId:'hair-custom-input',    customBtnId:'hair-custom-btn'    },
      { field:'outfit',        containerId:'edit-outfit-options',     inputId:'outfit-custom-input',  customBtnId:'outfit-custom-btn'  },
      { field:'medical_detail',containerId:'edit-medical-options',    inputId:'medical-custom-input', customBtnId:'medical-custom-btn' },
    ].forEach(({ field, containerId, inputId, customBtnId }) => {
      const val = editHeroChar[field];
      if (!val) return;
      const c     = document.getElementById(containerId);
      const input = document.getElementById(inputId);
      const preset = c.querySelector(`.char-icon-btn[data-value="${CSS.escape(val)}"]`);
      if (preset) {
        preset.classList.add('selected');
      } else {
        c.querySelector(`#${customBtnId}`).classList.add('selected');
        input.value = val;
        input.style.display = '';
      }
    });

    /* birth marks */
    if (editHeroChar.birth_marks) {
      document.getElementById('edit-birth-marks').value = editHeroChar.birth_marks;
    }
  }

  /* clear error */
  const err = document.getElementById('edit-error');
  err.style.display = 'none'; err.textContent = '';

  editOverlay.classList.add('open');
  setTimeout(() => document.getElementById('edit-name').focus(), 60);
}

function closeEditModal() {
  editOverlay.classList.remove('open');
  editChildId = null;
}

document.getElementById('edit-cancel').addEventListener('click', closeEditModal);
editOverlay.addEventListener('click', e => { if (e.target === editOverlay) closeEditModal(); });

/* ── Delete from inside edit modal ───────────────────────── */
document.getElementById('edit-delete-hero').addEventListener('click', () => {
  if (!editChildId) return;
  pendingDeleteId = editChildId;
  const name = document.getElementById('edit-name').value.trim() || 'this hero';
  document.getElementById('confirm-title').textContent = `Remove ${name}?`;
  closeEditModal();
  document.getElementById('confirm-overlay').classList.add('open');
});
document.addEventListener('keydown', e => {
  if (e.key === 'Escape') {
    closeEditModal();
    closeAddModal();
    if (manageMode) manageBtn.click();
  }
});

/* ── Save edit ─────────────────────────────────────────── */
document.getElementById('edit-save').addEventListener('click', async () => {
  const name = document.getElementById('edit-name').value.trim();
  const age  = parseInt(document.getElementById('edit-age').value, 10);
  const err  = document.getElementById('edit-error');
  err.style.display = 'none';

  if (!name) { err.textContent = 'Name is required.'; err.style.display = 'block'; return; }
  if (!age || age < 1 || age > 18) { err.textContent = 'Age must be between 1 and 18.'; err.style.display = 'block'; return; }

  const btn  = document.getElementById('edit-save');
  const txt  = document.getElementById('edit-save-text');
  const spin = document.getElementById('edit-save-spinner');
  btn.disabled = true; txt.textContent = 'Saving'; spin.style.display = '';

  const hasHeroChar = Object.values(editHeroChar).some(v => v && v !== 'none');
  const payload = {
    name,
    age,
    gender:           document.getElementById('edit-gender').value || 'neutral',
    medicalChallenge: document.getElementById('edit-medical').value.trim(),
    heroCharacter:    hasHeroChar ? { ...editHeroChar } : null,
  };

  try {
    const res = await fetch(`/api/children/${editChildId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json', ...authHdr() },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const d = await res.json().catch(() => ({}));
      throw new Error(d.message || 'Save failed');
    }
    const updated = await res.json();
    /* update active child in localStorage if it's the same hero */
    try {
      const active = JSON.parse(localStorage.getItem('cc_active_child') || 'null');
      if (active && active.id === updated.id) {
        localStorage.setItem('cc_active_child', JSON.stringify(updated));
      }
    } catch {}
    closeEditModal();
    await loadChildren();
  } catch (e) {
    err.textContent = e.message || 'Something went wrong — please try again.';
    err.style.display = 'block';
  } finally {
    btn.disabled = false; txt.textContent = 'Save Changes'; spin.style.display = 'none';
  }
});

/* ══════════════════════════════════════════════════════════
   MOONFACE — camera-based face analysis
   ══════════════════════════════════════════════════════════ */

let _moonfaceStream = null;

async function openMoonface() {
  const overlay  = document.getElementById('moonface-overlay');
  const video    = document.getElementById('moonface-video');
  const status   = document.getElementById('moonface-status');
  const capBtn   = document.getElementById('moonface-capture');

  status.textContent = '';
  capBtn.disabled = false;
  overlay.classList.add('open');

  try {
    _moonfaceStream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: 'user', width: { ideal: 640 }, height: { ideal: 480 } },
      audio: false,
    });
    video.srcObject = _moonfaceStream;
  } catch {
    status.textContent = 'Camera access denied — please allow camera access and try again.';
    capBtn.disabled = true;
  }
}

function closeMoonface() {
  const overlay = document.getElementById('moonface-overlay');
  const video   = document.getElementById('moonface-video');
  overlay.classList.remove('open');
  if (_moonfaceStream) {
    _moonfaceStream.getTracks().forEach(t => t.stop());
    _moonfaceStream = null;
  }
  video.srcObject = null;
  document.getElementById('moonface-status').textContent = '';
  document.getElementById('moonface-capture').disabled = false;
}

function applyMoonfaceResult(result) {
  if (result.skin_tone)  editHeroChar.skin_tone  = result.skin_tone;
  if (result.hair_style) editHeroChar.hair_style = result.hair_style;
  if (result.hair_color) editHeroChar.hair_color = result.hair_color;

  const skinC = document.getElementById('edit-skin-swatches');
  if (skinC && result.skin_tone) {
    skinC.querySelectorAll('.char-swatch').forEach(b =>
      b.classList.toggle('selected', b.dataset.value === result.skin_tone));
  }
  const hairCC = document.getElementById('edit-hair-color-swatches');
  if (hairCC && result.hair_color) {
    hairCC.querySelectorAll('.char-swatch').forEach(b =>
      b.classList.toggle('selected', b.dataset.value === result.hair_color));
  }
  const hairSC = document.getElementById('edit-hair-style-options');
  if (hairSC && result.hair_style) {
    hairSC.querySelectorAll('.char-icon-btn').forEach(b =>
      b.classList.toggle('selected', b.dataset.value === result.hair_style));
  }

  document.getElementById('edit-char-panel').scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

document.getElementById('moonface-trigger').addEventListener('click', openMoonface);
document.getElementById('moonface-cancel').addEventListener('click', closeMoonface);

document.getElementById('moonface-capture').addEventListener('click', async () => {
  const video  = document.getElementById('moonface-video');
  const canvas = document.getElementById('moonface-canvas');
  const status = document.getElementById('moonface-status');
  const capBtn = document.getElementById('moonface-capture');

  canvas.width  = video.videoWidth  || 640;
  canvas.height = video.videoHeight || 480;
  canvas.getContext('2d').drawImage(video, 0, 0);
  const imageData = canvas.toDataURL('image/jpeg', 0.85);

  capBtn.disabled = true;
  status.textContent = '🌙 Analysing face…';

  try {
    const res = await fetch('/api/moonface/analyze', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...authHdr() },
      body: JSON.stringify({ image: imageData }),
    });
    if (!res.ok) {
      const d = await res.json().catch(() => ({}));
      throw new Error(d.message || 'Analysis failed');
    }
    const result = await res.json();
    closeMoonface();
    applyMoonfaceResult(result);
  } catch (err) {
    status.textContent = err.message || 'Something went wrong — please try again.';
    capBtn.disabled = false;
  }
});

/* ── Boot ─────────────────────────────────────────────────── */
loadChildren();
