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

  window.addEventListener('resize', resizeCanvasToImage);
  startStream();
  pollStatus();
})();


