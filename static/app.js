const drop = document.getElementById('drop');
const input = document.getElementById('file-input');
const browse = document.getElementById('browse');
const statusEl = document.getElementById('status');
const statusText = document.getElementById('status-text');
const results = document.getElementById('results');
const totals = document.getElementById('totals');

let totalIn = 0, totalOut = 0;

browse.addEventListener('click', () => input.click());
input.addEventListener('change', () => { if (input.files.length) send(input.files); });

['dragenter', 'dragover'].forEach(ev =>
  drop.addEventListener(ev, e => { e.preventDefault(); drop.classList.add('drag'); }));
['dragleave', 'drop'].forEach(ev =>
  drop.addEventListener(ev, e => { e.preventDefault(); drop.classList.remove('drag'); }));
drop.addEventListener('drop', e => {
  const files = e.dataTransfer.files;
  if (files.length) send(files);
});

async function send(fileList) {
  const fd = new FormData();
  for (const f of fileList) fd.append('files', f);

  statusEl.classList.remove('hidden');
  statusText.textContent = `COMPRESSING ${fileList.length} FILE${fileList.length > 1 ? 'S' : ''}…`;

  try {
    const res = await fetch('/compress', { method: 'POST', body: fd });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.error || `server error ${res.status}`);
    }
    const data = await res.json();
    data.results.forEach(render);
  } catch (e) {
    const card = document.createElement('div');
    card.className = 'card skip';
    card.innerHTML = `<div class="card-top"><span class="fname">UPLOAD FAILED</span></div>
      <div class="sizes">${escape(e.message)}</div>`;
    results.prepend(card);
  } finally {
    statusEl.classList.add('hidden');
    input.value = '';
  }
}

function render(r) {
  const win = r.saved_pct >= 75;
  const some = r.saved_pct > 0 && r.saved_pct < 75;
  const pctClass = win ? 'win' : some ? 'mid' : 'none';
  const cardClass = win ? 'win' : r.status === 'skip' ? 'skip' : '';

  const tag = r.format_changed
    ? ` <span class="tag">→ ${escape(r.out_name.split('.').pop().toUpperCase())}</span>` : '';

  const card = document.createElement('div');
  card.className = `card ${cardClass}`;
  card.innerHTML = `
    <div class="card-top">
      <span class="fname">${escape(r.name)}</span>
      <span class="pct ${pctClass}">${r.saved_pct > 0 ? '-' + r.saved_pct + '%' : '0%'}</span>
    </div>
    <div class="sizes"><b>${r.original_h}</b><span class="arrow">▶</span><b>${r.output_h}</b></div>
    <div class="bar"><i style="width:${Math.max(2, r.saved_pct)}%"></i></div>
    <div class="meta">
      <span class="method">${escape(r.method)}${tag}${r.note ? ' · ' + escape(r.note) : ''}</span>
      <a class="dl" href="/download/${r.id}" download>DOWNLOAD</a>
    </div>`;
  results.prepend(card);

  // running totals
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
