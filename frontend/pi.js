(function () {
  const img = document.getElementById('server-stream');
  const overlayEl = document.getElementById('overlay');
  const overlayCtx = overlayEl.getContext('2d');
  const statusIndicator = document.getElementById('status-indicator');
  const activeModelEl = document.getElementById('active-model');
  const detectionCountEl = document.getElementById('detection-count');
  const detectionConfidenceEl = document.getElementById('detection-confidence');
  const errorMessageEl = document.getElementById('error-message');

  const backendOrigin = window.location.hostname === 'localhost'
    ? 'http://localhost:8080'
    : window.location.origin;

  function updateStatus(text, cls) {
    statusIndicator.textContent = text;
    statusIndicator.classList.remove('detected', 'error');
    if (cls) statusIndicator.classList.add(cls);
  }

  function resizeCanvasToImage() {
    const width = img.naturalWidth || img.clientWidth || 640;
    const height = img.naturalHeight || img.clientHeight || 480;
    overlayEl.width = width;
    overlayEl.height = height;
  }

  function drawDetections(detections) {
    overlayCtx.clearRect(0, 0, overlayEl.width, overlayEl.height);
    if (!Array.isArray(detections)) return;
    overlayCtx.strokeStyle = 'rgba(64,255,188,0.9)';
    overlayCtx.lineWidth = 2;
    overlayCtx.font = "14px 'Segoe UI', sans-serif";
    overlayCtx.fillStyle = 'rgba(10,17,31,0.8)';
    detections.forEach((d) => {
      if (!Array.isArray(d.bbox)) return;
      const [x1, y1, x2, y2] = d.bbox.map(Number);
      overlayCtx.strokeRect(x1, y1, x2 - x1, y2 - y1);
      const label = `${d.label ?? 'object'} ${(Math.round((Number(d.confidence||0))*1000)/10).toFixed(1)}%`;
      const w = overlayCtx.measureText(label).width + 10;
      const h = 20;
      const tx = Math.max(0, Math.min(x1, overlayEl.width - w));
      const ty = Math.max(0, y1 - h - 4);
      overlayCtx.fillRect(tx, ty, w, h);
      overlayCtx.fillStyle = 'rgba(64,255,188,0.9)';
      overlayCtx.fillText(label, tx + 5, ty + 4);
      overlayCtx.fillStyle = 'rgba(10,17,31,0.8)';
    });
  }

  // Pull detections status periodically to render overlay and meta
  async function pollStatus() {
    try {
      const res = await fetch(`${backendOrigin}/api/detections/status`);
      const payload = await res.json().catch(() => ({}));
      if (res.ok) {
        const detections = Array.isArray(payload.detections) ? payload.detections : [];
        detectionCountEl.textContent = String(detections.length);
        detectionConfidenceEl.textContent = detections.length
          ? String(Math.max(...detections.map(d => Number(d.confidence||0))))
          : '0';
        activeModelEl.textContent = payload.activeModel || payload.active || '—';
        drawDetections(detections);
        updateStatus('Онлайн');
      } else {
        updateStatus('Ошибка статуса', 'error');
      }
    } catch (e) {
      updateStatus('Нет связи', 'error');
      errorMessageEl.textContent = e instanceof Error ? e.message : 'Network error';
    } finally {
      setTimeout(pollStatus, 100);
    }
  }

  // Start MJPEG stream
  function startStream() {
    img.onload = () => {
      resizeCanvasToImage();
      updateStatus('Поток подключен');
    };
    img.onerror = () => {
      updateStatus('Ошибка потока', 'error');
      errorMessageEl.textContent = 'Не удалось подключиться к /api/detections/stream';
      setTimeout(startStream, 2000);
    };
    // Используем RAW поток без серверной разметки, рисуем боксы только на фронте
    img.src = `${backendOrigin}/api/detections/stream-raw?t=${Date.now()}`;
  }

  // -------- Saved detections logic ---------
  async function loadSavedDetections(dateValue) {
    try {
      const params = new URLSearchParams();
      if (dateValue) params.set('date', dateValue);
      const response = await fetch(`${backendOrigin}/api/detections/saved?${params.toString()}`);
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(payload.error || 'Не удалось загрузить сохранённые');
      }
      const items = Array.isArray(payload.items) ? payload.items : [];
      renderSavedList(items);
    } catch (err) {
      console.error('Ошибка загрузки сохранённых', err);
      renderSavedList([]);
    }
  }

  function renderSavedList(items) {
    const container = document.getElementById('saved-screen-list');
    if (!container) return;
    container.innerHTML = '';
    if (!items.length) {
      const p = document.createElement('p');
      p.style.color = '#93a4d2';
      p.style.textAlign = 'center';
      p.style.padding = '16px';
      p.textContent = 'Нет сохранённых элементов';
      container.appendChild(p);
      return;
    }

    items.forEach(item => {
      const card = document.createElement('div');
      card.className = 'saved-card';
      const thumb = document.createElement('div');
      thumb.className = 'saved-thumb';
      const img = document.createElement('img');
      img.src = item.gifPath ? `${backendOrigin}${item.gifPath}` : '';
      img.alt = item.id;
      img.loading = 'lazy';
      img.onerror = function() {
        console.error('Ошибка загрузки GIF:', this.src);
      };
      thumb.appendChild(img);
      const caption = document.createElement('div');
      caption.className = 'saved-caption';
      caption.textContent = item.id;
      card.append(thumb, caption);

      card.addEventListener('click', () => openGifModal(item));
      card.tabIndex = 0;
      card.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          openGifModal(item);
        }
      });
      container.appendChild(card);
    });
  }

  function formatTs(ts) {
    if (!Number.isFinite(ts)) return '—';
    try {
      const d = new Date(ts * 1000);
      return `${d.toLocaleDateString()} ${d.toLocaleTimeString()}`;
    } catch {
      return String(ts);
    }
  }

  function setMetaList(container, payload) {
    container.innerHTML = '';
    const add = (dt, dd) => {
      const dte = document.createElement('dt'); dte.textContent = dt;
      const dde = document.createElement('dd'); dde.textContent = dd;
      container.append(dte, dde);
    };
    if (!payload || typeof payload !== 'object') return;
    add('ID', payload.id || '—');
    add('Дата', payload.date || '—');
    add('Сохранено', formatTs(payload.savedAt));
    const det = payload.detection || {};
    add('Метка', det.label ?? 'object');
    add('TrackId', Number.isFinite(det.trackId) ? String(det.trackId) : String(det.id ?? '—'));
    add('Класс', det.classId == null ? '—' : String(det.classId));
    add('Уверенность', det.confidence == null ? '—' : String(det.confidence));
    add('BBox', Array.isArray(det.bbox) ? det.bbox.map((v)=>Math.round(Number(v)||0)).join(', ') : '—');
    add('Модель', det.model ?? payload.detection?.model ?? '—');
    add('Камера', det.cameraIndex == null ? '—' : String(det.cameraIndex));
    if (payload.gifPath) add('GIF', payload.gifPath);
    if (payload.jsonPath) add('JSON', payload.jsonPath);
  }

  function openGifModal(item) {
    const modal = document.getElementById('gif-modal');
    const img = document.getElementById('gif-modal-image');
    const list = document.getElementById('gif-modal-dl');
    if (!modal || !img || !list) return;

    const gifUrl = item.gifPath ? `${backendOrigin}${item.gifPath}` : '';
    const jsonUrl = item.jsonPath ? `${backendOrigin}${item.jsonPath}` : '';

    img.src = gifUrl;
    img.alt = item.id;

    if (jsonUrl) {
      fetch(jsonUrl)
        .then(r => r.json())
        .then(data => setMetaList(list, data))
        .catch(() => {
          setMetaList(list, { id: item.id, date: item.date, savedAt: null, detection: {}, gifPath: item.gifPath, jsonPath: item.jsonPath });
        });
    } else {
      setMetaList(list, { id: item.id, date: item.date, savedAt: null, detection: {}, gifPath: item.gifPath, jsonPath: item.jsonPath });
    }

    modal.classList.remove('hidden');
    modal.setAttribute('aria-hidden', 'false');

    const close = () => closeGifModal();
    document.getElementById('gif-modal-close').onclick = close;
    document.getElementById('gif-modal-backdrop').onclick = close;
    const onKey = (e) => { if (e.key === 'Escape') close(); };
    document.addEventListener('keydown', onKey, { once: true });
  }

  function closeGifModal() {
    const modal = document.getElementById('gif-modal');
    if (!modal) return;
    modal.classList.add('hidden');
    modal.setAttribute('aria-hidden', 'true');
    const img = document.getElementById('gif-modal-image');
    if (img) img.src = '';
  }

  // Screen switching logic
  function selectScreen(name) {
    const stream = document.getElementById('screen-stream');
    const saved = document.getElementById('screen-saved');
    const b1 = document.querySelector('.screen-button[data-screen="stream"]');
    const b2 = document.querySelector('.screen-button[data-screen="saved"]');
    if (!stream || !saved || !b1 || !b2) return;

    const showStream = name !== 'saved';
    stream.classList.toggle('hidden', !showStream);
    saved.classList.toggle('hidden', showStream);
    b1.classList.toggle('active', showStream);
    b2.classList.toggle('active', !showStream);

    if (!showStream) {
      // Подгрузить список сохранённых при переключении на вкладку
      const dateInput = document.getElementById('saved-screen-date');
      const value = dateInput && dateInput.value ? dateInput.value : undefined;
      loadSavedDetections(value);
    }
  }

  document.querySelectorAll('.screen-button').forEach(btn => {
    btn.addEventListener('click', () => selectScreen(btn.dataset.screen));
  });
  // По умолчанию открыт "Поток"
  selectScreen('stream');

  // Initialize saved detections
  const refreshSavedBtn = document.getElementById('saved-screen-refresh');
  if (refreshSavedBtn) {
    refreshSavedBtn.addEventListener('click', () => {
      const dateInput = document.getElementById('saved-screen-date');
      const value = dateInput && dateInput.value ? dateInput.value : undefined;
      loadSavedDetections(value);
    });
  }

  window.addEventListener('resize', resizeCanvasToImage);
  startStream();
  pollStatus();
})();


