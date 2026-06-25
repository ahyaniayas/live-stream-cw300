// ── Warna zona (cocok dengan ZONE_PALETTE Python, konversi BGR→RGB) ──────────
const ZONE_COLORS = ['#00C832','#FFA500','#C832FF','#00C8FF','#FF00C8'];
function zoneColor(id) { return ZONE_COLORS[id % ZONE_COLORS.length]; }

// ── Stream & loader ───────────────────────────────────────────────────────────
let detectOn   = true;
let serverDown = false;
const loader   = document.getElementById('loader');
const loaderP  = loader.querySelector('p');
const feed     = document.getElementById('feed');

function reloadFeed() {
  loaderP.textContent = 'Menghubungkan ke kamera...';
  loader.classList.remove('hidden');
  feed.src = '/video_feed?' + Date.now();
  feed.addEventListener('load', () => loader.classList.add('hidden'), { once:true });
}
feed.addEventListener('load', () => loader.classList.add('hidden'), { once:true });
document.addEventListener('visibilitychange', () => {
  if (document.visibilityState === 'visible') reloadFeed();
});

// ── Fullscreen ────────────────────────────────────────────────────────────────
const fsExitIcon = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none"
  stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
  <polyline points="4 14 10 14 10 20"/><polyline points="20 10 14 10 14 4"/>
  <line x1="10" y1="14" x2="3" y2="21"/><line x1="21" y1="3" x2="14" y2="10"/>
</svg>`;
const fsEnterIcon = document.getElementById('fsBtn').innerHTML;
function toggleFullscreen() {
  const wrap = document.getElementById('videoWrap');
  if (!document.fullscreenElement) wrap.requestFullscreen();
  else document.exitFullscreen();
}
document.addEventListener('fullscreenchange', () => {
  document.getElementById('fsBtn').innerHTML =
    document.fullscreenElement ? fsExitIcon : fsEnterIcon;
});

// ── Zone Canvas Editor ────────────────────────────────────────────────────────
const canvas   = document.getElementById('zoneCanvas');
const ctx      = canvas.getContext('2d');
let editMode   = false;
let editZoneId      = null;
let editPoints      = [];
let zonesData       = [];
let zonesLoaded     = false;
const pendingNotify = new Set();

function syncCanvas() {
  const r = canvas.getBoundingClientRect();
  canvas.width  = r.width;
  canvas.height = r.height;
}
window.addEventListener('resize', () => { syncCanvas(); if(editMode) drawEditPolygon(); });
syncCanvas();

function drawEditPolygon() {
  syncCanvas();
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  if (!editPoints.length) return;
  const color = editZoneId !== null ? zoneColor(editZoneId) : '#f97316';
  const px    = editPoints.map(([x,y]) => [x*canvas.width, y*canvas.height]);

  ctx.beginPath();
  ctx.moveTo(px[0][0], px[0][1]);
  px.slice(1).forEach(([x,y]) => ctx.lineTo(x,y));
  if (px.length > 2) ctx.closePath();
  ctx.strokeStyle = color; ctx.lineWidth = 2; ctx.stroke();
  if (px.length > 2) { ctx.fillStyle = color+'26'; ctx.fill(); }
  px.forEach(([x,y], i) => {
    ctx.beginPath(); ctx.arc(x,y,5,0,Math.PI*2);
    ctx.fillStyle = i===0 ? '#fff' : color; ctx.fill();
  });

  const n = editPoints.length;
  document.getElementById('editHint').textContent =
    n>=3 ? `${n} titik — klik Simpan atau tambah titik lagi`
         : `${n} titik — butuh minimal 3`;
}

canvas.addEventListener('click', e => {
  if (!editMode) return;
  const r = canvas.getBoundingClientRect();
  editPoints.push([
    parseFloat(((e.clientX-r.left)/r.width ).toFixed(4)),
    parseFloat(((e.clientY-r.top) /r.height).toFixed(4)),
  ]);
  drawEditPolygon();
});

function addZone() {
  editZoneId = null;
  editPoints = [];
  document.getElementById('zoneName').value = '';
  document.getElementById('editTitle').textContent = 'Tambah Zona Baru';
  openEditPanel();
}

function editZone(id) {
  const z = zonesData.find(z => z.id === id);
  if (!z) return;
  editZoneId = id;
  editPoints = z.points.map(p => [...p]);
  document.getElementById('zoneName').value = z.name;
  document.getElementById('editTitle').textContent = `Edit Zona: ${z.name}`;
  openEditPanel();
}

function openEditPanel() {
  editMode = true;
  syncCanvas(); ctx.clearRect(0, 0, canvas.width, canvas.height);
  canvas.style.pointerEvents = 'auto';
  canvas.style.cursor        = 'crosshair';
  document.getElementById('editPanel').classList.add('show');
  document.getElementById('editHint').textContent = 'Klik pada video untuk menambah titik zona.';
  drawEditPolygon();
}

function cancelEdit() {
  editMode = false;
  editPoints = [];
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  canvas.style.pointerEvents = 'none';
  canvas.style.cursor        = '';
  document.getElementById('editPanel').classList.remove('show');
}

function undoPoint() { editPoints.pop(); drawEditPolygon(); }

async function saveZone() {
  const name = document.getElementById('zoneName').value.trim();
  if (!name) { alert('Masukkan nama zona terlebih dahulu.'); return; }
  if (editPoints.length < 3) { alert('Minimal 3 titik untuk membuat zona.'); return; }

  if (editZoneId === null) {
    await fetch('/zones', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({ name, points: editPoints }),
    });
  } else {
    await fetch(`/zones/${editZoneId}`, {
      method:'PUT', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({ name, points: editPoints }),
    });
  }
  cancelEdit();
  forceRefreshZones();
}

// ── Zone Cards ────────────────────────────────────────────────────────────────
function renderZoneCards(zones) {
  const el = document.getElementById('zoneCards');
  if (!zones.length) {
    el.innerHTML = '<p class="empty">Belum ada zona. Klik "+ Tambah Zona" untuk mulai.</p>';
    return;
  }
  el.innerHTML = zones.map(z => {
    const c   = zoneColor(z.id);
    const hot = z.current_count > 0;
    return `
      <div class="zone-card ${z.active?'alert':''}" id="zone-card-${z.id}"
           style="border-color:${c};${z.active?'box-shadow:0 0 0 3px '+c+'30':''}">
        <div class="zone-card-header">
          <div class="zone-dot ${z.active?'active':''}" id="zone-dot-${z.id}"></div>
          <span class="zone-card-name" title="${z.name}">${z.name}</span>
        </div>
        <div class="zone-card-stats">
          <div class="zone-stat">
            <div class="zone-stat-val ${hot?'hot':''}" id="zs-curr-${z.id}">${z.current_count}</div>
            <div class="zone-stat-lbl">Saat ini</div>
          </div>
          <div class="zone-stat">
            <div class="zone-stat-val" id="zs-tot-${z.id}">${z.total_count}</div>
            <div class="zone-stat-lbl">Total</div>
          </div>
          <div class="zone-stat">
            <div class="zone-stat-val">${z.point_count}</div>
            <div class="zone-stat-lbl">Titik</div>
          </div>
        </div>
        <div class="zone-notify-toggle" title="Notifikasi Telegram">
          <span class="zone-notify-icon" id="zone-notify-icon-${z.id}">${z.notify?'🔔':'🔕'}</span>
          <label class="toggle-switch toggle-switch-sm">
            <input type="checkbox" id="zone-notify-chk-${z.id}" ${z.notify?'checked':''} onchange="toggleZoneNotify(${z.id})">
            <span class="toggle-track"></span>
          </label>
        </div>
        <div class="zone-card-actions">
          <button class="btn btn-panel btn-sm" onclick="resetZone(${z.id})">Reset</button>
          <button class="btn btn-panel btn-sm" onclick="editZone(${z.id})">Edit</button>
          <button class="btn btn-red   btn-sm" onclick="deleteZone(${z.id})">Hapus</button>
        </div>
      </div>`;
  }).join('');
}

function updateAlertBanner(zones) {
  const active = zones.filter(z => z.active);
  const banner = document.getElementById('gateBanner');
  if (active.length) {
    banner.classList.remove('hidden');
    document.getElementById('bannerText').textContent =
      'ORANG TERDETEKSI DI: ' + active.map(z => z.name.toUpperCase()).join(', ');
  } else {
    banner.classList.add('hidden');
  }
}

async function fetchZones() {
  try {
    const r     = await fetch('/zones', { signal: AbortSignal.timeout(2000) });
    const fresh = await r.json();
    const sameList = fresh.length === zonesData.length &&
      fresh.every((z, i) => z.id === zonesData[i]?.id);
    zonesLoaded = true;
    if (!sameList) {
      zonesData = fresh;
      renderZoneCards(zonesData);
      updateAlertBanner(zonesData);
      return;
    }
    const prev = zonesData;
    zonesData = fresh.map(z => {
      const curr = document.getElementById(`zs-curr-${z.id}`);
      const tot  = document.getElementById(`zs-tot-${z.id}`);
      const card = document.getElementById(`zone-card-${z.id}`);
      const dot  = document.getElementById(`zone-dot-${z.id}`);
      if (curr) { curr.textContent = z.current_count; curr.className = 'zone-stat-val' + (z.current_count > 0 ? ' hot' : ''); }
      if (tot)  tot.textContent = z.total_count;
      if (card) card.className  = 'zone-card' + (z.active ? ' alert' : '');
      if (dot)  dot.className   = 'zone-dot'  + (z.active ? ' active' : '');
      if (pendingNotify.has(z.id)) {
        const local = prev.find(l => l.id === z.id);
        return local ? { ...z, notify: local.notify } : z;
      }
      return z;
    });
    updateAlertBanner(zonesData);
  } catch(_) {}
}

async function forceRefreshZones() {
  try {
    const r   = await fetch('/zones', { signal: AbortSignal.timeout(2000) });
    zonesData = await r.json();
    zonesLoaded = true;
    renderZoneCards(zonesData);
    updateAlertBanner(zonesData);
  } catch(_) {}
}

async function resetZone(id) {
  await fetch(`/zones/${id}/reset`, { method:'POST' });
}

async function deleteZone(id) {
  const z = zonesData.find(z => z.id === id);
  if (!confirm(`Hapus zona "${z?.name}"?`)) return;
  await fetch(`/zones/${id}`, { method:'DELETE' });
  if (editZoneId === id) cancelEdit();
  forceRefreshZones();
}

// ── Time input helpers (force HH:MM 24h on all browsers) ─────────────────────
function onTimeInput(el) {
  const digits = el.value.replace(/\D/g, '').slice(0, 4);
  el.value = digits.length >= 3 ? digits.slice(0, 2) + ':' + digits.slice(2) : digits;
}
function onTimeBlur(el) {
  const m = el.value.match(/^(\d{1,2}):(\d{2})$/);
  if (!m) { el.value = el.defaultValue; return; }
  const h   = Math.min(parseInt(m[1], 10), 23).toString().padStart(2, '0');
  const min = Math.min(parseInt(m[2], 10), 59).toString().padStart(2, '0');
  el.value  = h + ':' + min;
}

// ── Settings modal ────────────────────────────────────────────────────────────
function openSettings() {
  document.getElementById('settingsBackdrop').classList.add('open');
  fetchNotifSettings();
}
function closeSettings() { document.getElementById('settingsBackdrop').classList.remove('open'); }
document.addEventListener('keydown', e => { if (e.key==='Escape') { closeSettings(); closeHistModal(); } });

async function fetchNotifSettings() {
  try {
    const r = await fetch('/notif/settings');
    const d = await r.json();
    document.getElementById('notifInterval').value  = Math.round(d.interval / 60);
    document.getElementById('notifAlwaysOn').checked = d.always_on || false;
    document.getElementById('notifStart').value     = d.time_start;
    document.getElementById('notifEnd').value       = d.time_end;
    _applyAlwaysOn(d.always_on || false);
  } catch(_) {}
}

function onAlwaysOnChange() {
  _applyAlwaysOn(document.getElementById('notifAlwaysOn').checked);
}

function _applyAlwaysOn(on) {
  const row = document.getElementById('notifTimeRow');
  row.style.opacity      = on ? '0.4' : '1';
  row.style.pointerEvents = on ? 'none' : '';
}

async function saveNotifSettings() {
  const minutes = parseInt(document.getElementById('notifInterval').value) || 5;
  const body    = {
    interval:   minutes * 60,
    always_on:  document.getElementById('notifAlwaysOn').checked,
    time_start: document.getElementById('notifStart').value,
    time_end:   document.getElementById('notifEnd').value,
  };
  try {
    await fetch('/notif/settings', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(body),
    });
    _setNotifStatus('Pengaturan disimpan.', true);
  } catch(_) { _setNotifStatus('Gagal menyimpan.', false); }
}

async function testNotif() {
  _setNotifStatus('Mengirim...', true);
  try {
    const r = await fetch('/notif/test', { method:'POST' });
    const d = await r.json();
    _setNotifStatus(d.ok ? 'Pesan tes terkirim!' : 'Gagal: ' + d.message, d.ok);
  } catch(_) { _setNotifStatus('Gagal terhubung ke server.', false); }
}

function _setNotifStatus(msg, ok) {
  const el = document.getElementById('notifStatus');
  el.textContent = msg;
  el.className   = 'notif-status ' + (ok ? 'ok' : 'err');
  setTimeout(() => { el.textContent = ''; el.className = 'notif-status'; }, 4000);
}

function _renderHistItems(items) {
  if (!items.length) return '<span class="empty">Belum ada notifikasi terkirim.</span>';
  return items.map(h => `
    <div class="notif-hist-item">
      <span class="notif-hist-icon">🔔</span>
      <div class="notif-hist-info">
        <div class="notif-hist-zone">${h.zone}</div>
        <div class="notif-hist-time">${h.time}</div>
      </div>
      <span class="notif-hist-count">${h.count} orang</span>
    </div>`).join('');
}

async function toggleHistAll() {
  document.getElementById('histModalBackdrop').classList.add('open');
  const el  = document.getElementById('histModalList');
  const hdr = document.getElementById('histModalTitle');
  el.innerHTML = '<span class="empty">Memuat...</span>';
  hdr.textContent = 'Semua Riwayat Notifikasi';
  try {
    const r = await fetch('/notif/history');
    const d = await r.json();
    hdr.textContent = `Semua Riwayat Notifikasi (${d.length})`;
    el.innerHTML = _renderHistItems(d);
  } catch(_) { el.innerHTML = '<span class="empty">Gagal memuat.</span>'; }
}

function closeHistModal() {
  document.getElementById('histModalBackdrop').classList.remove('open');
}

function _applyZoneNotifyUI(id, on) {
  const icon = document.getElementById(`zone-notify-icon-${id}`);
  const chk  = document.getElementById(`zone-notify-chk-${id}`);
  if (icon) icon.textContent = on ? '🔔' : '🔕';
  if (chk)  chk.checked = on;
}

async function toggleZoneNotify(id) {
  if (pendingNotify.has(id)) return;
  const z = zonesData.find(z => z.id === id);
  if (!z) return;
  pendingNotify.add(id);
  z.notify = !z.notify;
  _applyZoneNotifyUI(id, z.notify);
  try {
    const r = await fetch(`/zones/${id}/notify`, { method:'POST' });
    const d = await r.json();
    z.notify = d.notify;
  } catch(_) {
    z.notify = !z.notify;
  } finally {
    pendingNotify.delete(id);
    _applyZoneNotifyUI(id, z.notify);
  }
}

// ── Toggle controls ───────────────────────────────────────────────────────────
async function toggleDetect() {
  const r = await fetch('/detect/toggle', { method:'POST' });
  const d = await r.json();
  detectOn = d.enabled;
  document.getElementById('detectToggle').checked = detectOn;
}

async function toggleBoxes() {
  const r = await fetch('/overlay/toggle/boxes', { method:'POST' });
  const d = await r.json();
  document.getElementById('showBoxesToggle').checked = d.enabled;
}

async function toggleNames() {
  const r = await fetch('/overlay/toggle/names', { method:'POST' });
  const d = await r.json();
  document.getElementById('showNamesToggle').checked = d.enabled;
}

async function toggleCategory(cat) {
  const r = await fetch('/detect/category/toggle', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({cat}),
  });
  const d = await r.json();
  document.getElementById(
    cat === 'person' ? 'catPerson' : cat === 'vehicle' ? 'catVehicle' : 'catOther'
  ).checked = d.enabled;
}

// ── Poll /status ──────────────────────────────────────────────────────────────
async function pollStatus() {
  try {
    const r = await fetch('/status', { signal: AbortSignal.timeout(2000) });
    const d = await r.json();
    if (serverDown) { serverDown=false; reloadFeed(); }
    document.getElementById('detectToggle').checked    = d.enabled;
    document.getElementById('showBoxesToggle').checked = d.show_boxes;
    document.getElementById('showNamesToggle').checked = d.show_names;

    // Notif summary
    if (d.notif_always_on != null) {
      const settingsOpen = document.getElementById('settingsBackdrop').classList.contains('open');
      if (!settingsOpen) {
        document.getElementById('notifAlwaysOn').checked = d.notif_always_on;
        _applyAlwaysOn(d.notif_always_on);
      }
    }
    if (d.notif_cooldown != null) {
      const el      = document.getElementById('notifCooldownBadge');
      const inWin   = d.notif_in_window;
      const cd      = d.notif_cooldown;
      const mins    = Math.round((d.notif_interval || 0) / 60);
      const timeStr = d.notif_always_on
        ? 'Selalu Aktif'
        : (d.notif_time_start + ' – ' + d.notif_time_end);
      document.getElementById('notifTooltipInterval').textContent = `Interval: ${mins} menit`;
      document.getElementById('notifTooltipTime').textContent     = `Jam: ${timeStr}`;

      if (zonesLoaded && zonesData.length === 0) {
        el.textContent = 'Tidak ada zona';
        el.className   = 'notif-badge notif-badge-err';
      } else if (zonesLoaded && !zonesData.some(z => z.notify)) {
        el.textContent = 'Notifikasi Mati';
        el.className   = 'notif-badge notif-badge-err';
      } else if (cd > 0) {
        const m = Math.floor(cd / 60);
        const s = cd % 60;
        el.textContent = (m > 0 ? m + 'm ' : '') + s + 's';
        el.className   = 'notif-badge notif-badge-warn';
      } else if (!inWin && !d.notif_always_on) {
        el.textContent = 'Tidak Aktif';
        el.className   = 'notif-badge notif-badge-err';
      } else {
        el.textContent = 'Siap';
        el.className   = 'notif-badge notif-badge-ok';
      }
    }
    if (d.notif_history != null) {
      document.getElementById('notifHistList').innerHTML = _renderHistItems(d.notif_history);
    }
    if (d.categories) {
      document.getElementById('catPerson').checked  = d.categories.person;
      document.getElementById('catVehicle').checked = d.categories.vehicle;
      document.getElementById('catOther').checked   = d.categories.other;
    }

    if (!d.stream_connected) {
      loaderP.textContent = 'Menghubungkan ke kamera...';
      loader.classList.remove('hidden');
      document.getElementById('fpsBadge').textContent = '–';
      document.getElementById('detList').innerHTML =
        '<span class="empty">Stream tidak terhubung</span>';
    } else {
      loader.classList.add('hidden');
      document.getElementById('fpsBadge').textContent = d.fps>0 ? d.fps+' fps' : '–';
      const list = document.getElementById('detList');
      if (!d.enabled || !Object.keys(d.counts).length) {
        list.innerHTML = '<span class="empty">'+(d.enabled?'Tidak ada objek':'Deteksi nonaktif')+'</span>';
      } else {
        list.innerHTML = Object.entries(d.counts)
          .sort((a,b)=>b[1]-a[1])
          .map(([l,c])=>`<div class="chip">${l}<span class="cnt">${c}</span></div>`)
          .join('');
      }
    }
  } catch(_) {
    if (!serverDown) {
      serverDown=true;
      loaderP.textContent='Server tidak aktif, menunggu...';
      loader.classList.remove('hidden');
      document.getElementById('fpsBadge').textContent='–';
    }
  }
  setTimeout(pollStatus, 1000);
}

// ── Poll zona setiap 1 detik ──────────────────────────────────────────────────
function pollZones() {
  fetchZones().finally(() => setTimeout(pollZones, 1000));
}

pollStatus();
pollZones();
