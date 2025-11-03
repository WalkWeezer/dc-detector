(function () {
  const videoEl = document.getElementById("webcam");
  const overlayEl = document.getElementById("overlay");
  const overlayCtx = overlayEl.getContext("2d");
  const statusIndicator = document.getElementById("status-indicator");
  const detectionCountEl = document.getElementById("detection-count");
  const detectionConfidenceEl = document.getElementById("detection-confidence");
  const lastUpdateEl = document.getElementById("last-update");
  const lastDetectionLabelEl = document.getElementById("last-detection-label");
  const captureIntervalEl = document.getElementById("capture-interval");
  const errorMessageEl = document.getElementById("error-message");
  const modelSelect = document.getElementById("model-select");
  const activeModelEl = document.getElementById("active-model");

  let uploadIntervalMs = 400;
  const captureCanvas = document.createElement("canvas");
  const captureCtx = captureCanvas.getContext("2d", { willReadFrequently: true });
  const backendOrigin = window.location.hostname === "localhost"
    ? "http://localhost:8080"
    : window.location.origin;

  let uploadTimer = null;
  let isUploading = false;
  let isSwitchingModel = false;
  let availableModels = [];
  let activeModel = null;
  let trackerConfig = {
    capture_fps: 2.5,
    iou_threshold: 0.3,
    max_age: 5,
    min_hits: 1,
    colors: {
      fire: "#ff0000",
      smoke: "#808080",
      object: "#40ffbc"
    }
  };
  let detectionNames = new Map();
  const detectionItemElements = new Map();
  let selectedTrackId = null;
  let statusUpdateInterval = null;
  let isEditingNames = false;
  let previousTrackIds = [];
  let lastDetections = [];
  // Кольцевой буфер последних кадров для сохранения
  const frameBuffer = [];
  const frameBufferMax = 15; // ~2-3 секунды при 5-7 FPS

  function updateStatus(text, state = "idle") {
    statusIndicator.textContent = text;
    statusIndicator.classList.remove("detected", "error");
    if (state === "detected") {
      statusIndicator.classList.add("detected");
    } else if (state === "error") {
      statusIndicator.classList.add("error");
    }
  }

  function resizeCanvases() {
    // Используем реальные размеры видео, если они доступны
    let width = videoEl.videoWidth;
    let height = videoEl.videoHeight;
    
    // Если размеры еще не загружены, используем размеры элемента
    if (!width || !height || width === 0 || height === 0) {
      const rect = videoEl.getBoundingClientRect();
      width = rect.width || 640;
      height = rect.height || 480;
    }
    
    // Минимальные размеры для canvas
    if (width < 1) width = 640;
    if (height < 1) height = 480;
    
    captureCanvas.width = width;
    captureCanvas.height = height;
    overlayEl.width = width;
    overlayEl.height = height;
    
    // Принудительно перерисовать overlay если нужно
    if (lastDetections && lastDetections.length > 0) {
      drawDetections(lastDetections);
    }
  }

  function scheduleNextUpload(delay = uploadIntervalMs) {
    clearTimeout(uploadTimer);
    uploadTimer = window.setTimeout(captureAndUploadFrame, delay);
  }

  function clearOverlay() {
    overlayCtx.clearRect(0, 0, overlayEl.width, overlayEl.height);
  }

  function readErrorMessage(payload, fallback = "Сервис детекции не ответил") {
    if (typeof payload === "string") {
      const trimmed = payload.trim();
      return trimmed ? trimmed.slice(0, 160) : fallback;
    }
    if (payload && typeof payload.error === "string" && payload.error) {
      return payload.error;
    }
    return fallback;
  }

  async function readResponsePayload(response) {
    const contentType = response.headers.get("content-type") ?? "";
    if (contentType.includes("application/json")) {
      return response.json();
    }
    return response.text();
  }

  function renderModelOptions(models = [], nextActive = activeModel) {
    if (!modelSelect) {
      return;
    }

    const normalized = Array.from(new Set((models ?? []).filter((name) => typeof name === "string" && name.length)));
    if (typeof nextActive === "string" && nextActive.length && !normalized.includes(nextActive)) {
      normalized.push(nextActive);
    }
    normalized.sort((a, b) => a.localeCompare(b));

    availableModels = normalized;
    modelSelect.innerHTML = "";

    if (!normalized.length) {
      const option = document.createElement("option");
      option.value = "";
      option.textContent = "Модели не найдены";
      option.disabled = true;
      option.selected = true;
      modelSelect.append(option);
      modelSelect.disabled = true;
      return;
    }

    normalized.forEach((name) => {
      const option = document.createElement("option");
      option.value = name;
      option.textContent = name;
      if (name === nextActive) {
        option.selected = true;
      }
      modelSelect.append(option);
    });

    modelSelect.disabled = isSwitchingModel;
    if (typeof nextActive === "string" && nextActive.length) {
      modelSelect.value = nextActive;
    } else {
      modelSelect.selectedIndex = 0;
    }
  }

  function updateActiveModel(name) {
    activeModel = typeof name === "string" && name.length ? name : null;
    if (activeModelEl) {
      activeModelEl.textContent = activeModel ?? "—";
    }
    if (modelSelect && activeModel && modelSelect.value !== activeModel) {
      modelSelect.value = activeModel;
    }
  }

  async function loadTrackerConfig() {
    try {
      const response = await fetch(`${backendOrigin}/api/config/tracker`);
      const config = await readResponsePayload(response);
      if (!response.ok) {
        throw new Error(readErrorMessage(config, "Не удалось загрузить конфигурацию"));
      }

      trackerConfig = config;
      uploadIntervalMs = 1000 / (config.capture_fps || 2.5);

      if (captureIntervalEl) {
        captureIntervalEl.textContent = `${Math.round(uploadIntervalMs)} мс (${config.capture_fps || 2.5} FPS)`;
      }

      const fpsInput = document.getElementById("config-fps");
      const iouInput = document.getElementById("config-iou");
      const maxAgeInput = document.getElementById("config-max-age");
      const minHitsInput = document.getElementById("config-min-hits");

      if (fpsInput) fpsInput.value = config.capture_fps || 2.5;
      if (iouInput) iouInput.value = config.iou_threshold || 0.3;
      if (maxAgeInput) maxAgeInput.value = config.max_age || 5;
      if (minHitsInput) minHitsInput.value = config.min_hits || 1;

      return config;
    } catch (error) {
      console.error("Не удалось загрузить конфигурацию трекера", error);
      errorMessageEl.textContent = error instanceof Error ? error.message : "Не удалось загрузить конфигурацию";
      return null;
    }
  }

  async function saveTrackerConfig() {
    const fpsInput = document.getElementById("config-fps");
    const iouInput = document.getElementById("config-iou");
    const maxAgeInput = document.getElementById("config-max-age");
    const minHitsInput = document.getElementById("config-min-hits");

    const updates = {
      capture_fps: fpsInput ? Number(fpsInput.value) : trackerConfig.capture_fps,
      iou_threshold: iouInput ? Number(iouInput.value) : trackerConfig.iou_threshold,
      max_age: maxAgeInput ? Number(maxAgeInput.value) : trackerConfig.max_age,
      min_hits: minHitsInput ? Number(minHitsInput.value) : trackerConfig.min_hits
    };

    try {
      const response = await fetch(`${backendOrigin}/api/config/tracker`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(updates)
      });

      const payload = await readResponsePayload(response);
      if (!response.ok) {
        throw new Error(readErrorMessage(payload, "Не удалось сохранить конфигурацию"));
      }

      trackerConfig = { ...trackerConfig, ...payload };
      uploadIntervalMs = 1000 / (trackerConfig.capture_fps || 2.5);

      if (captureIntervalEl) {
        captureIntervalEl.textContent = `${Math.round(uploadIntervalMs)} мс (${trackerConfig.capture_fps || 2.5} FPS)`;
      }

      errorMessageEl.textContent = "";
      alert("Конфигурация сохранена");
    } catch (error) {
      console.error("Ошибка сохранения конфигурации", error);
      errorMessageEl.textContent = error instanceof Error ? error.message : "Не удалось сохранить конфигурацию";
    }
  }

  function getColorForLabel(label) {
    const normalizedLabel = (label || "object").toLowerCase();
    return trackerConfig.colors[normalizedLabel] || trackerConfig.colors.object || "#40ffbc";
  }

  function ensureDetectionRow(trackId, labelName) {
    const container = document.getElementById('detections-list-container');
    let row = detectionItemElements.get(trackId);
    if (row) return row;

    const color = getColorForLabel(labelName);
    row = document.createElement('div');
    row.className = 'detection-item';
    row.dataset.trackId = String(trackId);
    row.style.borderLeftColor = color;

    const header = document.createElement('div');
    header.className = 'detection-item-header';
    const trackSpan = document.createElement('span');
    trackSpan.className = 'detection-item-track';
    const labelSpan = document.createElement('span');
    labelSpan.className = 'detection-item-label';
    header.append(trackSpan, labelSpan);

    const details = document.createElement('div');
    details.className = 'detection-item-details';
    const confSpan = document.createElement('span');
    const colorSpan = document.createElement('span');
    details.append(confSpan, colorSpan);

        const input = document.createElement('input');
    input.type = 'text';
    input.className = 'detection-item-name-input';
    input.placeholder = 'Имя объекта (не сохраняется)';
    input.dataset.trackId = String(trackId);

        // Кнопка сохранения
        const saveBtn = document.createElement('button');
        saveBtn.textContent = 'Сохранить';
        saveBtn.style.marginTop = '8px';
        saveBtn.addEventListener('click', async (e) => {
          e.stopPropagation();
          await saveDetection(trackId);
        });

        row.append(header, details, input, saveBtn);
    container.appendChild(row);

    row.addEventListener('click', (e) => {
      if (e.target.classList.contains('detection-item-name-input')) return;
      const id = parseInt(row.dataset.trackId);
      selectedTrackId = selectedTrackId === id ? null : id;
      document.querySelectorAll('#detections-list-container .detection-item').forEach(el => {
        el.classList.toggle('selected', el === row && selectedTrackId === id);
      });
      updateDetectionsDisplay();
    });

    input.addEventListener('focus', () => { isEditingNames = true; });
    input.addEventListener('blur', () => { isEditingNames = false; });
    input.addEventListener('change', (e) => {
      const id = parseInt(e.target.dataset.trackId);
      const name = e.target.value.trim();
      if (name) detectionNames.set(id, name); else detectionNames.delete(id);
      updateDetectionsDisplay();
    });
    input.addEventListener('click', (e) => e.stopPropagation());

    detectionItemElements.set(trackId, row);
    return row;
  }

  function syncDetectionsList(detections = []) {
    const container = document.getElementById('detections-list-container');
    if (!container) return;
    if (isEditingNames) return;

    const currentIds = new Set(detections.map(d => (Number.isFinite(d.trackId) ? d.trackId : d.id)).filter(Boolean));
    for (const [id, el] of detectionItemElements.entries()) {
      if (!currentIds.has(id)) {
        el.remove();
        detectionItemElements.delete(id);
      }
    }

    if (detections.length === 0) {
      if (!container.querySelector('.empty-msg')) {
        const p = document.createElement('p');
        p.className = 'empty-msg';
        p.style.color = '#93a4d2';
        p.style.textAlign = 'center';
        p.style.padding = '16px';
        p.textContent = 'Нет активных детекций';
        container.innerHTML = '';
        container.appendChild(p);
      }
      return;
    }
    const empty = container.querySelector('.empty-msg');
    if (empty) empty.remove();

    const sorted = detections.slice().sort((a, b) => {
      const A = Number.isFinite(a.trackId) ? a.trackId : 0;
      const B = Number.isFinite(b.trackId) ? b.trackId : 0;
      return A - B;
    });

    sorted.forEach(det => {
      const trackId = Number.isFinite(det.trackId) ? det.trackId : det.id;
      const labelName = typeof det.label === 'string' && det.label.length ? det.label : 'object';
      const row = ensureDetectionRow(trackId, labelName);

      row.classList.toggle('selected', selectedTrackId === trackId);
      row.style.borderLeftColor = getColorForLabel(labelName);
      const [header, details, input] = row.children;
      const [trackSpan, labelSpan] = header.children;
      const [confSpan, colorSpan] = details.children;
      trackSpan.textContent = `#${trackId}`;
      labelSpan.textContent = labelName;
      const confidence = Math.max(0, Math.min(100, Math.round((Number(det.confidence ?? 0) || 0) * 1000) / 10));
      confSpan.textContent = `Уверенность: ${confidence.toFixed(1)}%`;
      const col = getColorForLabel(labelName);
      colorSpan.innerHTML = `Цвет: <span style="color: ${col}">${col}</span>`;
      if (!isEditingNames && document.activeElement !== input) {
        input.value = detectionNames.get(trackId) || '';
      }
    });
  }

  async function updateDetectionsStatus() {
    try {
      const response = await fetch(`${backendOrigin}/api/detections/status`);
      const payload = await readResponsePayload(response);
      if (!response.ok) {
        return;
      }

      const detections = Array.isArray(payload.detections) ? payload.detections : [];
      const listDetections = Array.isArray(payload.stableDetections) ? payload.stableDetections : detections;
      const nextTrackIds = listDetections.map(d => (Number.isFinite(d.trackId) ? d.trackId : d.id)).filter(Boolean);

      if (JSON.stringify(nextTrackIds) !== JSON.stringify(previousTrackIds)) {
        lastDetections = listDetections;
        previousTrackIds = nextTrackIds;
        if (!isEditingNames) syncDetectionsList(listDetections);
      }

      if (detections.length > 0) {
        drawDetections(detections);
      }
    } catch (error) {
      console.error("Ошибка обновления статуса детекций", error);
    }
  }

  async function loadModels() {
    if (!modelSelect) {
      return;
    }
    try {
      modelSelect.disabled = true;
      const response = await fetch(`${backendOrigin}/api/detections/models`);
      const payload = await readResponsePayload(response);
      if (!response.ok) {
        throw new Error(readErrorMessage(payload, "Не удалось получить список моделей"));
      }

      const models = Array.isArray(payload.models) ? payload.models : [];
      const nextActive = typeof payload.active === "string" ? payload.active : null;
      renderModelOptions(models, nextActive ?? activeModel);
      updateActiveModel(nextActive ?? activeModel);
    } catch (error) {
      console.error("Не удалось загрузить список моделей", error);
      errorMessageEl.textContent = error instanceof Error ? error.message : "Не удалось получить список моделей";
      renderModelOptions([], activeModel);
    } finally {
      if (modelSelect && availableModels.length && !isSwitchingModel) {
        modelSelect.disabled = false;
      }
    }
  }

  async function switchModel(modelName) {
    if (!modelSelect || !modelName || modelName === activeModel || isSwitchingModel) {
      if (modelSelect && activeModel) {
        modelSelect.value = activeModel;
      }
      return;
    }

    isSwitchingModel = true;
    modelSelect.disabled = true;
    try {
      const response = await fetch(`${backendOrigin}/api/detections/models`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: modelName })
      });
      const payload = await readResponsePayload(response);
      if (!response.ok) {
        throw new Error(readErrorMessage(payload, "Не удалось переключить модель"));
      }

      const models = Array.isArray(payload.models) ? payload.models : availableModels;
      const nextActive = typeof payload.active === "string" ? payload.active : modelName;
      renderModelOptions(models, nextActive);
      updateActiveModel(nextActive);
      errorMessageEl.textContent = "";
    } catch (error) {
      console.error("Ошибка переключения модели", error);
      errorMessageEl.textContent = error instanceof Error ? error.message : "Не удалось переключить модель";
    } finally {
      isSwitchingModel = false;
      if (modelSelect) {
        modelSelect.disabled = availableModels.length === 0;
        if (activeModel) {
          modelSelect.value = activeModel;
        }
      }
    }
  }

  if (modelSelect) {
    modelSelect.addEventListener("change", (event) => {
      const value = event.target.value;
      if (!value) {
        return;
      }
      switchModel(value);
    });
  }

  function hexToRgba(hex, alpha = 1) {
    const r = parseInt(hex.slice(1, 3), 16);
    const g = parseInt(hex.slice(3, 5), 16);
    const b = parseInt(hex.slice(5, 7), 16);
    return `rgba(${r}, ${g}, ${b}, ${alpha})`;
  }

  async function saveDetection(trackId) {
    try {
      // Найти детекцию с таким trackId из последнего списка
      const det = (lastDetections || []).find(d => (Number.isFinite(d.trackId) ? d.trackId : d.id) === trackId);
      if (!det) {
        alert('Детекция не найдена для сохранения');
        return;
      }
      const detectionPayload = {
        trackId: Number.isFinite(det.trackId) ? det.trackId : det.id,
        bbox: Array.isArray(det.bbox) ? det.bbox.slice(0, 4).map(Number) : null,
        label: typeof det.label === 'string' ? det.label : 'object',
        classId: Number.isFinite(det.classId) ? det.classId : null,
        confidence: Number(det.confidence ?? 0) || 0,
        cameraIndex: null,
        model: activeModel,
        capturedAt: Math.floor(Date.now() / 1000)
      };
      const payload = {
        detection: detectionPayload,
        frames: frameBuffer.slice(-frameBufferMax),
        fps: Math.max(1, Math.round(1000 / uploadIntervalMs))
      };

      const response = await fetch(`${backendOrigin}/api/detections/save`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const result = await readResponsePayload(response);
      if (!response.ok) {
        throw new Error(readErrorMessage(result, 'Не удалось сохранить детекцию'));
      }
      alert('Сохранено: ' + (result.gifPath || 'OK'));
    } catch (err) {
      console.error('Ошибка сохранения детекции', err);
      alert('Ошибка сохранения: ' + (err instanceof Error ? err.message : 'Unknown'));
    }
  }

  function drawDetections(detections = []) {
    clearOverlay();
    if (!detections.length) {
      return;
    }

    overlayCtx.font = "16px 'Segoe UI', sans-serif";
    overlayCtx.fillStyle = "rgba(10, 17, 31, 0.8)";
    overlayCtx.textBaseline = "top";

    detections.forEach((det) => {
      if (!Array.isArray(det.bbox)) {
        return;
      }
      const [x1, y1, x2, y2] = det.bbox.map(Number);
      const width = x2 - x1;
      const height = y2 - y1;

      const labelName = typeof det.label === "string" && det.label.length ? det.label : "object";
      const trackId = typeof det.trackId === "number" && Number.isFinite(det.trackId)
        ? det.trackId
        : (det.id ?? "?");
      
      const isSelected = selectedTrackId === trackId;
      const color = getColorForLabel(labelName);
      const strokeColor = hexToRgba(color, 0.9);
      const lineWidth = isSelected ? 5 : 3;

      overlayCtx.strokeStyle = strokeColor;
      overlayCtx.lineWidth = lineWidth;
      overlayCtx.strokeRect(x1, y1, width, height);

      const customName = detectionNames.get(trackId);
      const displayName = customName || labelName;
      const confidencePercent = Math.max(0, Math.min(100, Math.round((Number(det.confidence ?? 0) || 0) * 1000) / 10));
      const label = `${displayName} #${trackId} ${confidencePercent.toFixed(1)}%`;
      const textWidth = overlayCtx.measureText(label).width + 12;
      const textHeight = 24;
      const textX = Math.max(0, Math.min(x1, overlayEl.width - textWidth));
      const textY = Math.max(0, y1 - textHeight - 4);

      overlayCtx.fillRect(textX, textY, textWidth, textHeight);
      overlayCtx.fillStyle = strokeColor;
      overlayCtx.fillText(label, textX + 6, textY + 4);
      overlayCtx.fillStyle = "rgba(10, 17, 31, 0.8)";
    });
  }

  async function captureAndUploadFrame() {
    if (isUploading || isSwitchingModel) {
      scheduleNextUpload(100);
      return;
    }

    if (videoEl.readyState < HTMLMediaElement.HAVE_CURRENT_DATA) {
      scheduleNextUpload(200);
      return;
    }

    // Проверяем, что видео имеет размеры
    if (!videoEl.videoWidth || !videoEl.videoHeight || videoEl.videoWidth === 0 || videoEl.videoHeight === 0) {
      console.warn("Видео не имеет размеров, ждем...", {
        videoWidth: videoEl.videoWidth,
        videoHeight: videoEl.videoHeight,
        readyState: videoEl.readyState
      });
      resizeCanvases(); // Попробуем переинициализировать
      scheduleNextUpload(500);
      return;
    }

    isUploading = true;
    errorMessageEl.textContent = "";

    try {
      captureCtx.drawImage(videoEl, 0, 0, captureCanvas.width, captureCanvas.height);
      const dataUrl = captureCanvas.toDataURL("image/jpeg", 0.85);
      // Буферизация последних кадров для сохранения гифок
      frameBuffer.push(dataUrl);
      if (frameBuffer.length > frameBufferMax) {
        frameBuffer.splice(0, frameBuffer.length - frameBufferMax);
      }
      const base64Data = dataUrl.split(",")[1];

      const response = await fetch(`${backendOrigin}/api/detections/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ image: base64Data })
      });

      const payload = await readResponsePayload(response);

      if (!response.ok) {
        throw new Error(readErrorMessage(payload));
      }

      const result = typeof payload === "string" ? {} : payload;

      const detected = Boolean(result.detected);
      const detections = Array.isArray(result.detections) ? result.detections : [];
      const confidence = Number(result.confidence ?? 0);

      updateStatus(detected ? "Обнаружены объекты" : "Объекты не обнаружены", detected ? "detected" : "idle");
      detectionCountEl.textContent = detections.length.toString();
      detectionConfidenceEl.textContent = confidence > 0 ? confidence.toFixed(3) : "0.000";
      lastUpdateEl.textContent = new Date().toLocaleTimeString();

      if (lastDetectionLabelEl) {
        if (detections.length) {
          const bestDetection = detections.reduce((best, current) => (
            Number(current?.confidence ?? 0) > Number(best?.confidence ?? 0) ? current : best
          ), detections[0]);
          const labelName = typeof bestDetection.label === "string" && bestDetection.label.length
            ? bestDetection.label
            : "object";
          const trackId = typeof bestDetection.trackId === "number" && Number.isFinite(bestDetection.trackId)
            ? bestDetection.trackId
            : (bestDetection.id ?? "?");
          lastDetectionLabelEl.textContent = `${labelName} #${trackId}`;
        } else {
          lastDetectionLabelEl.textContent = "—";
        }
      }

      if (typeof result.model === "string" && result.model.length) {
        if (!availableModels.includes(result.model)) {
          renderModelOptions([...availableModels, result.model], result.model);
        }
        updateActiveModel(result.model);
      }

      drawDetections(detections);

      // Список обновляется через status-пул
    } catch (error) {
      console.error("Ошибка при отправке кадра", error);
      updateStatus("Ошибка обмена", "error");
      errorMessageEl.textContent = error instanceof Error ? error.message : "Неизвестная ошибка";
      if (lastDetectionLabelEl) {
        lastDetectionLabelEl.textContent = "—";
      }
      clearOverlay();
    } finally {
      isUploading = false;
      scheduleNextUpload(uploadIntervalMs);
    }
  }

  async function startWebcam() {
    if (!navigator.mediaDevices?.getUserMedia) {
      updateStatus("Браузер не поддерживает getUserMedia", "error");
      errorMessageEl.textContent = "Используйте современный браузер (Chrome/Edge/Firefox).";
      return;
    }

    const tryConstraints = async (constraints) => {
      try {
        return await navigator.mediaDevices.getUserMedia(constraints);
      } catch (e) {
        return null;
      }
    };

    // Пошаговые попытки: environment -> user -> авто
    const attempts = [
      { video: { width: { ideal: 1280 }, height: { ideal: 720 }, facingMode: { ideal: "environment" } }, audio: false },
      { video: { width: { ideal: 1280 }, height: { ideal: 720 }, facingMode: { ideal: "user" } }, audio: false },
      { video: true, audio: false }
    ];

    let stream = null;
    for (const c of attempts) {
      // eslint-disable-next-line no-await-in-loop
      stream = await tryConstraints(c);
      if (stream) break;
    }

    if (!stream) {
      updateStatus("Нет доступа к камере", "error");
      errorMessageEl.textContent = "Камера недоступна или отклонено разрешение. Проверьте настройки браузера/ОС.";
      return;
    }

    try {
      // Очистить предыдущий поток если был
      if (videoEl.srcObject) {
        const oldStream = videoEl.srcObject;
        oldStream.getTracks().forEach(track => track.stop());
      }

      videoEl.srcObject = stream;
      
      // Ждем загрузки метаданных перед воспроизведением
      const metadataLoaded = new Promise((resolve) => {
        if (videoEl.readyState >= HTMLMediaElement.HAVE_METADATA) {
          resolve();
          return;
        }
        const handler = () => {
          videoEl.removeEventListener("loadedmetadata", handler);
          resolve();
        };
        videoEl.addEventListener("loadedmetadata", handler);
      });

      await metadataLoaded;

      // Ждем начала воспроизведения
      const playingPromise = new Promise((resolve, reject) => {
        const onPlaying = () => {
          videoEl.removeEventListener("playing", onPlaying);
          videoEl.removeEventListener("error", onError);
          resolve();
        };
        const onError = (err) => {
          videoEl.removeEventListener("playing", onPlaying);
          videoEl.removeEventListener("error", onError);
          reject(err);
        };
        videoEl.addEventListener("playing", onPlaying, { once: true });
        videoEl.addEventListener("error", onError, { once: true });
        
        // Если уже играет, сразу резолвим
        if (!videoEl.paused && videoEl.readyState >= HTMLMediaElement.HAVE_CURRENT_DATA) {
          videoEl.removeEventListener("playing", onPlaying);
          videoEl.removeEventListener("error", onError);
          resolve();
        }
      });

      // Явно запускаем воспроизведение
      try {
        await videoEl.play();
        await Promise.race([
          playingPromise,
          new Promise(resolve => setTimeout(resolve, 2000)) // Таймаут 2 секунды
        ]);
      } catch (playError) {
        console.warn("Не удалось автоматически запустить видео", playError);
        // Если автоплей не работает, показываем подсказку
        if (playError.name === 'NotAllowedError') {
          errorMessageEl.textContent = "Кликните на страницу для запуска видео";
          document.body.style.cursor = 'pointer';
          const clickHandler = async () => {
            document.body.style.cursor = '';
            document.body.removeEventListener('click', clickHandler);
            try {
              await videoEl.play();
              errorMessageEl.textContent = "";
            } catch (e) {
              console.error("Ошибка при ручном запуске видео", e);
            }
          };
          document.body.addEventListener('click', clickHandler, { once: true });
        }
      }

      // Инициализируем canvas после получения метаданных
      resizeCanvases();

      // Добавляем обработчик для события canplay, чтобы убедиться что видео готово
      const onCanPlay = () => {
        console.log("Видео готово к воспроизведению", {
          videoWidth: videoEl.videoWidth,
          videoHeight: videoEl.videoHeight,
          readyState: videoEl.readyState,
          paused: videoEl.paused
        });
        resizeCanvases();
        if (!isUploading && videoEl.videoWidth > 0 && videoEl.videoHeight > 0) {
          scheduleNextUpload(200);
        }
      };
      videoEl.addEventListener("canplay", onCanPlay, { once: true });

      // Также обработчик для loadeddata
      const onLoadedData = () => {
        console.log("Видео данные загружены", {
          videoWidth: videoEl.videoWidth,
          videoHeight: videoEl.videoHeight
        });
        resizeCanvases();
      };
      videoEl.addEventListener("loadeddata", onLoadedData);

      updateStatus("Камера подключена");

      // Обработчик для повторной инициализации если размеры изменились
      const onMetadataLoaded = () => {
        console.log("Метаданные загружены", {
          videoWidth: videoEl.videoWidth,
          videoHeight: videoEl.videoHeight
        });
        resizeCanvases();
        if (!isUploading) {
          scheduleNextUpload(200);
        }
      };

      videoEl.addEventListener("loadedmetadata", onMetadataLoaded);

      // Обработчик для изменения размеров
      const onResize = () => {
        if (videoEl.videoWidth && videoEl.videoHeight) {
          resizeCanvases();
        }
      };
      window.addEventListener("resize", onResize);

      // Также пробуем запустить отправку кадров сразу
      if (videoEl.readyState >= HTMLMediaElement.HAVE_CURRENT_DATA && videoEl.videoWidth > 0 && videoEl.videoHeight > 0) {
        console.log("Запуск отправки кадров, видео готово", {
          videoWidth: videoEl.videoWidth,
          videoHeight: videoEl.videoHeight
        });
        scheduleNextUpload(200);
      } else {
        console.log("Видео еще не готово, ждем событий", {
          readyState: videoEl.readyState,
          videoWidth: videoEl.videoWidth,
          videoHeight: videoEl.videoHeight
        });
      }

      // Добавляем обработчик ошибок для видео элемента
      const onVideoError = (e) => {
        console.error("Ошибка видео элемента", e);
        updateStatus("Ошибка видео", "error");
        errorMessageEl.textContent = "Ошибка при воспроизведении видео потока";
      };
      videoEl.addEventListener("error", onVideoError);
    } catch (error) {
      console.error("Ошибка инициализации видео", error);
      updateStatus("Ошибка видео", "error");
      errorMessageEl.textContent = error instanceof Error ? error.message : "Не удалось запустить видео";
      
      // Остановить поток в случае ошибки
      if (stream) {
        stream.getTracks().forEach(track => track.stop());
      }
    }
  }

  document.addEventListener("visibilitychange", () => {
    if (document.hidden) {
      clearTimeout(uploadTimer);
      uploadTimer = null;
      if (statusUpdateInterval) {
        clearInterval(statusUpdateInterval);
        statusUpdateInterval = null;
      }
    } else {
      if (!isUploading) {
        scheduleNextUpload(200);
      }
      if (!statusUpdateInterval) {
        statusUpdateInterval = setInterval(updateDetectionsStatus, 1000);
      }
    }
  });

  function selectTab(name) {
    document.querySelectorAll('.tab-button').forEach(btn => {
      btn.classList.toggle('active', btn.dataset.tab === name);
    });
    document.querySelectorAll('.tab-panel').forEach(panel => {
      panel.classList.toggle('active', panel.id === `tab-${name}`);
    });
  }
  document.querySelectorAll('.tab-button').forEach(btn => {
    btn.addEventListener('click', () => selectTab(btn.dataset.tab));
  });
  selectTab('status');

  loadTrackerConfig().then(() => {
    const saveBtn = document.getElementById("save-config-btn");
    if (saveBtn) {
      saveBtn.addEventListener("click", saveTrackerConfig);
    }
  });
  statusUpdateInterval = setInterval(updateDetectionsStatus, 1000);
  loadModels();
  startWebcam();
})();


