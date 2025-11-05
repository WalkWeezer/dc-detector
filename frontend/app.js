(function () {
  const videoEl = document.getElementById("webcam");
  const serverStreamEl = document.getElementById("server-stream");
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
  
  // Режим работы: 'local' (локальная камера для разработки) или 'server' (серверный стрим для Raspberry Pi)
  let streamMode = 'local'; // По умолчанию локальная камера для разработки

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

  // ---- Автосохранение ----
  const autosaveEnabledKey = 'autosave_enabled';
  const autosaveThresholdKey = 'autosave_min_conf';
  let autoSaveEnabled = localStorage.getItem(autosaveEnabledKey) !== '0';
  let autoSaveMinConfidence = Number(localStorage.getItem(autosaveThresholdKey) ?? '0.8') || 0.8;
  const autoSavedTrackIds = new Set(); // чтобы не сохранять один id дважды

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
    // Используем реальные размеры видео или изображения, если они доступны
    let width, height;
    
    if (streamMode === 'server' && serverStreamEl) {
      // Для серверного стрима используем размеры изображения
      width = serverStreamEl.naturalWidth || serverStreamEl.width;
      height = serverStreamEl.naturalHeight || serverStreamEl.height;
    } else {
      // Для локальной камеры используем размеры видео
      width = videoEl.videoWidth;
      height = videoEl.videoHeight;
    }
    
    // Если размеры еще не загружены, используем размеры элемента
    if (!width || !height || width === 0 || height === 0) {
      const rect = (streamMode === 'server' && serverStreamEl) 
        ? serverStreamEl.getBoundingClientRect() 
        : videoEl.getBoundingClientRect();
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
    // В режиме сервера не нужно отправлять кадры локально
    if (streamMode === 'server') {
      return;
    }
    clearTimeout(uploadTimer);
    uploadTimer = window.setTimeout(captureAndUploadFrame, delay);
  }
  
  // Определение режима работы: проверка доступности серверного стрима
  async function detectStreamMode() {
    try {
      // Проверяем доступность серверного стрима
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 2000);
      
      const response = await fetch(`${backendOrigin}/api/detections/status`, {
        signal: controller.signal
      });
      clearTimeout(timeout);
      
      if (response.ok) {
        const status = await response.json();
        // Поддерживаем оба варианта кейсов: snake_case и camelCase
        const cameraEnabled = (status && (status.local_camera_enabled ?? status.localCameraEnabled));
        const activeCam = (status && (status.active_camera ?? status.activeCamera));
        if (cameraEnabled && activeCam !== null && activeCam !== undefined) {
          return 'server';
        }
      }
    } catch (error) {
      console.log('Серверный стрим недоступен, используем локальную камеру', error);
    }
    // По умолчанию используем локальную камеру для разработки
    return 'local';
  }
  
  // Запуск серверного стрима
  function startServerStream() {
    if (!serverStreamEl) {
      console.error('Элемент server-stream не найден');
      return;
    }
    
    // Скрываем video элемент, показываем img
    videoEl.style.display = 'none';
    serverStreamEl.style.display = 'block';
    
    // Устанавливаем источник MJPEG потока
    const streamUrl = `${backendOrigin}/api/detections/stream?t=${Date.now()}`;
    serverStreamEl.src = streamUrl;
    
    // Обработчик загрузки изображения для обновления размеров canvas
    serverStreamEl.onload = () => {
      resizeCanvases();
      updateStatus("Серверный стрим подключен");
    };
    
    // Обработчик ошибок
    serverStreamEl.onerror = () => {
      updateStatus("Ошибка серверного стрима", "error");
      errorMessageEl.textContent = "Не удалось подключиться к серверному видеопотоку";
      // Попробуем переподключиться через 2 секунды
      setTimeout(() => {
        if (streamMode === 'server') {
          startServerStream();
        }
      }, 2000);
    };
    
    updateStatus("Подключение к серверному стриму...");
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
      const autosaveEnabledInput = document.getElementById('config-autosave-enabled');
      const autosaveThresholdInput = document.getElementById('config-autosave-threshold');

      if (fpsInput) fpsInput.value = config.capture_fps || 2.5;
      if (iouInput) iouInput.value = config.iou_threshold || 0.3;
      if (maxAgeInput) maxAgeInput.value = config.max_age || 5;
      if (minHitsInput) minHitsInput.value = config.min_hits || 1;
      if (autosaveEnabledInput) autosaveEnabledInput.checked = !!autoSaveEnabled;
      if (autosaveThresholdInput) autosaveThresholdInput.value = autoSaveMinConfidence.toFixed(2);

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
    const autosaveEnabledInput = document.getElementById('config-autosave-enabled');
    const autosaveThresholdInput = document.getElementById('config-autosave-threshold');

    const updates = {
      capture_fps: fpsInput ? Number(fpsInput.value) : trackerConfig.capture_fps,
      iou_threshold: iouInput ? Number(iouInput.value) : trackerConfig.iou_threshold,
      max_age: maxAgeInput ? Number(maxAgeInput.value) : trackerConfig.max_age,
      min_hits: minHitsInput ? Number(minHitsInput.value) : trackerConfig.min_hits
    };

    try {
      // Сохраняем локальные настройки автосохранения в localStorage
      if (autosaveEnabledInput) {
        autoSaveEnabled = !!autosaveEnabledInput.checked;
        localStorage.setItem(autosaveEnabledKey, autoSaveEnabled ? '1' : '0');
      }
      if (autosaveThresholdInput) {
        const v = Number(autosaveThresholdInput.value);
        if (Number.isFinite(v) && v >= 0 && v <= 1) {
          autoSaveMinConfidence = v;
          localStorage.setItem(autosaveThresholdKey, String(v));
        }
      }
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
      // Если открыта вкладка сохранённых — обновить список
      const savedTabActive = document.getElementById('tab-saved')?.classList.contains('active');
      if (savedTabActive) {
        loadSavedDetections();
      }
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
    // В режиме сервера не нужно захватывать и отправлять кадры локально
    if (streamMode === 'server') {
      return;
    }
    
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

          // ---- Автосохранение по правилу: >= threshold и не более 1 раза на trackId
          const conf = Number(bestDetection?.confidence ?? 0) || 0;
          if (autoSaveEnabled && conf >= autoSaveMinConfidence && Number.isFinite(trackId) && !autoSavedTrackIds.has(trackId)) {
            try {
              await saveDetection(trackId);
              autoSavedTrackIds.add(trackId);
              // Небольшой индикатор в статусе
              updateStatus(`Автосохранено #${trackId}`, 'detected');
            } catch (e) {
              console.warn('Автосохранение не удалось', e);
            }
          }
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
    // Если режим сервера, запускаем серверный стрим
    if (streamMode === 'server') {
      startServerStream();
      return;
    }
    
    // Режим локальной камеры (для разработки)
    if (!navigator.mediaDevices?.getUserMedia) {
      updateStatus("Браузер не поддерживает getUserMedia", "error");
      errorMessageEl.textContent = "Используйте современный браузер (Chrome/Edge/Firefox).";
      return;
    }
    
    // Показываем video элемент, скрываем img
    if (serverStreamEl) {
      serverStreamEl.style.display = 'none';
    }
    videoEl.style.display = 'block';

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
    if (name === 'saved') {
      loadSavedDetections();
    }
  }
  document.querySelectorAll('.tab-button').forEach(btn => {
    btn.addEventListener('click', () => selectTab(btn.dataset.tab));
  });
  selectTab('status');

  // ------- Экранный переключатель (Поток/Сохранённые) -------
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
      // Подгрузить список сохранённых для полноэкранного режима
      const dateInput = document.getElementById('saved-screen-date');
      const value = dateInput && dateInput.value ? dateInput.value : undefined;
      loadSavedDetections(value, 'saved-screen-list');
    }
  }

  document.querySelectorAll('.screen-button').forEach(btn => {
    btn.addEventListener('click', () => selectScreen(btn.dataset.screen));
  });
  // По умолчанию открыт "Поток"
  selectScreen('stream');

  loadTrackerConfig().then(() => {
    const saveBtn = document.getElementById("save-config-btn");
    if (saveBtn) {
      saveBtn.addEventListener("click", saveTrackerConfig);
    }
  });
  statusUpdateInterval = setInterval(updateDetectionsStatus, 1000);
  loadModels();
  
  // Определяем режим работы и запускаем соответствующий стрим
  (async () => {
    streamMode = await detectStreamMode();
    console.log('Режим работы:', streamMode);
    startWebcam();
  })();

  // -------- Saved list logic ---------
  async function loadSavedDetections(dateValue, targetId = 'saved-list-container') {
    try {
      const params = new URLSearchParams();
      if (dateValue) params.set('date', dateValue);
      const response = await fetch(`${backendOrigin}/api/detections/saved?${params.toString()}`);
      const payload = await readResponsePayload(response);
      if (!response.ok) {
        throw new Error(readErrorMessage(payload, 'Не удалось загрузить сохранённые'));
      }
      const items = Array.isArray(payload.items) ? payload.items : [];
      renderSavedList(items, targetId);
    } catch (err) {
      console.error('Ошибка загрузки сохранённых', err);
      renderSavedList([], targetId);
    }
  }

  function renderSavedList(items, targetId = 'saved-list-container') {
    const container = document.getElementById(targetId);
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

  const refreshSavedBtn = document.getElementById('refresh-saved-btn');
  if (refreshSavedBtn) {
    refreshSavedBtn.addEventListener('click', () => {
      const dateInput = document.getElementById('saved-date');
      const value = dateInput && dateInput.value ? dateInput.value : undefined;
      loadSavedDetections(value);
    });
  }

  const refreshSavedScreenBtn = document.getElementById('saved-screen-refresh');
  if (refreshSavedScreenBtn) {
    refreshSavedScreenBtn.addEventListener('click', () => {
      const dateInput = document.getElementById('saved-screen-date');
      const value = dateInput && dateInput.value ? dateInput.value : undefined;
      loadSavedDetections(value, 'saved-screen-list');
    });
  }

  // -------- Modal for GIF preview ---------
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
    // detection fields
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
    const gifUrl = item.gifPath ? `${backendOrigin}${item.gifPath}` : '';
    const jsonUrl = item.jsonPath ? `${backendOrigin}${item.jsonPath}` : '';

    img.src = gifUrl;
    img.alt = item.id;

    // Load metadata JSON
    if (jsonUrl) {
      fetch(jsonUrl)
        .then(r => r.json())
        .then(data => setMetaList(list, data))
        .catch(() => {
          // Fallback to basic info if JSON not available
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
})();


