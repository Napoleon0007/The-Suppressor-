// ---- format map (mirrors engine/convert.py TARGETS) ----
const TARGETS = {
  image: ['jpg', 'png', 'webp', 'tiff', 'gif', 'bmp', 'pdf'],
  audio: ['mp3', 'wav', 'flac', 'm4a', 'opus', 'ogg'],
  video: ['mp4', 'mov', 'mkv', 'webm', 'avi', 'gif', 'mp3', 'm4a'],
  pdf: [],
  other: [],
};
const EXT2CAT = {};
[['image', 'jpg jpeg png gif webp tif tiff bmp'],
 ['audio', 'wav flac ogg mp3 m4a aac aiff aif opus'],
 ['video', 'mp4 mov m4v mkv webm avi wmv flv'],
 ['pdf', 'pdf']].forEach(([cat, exts]) =>
  exts.split(' ').forEach(e => { EXT2CAT[e] = cat; }));

function extOf(name) { return (name.split('.').pop() || '').toLowerCase(); }
function catOf(name) { return EXT2CAT[extOf(name)] || 'other'; }

// ---- DOM ----
const drop = document.getElementById('drop');
const input = document.getElementById('file-input');
const browse = document.getElementById('browse');
const queueWrap = document.getElementById('queue-wrap');
const queueEl = document.getElementById('queue');
const runBtn = document.getElementById('run');
const clearBtn = document.getElementById('clear');
const statusEl = document.getElementById('status');
const statusText = document.getElementById('status-text');
const results = document.getElementById('results');
const totals = document.getElementById('totals');

let queue = [];           // [{file, target}]
let totalIn = 0, totalOut = 0;

browse.addEventListener('click', () => input.click());
input.addEventListener('change', () => { addFiles(input.files); input.value = ''; });

['dragenter', 'dragover'].forEach(ev =>
  drop.addEventListener(ev, e => { e.preventDefault(); drop.classList.add('drag'); }));
['dragleave', 'drop'].forEach(ev =>
  drop.addEventListener(ev, e => { e.preventDefault(); drop.classList.remove('drag'); }));
drop.addEventListener('drop', e => addFiles(e.dataTransfer.files));

clearBtn.addEventListener('click', () => { queue = []; renderQueue(); });
runBtn.addEventListener('click', run);

function addFiles(fileList) {
  for (const f of fileList) queue.push({ file: f, target: 'auto' });
  renderQueue();
}

function renderQueue() {
  if (!queue.length) { queueWrap.classList.add('hidden'); queueEl.innerHTML = ''; return; }
  queueWrap.classList.remove('hidden');
  queueEl.innerHTML = '';

  queue.forEach((item, i) => {
    const cat = catOf(item.file.name);
    const ext = extOf(item.file.name);
    const opts = ['<option value="auto">Auto · compress (keep .' + escape(ext) + ')</option>'];
    TARGETS[cat].filter(t => t !== ext && !(t === 'jpg' && ext === 'jpeg'))
      .forEach(t => { opts.push(`<option value="${t}">→ ${t.toUpperCase()}</option>`); });

    const row = document.createElement('div');
    row.className = 'qrow';
    row.innerHTML = `
      <span class="qname" title="${escape(item.file.name)}">${escape(item.file.name)}</span>
      <span class="qcat">${cat}</span>
      <select class="qsel" data-i="${i}" ${TARGETS[cat].length ? '' : 'disabled'}>${opts.join('')}</select>
      <button class="qdel" data-i="${i}" title="remove">✕</button>`;
    queueEl.appendChild(row);
  });

  queueEl.querySelectorAll('.qsel').forEach(sel =>
    sel.addEventListener('change', e => { queue[+e.target.dataset.i].target = e.target.value; }));
  queueEl.querySelectorAll('.qdel').forEach(btn =>
    btn.addEventListener('click', e => { queue.splice(+e.target.dataset.i, 1); renderQueue(); }));
}

async function run() {
  if (!queue.length) return;
  const fd = new FormData();
  queue.forEach(item => { fd.append('files', item.file); fd.append('targets', item.target); });

  queueWrap.classList.add('hidden');
  statusEl.classList.remove('hidden');
  statusText.textContent = `WORKING ON ${queue.length} FILE${queue.length > 1 ? 'S' : ''}…`;

  try {
    const res = await fetch('/compress', { method: 'POST', body: fd });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.error || `server error ${res.status}`);
    }
    const data = await res.json();
    data.results.forEach(render);
    queue = [];
  } catch (e) {
    const card = document.createElement('div');
    card.className = 'card skip';
    card.innerHTML = `<div class="card-top"><span class="fname">UPLOAD FAILED</span></div>
      <div class="sizes">${escape(e.message)}</div>`;
    results.prepend(card);
    queueWrap.classList.toggle('hidden', !queue.length);
  } finally {
    statusEl.classList.add('hidden');
  }
}

function render(r) {
  const pct = r.saved_pct;
  const grew = pct < 0;
  const win = pct >= 75;
  const some = pct > 0 && pct < 75;
  const pctClass = win ? 'win' : some ? 'mid' : grew ? 'grew' : 'none';
  const cardClass = win ? 'win' : r.status === 'skip' ? 'skip' : '';

  const label = grew ? '+' + Math.abs(pct) + '%' : (pct > 0 ? '-' + pct + '%' : '0%');
  const tag = r.format_changed
    ? ` <span class="tag">${escape(r.out_name.split('.').pop().toUpperCase())}</span>` : '';
  const barW = Math.max(2, Math.min(100, pct));

  const card = document.createElement('div');
  card.className = `card ${cardClass}`;
  card.innerHTML = `
    <div class="card-top">
      <span class="fname">${escape(r.name)} ${tag}</span>
      <span class="pct ${pctClass}">${label}</span>
    </div>
    <div class="sizes"><b>${r.original_h}</b><span class="arrow">▶</span><b>${r.output_h}</b></div>
    <div class="bar"><i style="width:${barW}%"></i></div>
    <div class="meta">
      <span class="method">${escape(r.method)}${r.note ? ' · ' + escape(r.note) : ''}</span>
      <a class="dl" href="/download/${r.id}" download>DOWNLOAD</a>
    </div>`;
  results.prepend(card);

  totalIn += parseSize(r.original_h);
  totalOut += parseSize(r.output_h);
  if (totalIn > 0) {
    const saved = (1 - totalOut / totalIn) * 100;
    totals.textContent = `SESSION: ${saved.toFixed(1)}% SAVED`;
  }
}

function parseSize(h) {
  const [n, u] = h.split(' ');
  const mult = { B: 1, KB: 1024, MB: 1024 ** 2, GB: 1024 ** 3, TB: 1024 ** 4 }[u] || 1;
  return parseFloat(n) * mult;
}

function escape(s) {
  const d = document.createElement('div');
  d.textContent = s;
  return d.innerHTML;
}
