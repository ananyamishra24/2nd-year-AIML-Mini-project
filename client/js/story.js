/* ─── Story Viewer ────────────────────────────────────── */

let story      = null;
let pages      = [];
let currentPage = 0;
let isCrayon   = false;
let isFav      = false;

// Narration state
let synth      = window.speechSynthesis;
let utterance  = null;
let voiceList  = [];

// Translation cache & state
const transCache = {};  // { `${lang}:${pageIdx}`: translatedText }
let   currentLang = 'en';

// ── Utils ──────────────────────────────────────────────
function storyId() {
  return location.pathname.split('/').pop();
}
function showToast(msg, type = 'success') {
  const c = document.getElementById('toast-container');
  const t = document.createElement('div');
  t.className = `toast ${type}`;
  t.textContent = msg;
  c.appendChild(t);
  setTimeout(() => t.remove(), 3000);
}

// ── Load story ─────────────────────────────────────────
async function loadStory() {
  try {
    const res = await fetch(`/api/stories/${storyId()}`);
    if (!res.ok) throw new Error('Not found');
    story = await res.json();
    pages = typeof story.pages === 'string' ? JSON.parse(story.pages) : (story.pages || []);
    isFav = !!story.isFavorite;
    document.title = `${story.storyTitle} · Brave Story Maker`;
    updateFavBtn();
    renderPage();
  } catch {
    document.getElementById('story-card').innerHTML =
      '<div style="padding:3rem;text-align:center;color:var(--destructive)">Story not found. <a href="/">Go home</a></div>';
  }
}

// ── Render page ────────────────────────────────────────
function renderPage() {
  stopNarration();
  const page = pages[currentPage];
  if (!page) return;

  // Image
  const img   = document.getElementById('story-img');
  const ph    = document.getElementById('img-placeholder');
  const pageLabel = document.getElementById('img-page-label');
  if (pageLabel) pageLabel.textContent = `Page ${currentPage + 1}`;
  if (page.imageUrl) {
    img.src = page.imageUrl;
    img.alt = story.storyTitle;
    img.style.display = 'block';
    ph.style.display  = 'none';
    img.classList.add('fade-in');
    img.onload = () => img.classList.remove('fade-in');
  } else {
    img.style.display = 'none';
    ph.style.display  = 'flex';
  }

  // Text
  const text = getDisplayText();
  renderText(text);
  updatePageBadge();
  updateNavBtns();
}

function getDisplayText() {
  if (currentLang === 'en') {
    return pages[currentPage]?.text || '';
  }
  const key = `${currentLang}:${currentPage}`;
  if (transCache[key]) return transCache[key];
  return pages[currentPage]?.text || '';
}

function renderText(raw) {
  const container = document.getElementById('story-text-content');
  container.classList.toggle('crayon-mode', isCrayon);

  const trimmed = raw.trim();
  if (!trimmed) { container.innerHTML = ''; return; }

  const allWords = trimmed.split(/\s+/);
  let out = '';
  allWords.forEach((w, i) => {
    out += `<span class="word-span" data-idx="${i}">${escHtml(w)}</span> `;
  });
  container.innerHTML = out;
}

function escHtml(s) {
  const d = document.createElement('div');
  d.textContent = s;
  return d.innerHTML;
}

function updatePageBadge() {
  document.getElementById('page-badge').textContent = `Page ${currentPage + 1} of ${pages.length}`;
}

function updateNavBtns() {
  const prev = document.getElementById('prev-btn');
  const next = document.getElementById('next-btn');
  prev.disabled = currentPage === 0;
  const isLast = currentPage === pages.length - 1;
  if (isLast) {
    next.textContent = '';
    next.innerHTML = `New Story
      <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none"
        stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
        <path d="M12 5v14M5 12h14"/>
      </svg>`;
    next.onclick = () => window.location.href = '/create';
  } else {
    next.innerHTML = `Next
      <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none"
        stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
        <path d="M9 18l6-6-6-6"/>
      </svg>`;
    next.onclick = () => changePage(1);
  }
}

function changePage(delta) {
  stopNarration();
  const next = currentPage + delta;
  if (next < 0 || next >= pages.length) return;
  currentPage = next;
  renderPage();
  // animate card
  const card = document.getElementById('story-card');
  card.classList.remove('fade-in');
  void card.offsetWidth;
  card.classList.add('fade-in');
}

// ── Narration ──────────────────────────────────────────
function loadVoices() {
  voiceList = synth.getVoices();
  const sel = document.getElementById('voice-select');
  sel.innerHTML = '';
  const engVoices = voiceList.filter(v => v.lang.startsWith('en'));
  const list = engVoices.length ? engVoices : voiceList;
  list.forEach((v, i) => {
    const opt = document.createElement('option');
    opt.value = i;
    opt.textContent = `${v.name} (${v.lang})`;
    sel.appendChild(opt);
  });
  if (!list.length) {
    document.getElementById('voice-row').style.display = 'none';
  }
}

function startNarration() {
  if (!synth) return;
  stopNarration();

  const text  = getDisplayText();
  const words = text.trim().split(/\s+/);
  utterance   = new SpeechSynthesisUtterance(text);

  const speedVal = parseFloat(document.getElementById('speed-range').value);
  utterance.rate  = speedVal;
  utterance.pitch = 1.1;

  const selIdx = parseInt(document.getElementById('voice-select').value, 10);
  const engVoices = voiceList.filter(v => v.lang.startsWith('en'));
  const list = engVoices.length ? engVoices : voiceList;
  if (list[selIdx]) utterance.voice = list[selIdx];

  utterance.onboundary = (e) => {
    if (e.name !== 'word') return;
    // find word index from charIndex
    const before = text.slice(0, e.charIndex);
    const idx    = before.trim() === '' ? 0 : before.trim().split(/\s+/).length;
    clearHighlight();
    const spans = document.querySelectorAll('.word-span');
    const target = [...spans].find(s => parseInt(s.dataset.idx) === idx);
    if (target) {
      target.classList.add('highlighted');
      target.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
  };

  utterance.onend = () => {
    clearHighlight();
    updateNarrateIcon(false);
  };

  synth.speak(utterance);
  updateNarrateIcon(true);
}

function stopNarration() {
  if (synth) synth.cancel();
  clearHighlight();
  updateNarrateIcon(false);
}

function clearHighlight() {
  document.querySelectorAll('.word-span.highlighted').forEach(el => el.classList.remove('highlighted'));
}

function updateNarrateIcon(playing) {
  const btn = document.getElementById('narrate-btn');
  const icon = document.getElementById('narrate-icon');
  if (playing) {
    btn.classList.add('playing');
    // swap to pause icon
    icon.innerHTML = '<rect x="6" y="4" width="4" height="16"/><rect x="14" y="4" width="4" height="16"/>';
    btn.title = 'Pause narration';
  } else {
    btn.classList.remove('playing');
    // swap to play icon
    icon.innerHTML = '<polygon points="5 3 19 12 5 21 5 3"/>';
    btn.title = 'Read aloud';
  }
}

// ── Translation ────────────────────────────────────────
async function translatePage(lang) {
  if (lang === 'en') {
    currentLang = 'en';
    renderPage();
    return;
  }
  const key = `${lang}:${currentPage}`;
  if (transCache[key]) {
    currentLang = lang;
    renderPage();
    return;
  }

  const text   = pages[currentPage]?.text || '';
  if (!text) return;

  // Chunk into ≤ 500 char pieces at sentence boundary
  const chunks = chunkText(text, 450);
  const translated = [];
  for (const chunk of chunks) {
    const url = `https://api.mymemory.translated.net/get?q=${encodeURIComponent(chunk)}&langpair=en|${lang}`;
    try {
      const r = await fetch(url);
      const d = await r.json();
      translated.push(d.responseData?.translatedText || chunk);
    } catch {
      translated.push(chunk);
    }
  }
  transCache[key] = translated.join(' ');
  currentLang = lang;
  renderPage();
}

function chunkText(text, maxLen) {
  if (text.length <= maxLen) return [text];
  const chunks = [];
  let remaining = text;
  while (remaining.length > maxLen) {
    let split = remaining.lastIndexOf('. ', maxLen);
    if (split < 0) split = remaining.lastIndexOf(' ', maxLen);
    if (split < 0) split = maxLen;
    chunks.push(remaining.slice(0, split + 1).trim());
    remaining = remaining.slice(split + 1).trim();
  }
  if (remaining) chunks.push(remaining);
  return chunks;
}

// ── Favourite ──────────────────────────────────────────
async function toggleFav() {
  try {
    const res = await fetch(`/api/stories/${storyId()}/favorite`, { method: 'POST' });
    if (!res.ok) throw new Error();
    const data = await res.json();
    isFav = data.isFavorite;
    updateFavBtn();
    showToast(isFav ? 'Added to favourites!' : 'Removed from favourites');
  } catch {
    showToast('Could not update favourite', 'error');
  }
}
function updateFavBtn() {
  const btn  = document.getElementById('fav-btn');
  const icon = document.getElementById('fav-icon');
  if (isFav) {
    btn.classList.add('active');
    icon.setAttribute('fill', 'currentColor');
  } else {
    btn.classList.remove('active');
    icon.setAttribute('fill', 'none');
  }
}

// ── Popovers ───────────────────────────────────────────
function setupPopovers() {
  // Big green play button — toggle narration
  document.getElementById('narrate-btn').addEventListener('click', (e) => {
    e.stopPropagation();
    if (synth.speaking) { stopNarration(); } else { startNarration(); }
  });
  // Reset button — stop & restart
  document.getElementById('reset-btn').addEventListener('click', (e) => {
    e.stopPropagation();
    stopNarration();
    startNarration();
  });
  // Volume/settings button — opens narration panel
  document.getElementById('volume-btn').addEventListener('click', (e) => {
    e.stopPropagation();
    togglePanel('narrate-panel');
    closePanel('translate-panel');
  });
  // Translate button
  document.getElementById('translate-btn').addEventListener('click', (e) => {
    e.stopPropagation();
    togglePanel('translate-panel');
    closePanel('narrate-panel');
  });
  document.addEventListener('click', () => {
    closePanel('narrate-panel');
    closePanel('translate-panel');
  });
  document.querySelectorAll('.popover-panel').forEach(p =>
    p.addEventListener('click', e => e.stopPropagation())
  );
}
function togglePanel(id) {
  const p = document.getElementById(id);
  p.classList.toggle('hidden');
}
function closePanel(id) {
  document.getElementById(id).classList.add('hidden');
}

// ── Event wiring ───────────────────────────────────────
document.getElementById('prev-btn').addEventListener('click', () => changePage(-1));
// next-btn handler set in updateNavBtns()

document.getElementById('fav-btn').addEventListener('click', toggleFav);

document.getElementById('font-toggle-btn').addEventListener('click', () => {
  isCrayon = !isCrayon;
  const btn = document.getElementById('font-toggle-btn');
  btn.classList.toggle('active', isCrayon);
  renderPage();
});

document.getElementById('speed-range').addEventListener('input', (e) => {
  document.getElementById('speed-val').textContent = `${parseFloat(e.target.value).toFixed(1)}×`;
  if (synth.speaking) { stopNarration(); startNarration(); }
});

document.getElementById('translate-go').addEventListener('click', async () => {
  const lang = document.getElementById('lang-select').value;
  closePanel('translate-panel');
  await translatePage(lang);
});
document.getElementById('translate-reset').addEventListener('click', () => {
  currentLang = 'en';
  document.getElementById('lang-select').value = 'en';
  closePanel('translate-panel');
  renderPage();
});

// Voices may load async
if (speechSynthesis.onvoiceschanged !== undefined) {
  speechSynthesis.onvoiceschanged = loadVoices;
}

// ── Init ───────────────────────────────────────────────
setupPopovers();
loadVoices();
loadStory();
