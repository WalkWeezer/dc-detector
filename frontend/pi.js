(() => {
  const els = {
    img: document.getElementById('server-stream'),
    overlay: document.getElementById('overlay'),
    statusIndicator: document.getElementById('status-indicator'),
    cameraType: document.getElementById('camera-type'),
    activeModel: document.getElementById('active-model'),
    detectionCount: document.getElementById('detection-count'),
    detectionConfidence: document.getElementById('detection-confidence'),
    mavlinkStatus: document.getElementById('mavlink-status'),
    gpsStatus: document.getElementById('gps-status'),
    errorMessage: document.getElementById('error-message'),
    modelForm: document.getElementById('model-form'),
    modelSelect: document.getElementById('model-select'),
    modelApplyBtn: document.getElementById('model-apply-btn'),
    trackerList: document.getElementById('tracker-list'),
    trackerRefresh: document.getElementById('tracker-refresh'),
    targetSelect: document.getElementById('target-select'),
    applyTargetBtn: document.getElementById('apply-target-btn'),
    saveDetectionBtn: document.getElementById('save-detection-btn'),
    savedDate: document.getElementById('saved-screen-date'),
    savedRefresh: document.getElementById('saved-screen-refresh'),
    savedClear: document.getElementById('saved-screen-clear'),
    savedList: document.getElementById('saved-screen-list'),
    tabButtons: document.querySelectorAll('.tab-button'),
    tabPanels: document.querySelectorAll('.tab-panel'),
    // Автосохранение
    autosaveEnabled: document.getElementById('autosave-enabled'),
    autosaveMinConfidence: document.getElementById('autosave-min-confidence'),
    autosaveMinHits: document.getElementById('autosave-min-hits'),
    autosaveDelay: document.getElementById('autosave-delay'),
    autosaveSaveBtn: document.getElementById('autosave-save-btn'),
    autosaveSettingsGroup: document.getElementById('autosave-settings-group'),
    // Производительность
    performanceInferFps: document.getElementById('performance-infer-fps'),
    performanceConfidence: document.getElementById('performance-confidence'),
    performanceJpegStream: document.getElementById('performance-jpeg-stream'),
    performanceQueueSize: document.getElementById('performance-queue-size'),
    performanceInputSize: document.getElementById('performance-input-size'),
    performanceDrawDetections: document.getElementById('performance-draw-detections'),
    performanceApplyBtn: document.getElementById('performance-apply-btn'),
    performanceInferFpsValue: document.getElementById('performance-infer-fps-value'),
    performanceConfidenceValue: document.getElementById('performance-confidence-value'),
    performanceJpegStreamValue: document.getElementById('performance-jpeg-stream-value'),
    performanceQueueSizeValue: document.getElementById('performance-queue-size-value'),
    performanceInputSizeValue: document.getElementById('performance-input-size-value'),
    metricInferFps: document.getElementById('metric-infer-fps'),
    metricQueueSize: document.getElementById('metric-queue-size'),
    metricFrameTime: document.getElementById('metric-frame-time'),
    // Сервоприводы
    servoPan: document.getElementById('servo-pan'),
    servoPanValue: document.getElementById('servo-pan-value'),
    servoTilt: document.getElementById('servo-tilt'),
    servoTiltValue: document.getElementById('servo-tilt-value'),
    servoResetBtn: document.getElementById('servo-reset-btn'),
    servoStatus: document.getElementById('servo-status'),
    servoError: document.getElementById('servo-error'),
  };

  const state = {
    trackers: [],
    selectedTrackId: null,
    models: {
      active: null,
      available: [],
    },
  };

  const overlayCtx = els.overlay.getContext('2d');

  const computeOrigin = (port) => {
    const { protocol, hostname } = window.location;
    const isLocal = hostname === 'localhost' || hostname === '127.0.0.1';
    const baseHost = isLocal ? 'localhost' : hostname;
    return `${protocol}//${baseHost}:${port}`;
  };

  const backendOrigin = computeOrigin(8080);
  const detectionServiceOrigin = computeOrigin(8001); // Прямой доступ к detection service

  // Все запросы идут через бэкенд, кроме видео потока (прямой доступ к detection service)
  const api = {
    detection: `${backendOrigin}/api/detection`,
    trackers: `${backendOrigin}/api/trackers`,
    trackerName: `${backendOrigin}/api/trackers/name`, // Имена хранятся в backend
    trackerTarget: `${backendOrigin}/api/trackers/target`,
    detectionsSave: `${backendOrigin}/api/detections/save`, // Сохранение через backend
    detectionsSaved: `${backendOrigin}/api/detections/saved`,
    models: `${backendOrigin}/api/models`,
    stream: `${detectionServiceOrigin}/video_feed_raw`, // Прямой доступ к detection service
    autosaveConfig: `${backendOrigin}/api/config/autosave`, // Конфигурация автосохранения
    performanceConfig: `${detectionServiceOrigin}/api/config/performance`, // Настройки производительности
    servo: `${detectionServiceOrigin}/api/servo`, // Управление сервоприводами
    servoStatus: `${detectionServiceOrigin}/api/servo/status`, // Детальный статус сервоприводов
    gps: `${detectionServiceOrigin}/api/gps`, // GPS координаты
  };

  function updateStatus(text, variant) {
    els.statusIndicator.textContent = text;
    els.statusIndicator.classList.remove('detected', 'error');
    if (variant) els.statusIndicator.classList.add(variant);
  }

  function resizeCanvas() {
    if (!els.img || !els.overlay) return;
    const width = els.img.naturalWidth || els.img.clientWidth || 640;
    const height = els.img.naturalHeight || els.img.clientHeight || 480;
    if (width > 0 && height > 0) {
      els.overlay.width = width;
      els.overlay.height = height;
      drawTrackers();
    }
  }

  function drawTrackers() {
    overlayCtx.clearRect(0, 0, els.overlay.width, els.overlay.height);
    if (!state.trackers.length) return;

    overlayCtx.lineWidth = 3;
    overlayCtx.font = "16px 'Segoe UI', sans-serif";
    overlayCtx.textBaseline = 'top';

    state.trackers.forEach((tracker) => {
      if (!Array.isArray(tracker.bbox) || tracker.bbox.length < 4) return;
      const [x1, y1, x2, y2] = tracker.bbox.map(Number);
      const width = x2 - x1;
      const height = y2 - y1;
      
      // Выделяем выбранный трекер более ярким цветом и толстой линией
      const isSelected = tracker.trackId === state.selectedTrackId;
      overlayCtx.strokeStyle = isSelected
        ? 'rgba(126,229,255,0.95)'
        : 'rgba(64,255,188,0.85)';
      overlayCtx.lineWidth = isSelected ? 4 : 2;
      overlayCtx.strokeRect(x1, y1, width, height);

      // Подпись с именем и уверенностью
      const labelName = tracker.name || tracker.label || 'object';
      const confidence = (Number(tracker.confidence || tracker.lastConfidence || 0) * 100).toFixed(1);
      const label = `${labelName} #${tracker.trackId} ${confidence}%`;
      const metrics = overlayCtx.measureText(label);
      const textWidth = metrics.width + 12;
      const textHeight = 24;
      const tx = Math.max(0, Math.min(x1, els.overlay.width - textWidth));
      const ty = Math.max(0, y1 - textHeight - 4);

      // Фон для текста
      overlayCtx.fillStyle = 'rgba(10,17,31,0.85)';
      overlayCtx.fillRect(tx, ty, textWidth, textHeight);
      
      // Текст
      overlayCtx.fillStyle = isSelected ? '#7ee5ff' : '#40ffbc';
      overlayCtx.fillText(label, tx + 6, ty + 4);
    });
  }

  async function fetchJSON(url, options = {}) {
    const response = await fetch(url, options);
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.error || response.statusText);
    return data;
  }

  async function refreshModels() {
    try {
      const data = await fetchJSON(api.models);
      // Поддержка разных форматов ответа
      state.models.active = data.active_model || data.activeModel || data.active || null;
      state.models.available = Array.isArray(data.available_models)
        ? data.available_models
        : (Array.isArray(data.availableModels) ? data.availableModels : (Array.isArray(data.available) ? data.available : []));
      renderModelSelect();
    } catch (err) {
      console.error('Не удалось загрузить модели', err);
      updateStatus('Ошибка загрузки моделей', 'error');
    }
  }

  function renderModelSelect() {
    const { available, active } = state.models;
    els.modelSelect.innerHTML = '';
    if (!available.length) {
      const opt = document.createElement('option');
      opt.value = '';
      opt.textContent = 'Нет моделей';
      els.modelSelect.appendChild(opt);
      els.modelSelect.disabled = true;
      els.modelApplyBtn.disabled = true;
      return;
    }
    available.forEach((name) => {
      const opt = document.createElement('option');
      opt.value = name;
      opt.textContent = name;
      if (name === active) opt.selected = true;
      els.modelSelect.appendChild(opt);
    });
    els.modelSelect.disabled = false;
    els.modelApplyBtn.disabled = false;
    els.activeModel.textContent = active || '—';
  }

  async function refreshStatus() {
    try {
      const data = await fetchJSON(api.detection);
      els.cameraType.textContent = data.camera_type || data.cameraType || '—';
      // Поддержка разных форматов ответа от detection service
      const trackersCount = data.active_trackers_count ?? data.activeTrackersCount ?? data.trackers_count ?? data.trackersCount ?? 0;
      els.detectionCount.textContent = String(trackersCount);
      els.detectionConfidence.textContent = data.max_confidence
        ? `${(Number(data.max_confidence) * 100).toFixed(1)}%`
        : '—';
      els.errorMessage.textContent = '';
      updateStatus('Онлайн', 'detected');
      
      // Обновляем статус сервоприводов
      if (data.servo) {
        updateServoStatus(data.servo);
      }
      
      // Обновляем детальный статус сервоприводов
      refreshServoStatus();
      
      // Обновляем метрики производительности если вкладка открыта
      const performancePanel = document.getElementById('panel-tab-performance');
      if (performancePanel && performancePanel.classList.contains('active')) {
        try {
          const perfConfig = await fetchJSON(api.performanceConfig);
          if (els.metricInferFps) {
            els.metricInferFps.textContent = `${perfConfig.infer_fps || '—'} FPS`;
          }
          if (els.metricQueueSize) {
            // Показываем реальный размер очереди, а не максимальный
            els.metricQueueSize.textContent = `${perfConfig.queue_size ?? 0} / ${perfConfig.max_infer_queue_size || '—'}`;
          }
          if (els.metricFrameTime) {
            const frameTime = perfConfig.frame_process_time_ms;
            if (frameTime !== null && frameTime !== undefined) {
              els.metricFrameTime.textContent = `${frameTime.toFixed(1)} мс`;
            } else {
              els.metricFrameTime.textContent = '—';
            }
          }
        } catch (err) {
          // Игнорируем ошибки метрик
          console.debug('Ошибка загрузки метрик производительности:', err);
        }
      }
    } catch (err) {
      updateStatus('Нет связи', 'error');
      els.errorMessage.textContent = err.message;
    } finally {
      setTimeout(refreshStatus, 2000);
    }
  }

  async function refreshMavLinkAndGPS() {
    try {
      const gpsData = await fetchJSON(api.gps);
      
      // Обновляем статус MavLink
      if (gpsData.available) {
        els.mavlinkStatus.textContent = 'Подключен';
        els.mavlinkStatus.style.color = '#40ffbc';
        
        // Обновляем GPS координаты
        if (gpsData.latitude != null && gpsData.longitude != null) {
          const lat = Number(gpsData.latitude).toFixed(6);
          const lon = Number(gpsData.longitude).toFixed(6);
          const alt = gpsData.altitude != null ? `, ${Number(gpsData.altitude).toFixed(1)}м` : '';
          const fixType = gpsData.fix_type || 0;
          const fixText = fixType >= 3 ? '3D' : fixType >= 2 ? '2D' : 'нет фикса';
          els.gpsStatus.textContent = `${lat}, ${lon}${alt} (${fixText})`;
          els.gpsStatus.style.color = fixType >= 2 ? '#40ffbc' : '#ff6b6b';
        } else {
          els.gpsStatus.textContent = 'Нет координат';
          els.gpsStatus.style.color = '#ff6b6b';
        }
      } else {
        els.mavlinkStatus.textContent = 'Не подключен';
        els.mavlinkStatus.style.color = '#ff6b6b';
        els.gpsStatus.textContent = gpsData.error || 'GPS не настроен';
        els.gpsStatus.style.color = '#ffa500';
      }
    } catch (err) {
      els.mavlinkStatus.textContent = 'Ошибка';
      els.mavlinkStatus.style.color = '#ff6b6b';
      els.gpsStatus.textContent = 'Недоступен';
      els.gpsStatus.style.color = '#ff6b6b';
    }
  }

  async function updateServoStatus(servoState) {
    if (!servoState) return;
    
    if (els.servoStatus) {
      let statusText = '—';
      let statusColor = '#999';
      
      if (servoState.hardware_enabled) {
        statusText = 'Аппаратный';
        statusColor = '#40ffbc';
      } else if (servoState.configured) {
        statusText = 'Ошибка инициализации';
        statusColor = '#ff6b6b';
      } else {
        statusText = 'Программный';
        statusColor = '#ffa500';
      }
      
      els.servoStatus.textContent = statusText;
      els.servoStatus.style.color = statusColor;
      els.servoStatus.title = servoState.error || statusText;
    }
    
    // Показываем ошибку если есть
    if (els.servoError) {
      if (servoState.error) {
        els.servoError.textContent = `⚠️ ${servoState.error}`;
        els.servoError.style.display = 'block';
      } else {
        els.servoError.style.display = 'none';
      }
    }
    
    // Обновляем ползунки только если они не в фокусе (чтобы не мешать пользователю)
    if (els.servoPan && document.activeElement !== els.servoPan) {
      els.servoPan.value = Math.round(servoState.pan || 90);
      if (els.servoPanValue) {
        els.servoPanValue.textContent = `${Math.round(servoState.pan || 90)}°`;
      }
    }
    
    if (els.servoTilt && document.activeElement !== els.servoTilt) {
      els.servoTilt.value = Math.round(servoState.tilt || 90);
      if (els.servoTiltValue) {
        els.servoTiltValue.textContent = `${Math.round(servoState.tilt || 90)}°`;
      }
    }
  }
  
  async function refreshServoStatus() {
    try {
      const status = await fetchJSON(api.servoStatus);
      updateServoStatus(status);
    } catch (err) {
      console.debug('Ошибка получения статуса сервоприводов:', err);
    }
  }

  async function setServoAngles(pan, tilt) {
    try {
      const payload = {};
      if (pan != null) payload.pan = Number(pan);
      if (tilt != null) payload.tilt = Number(tilt);
      
      const result = await fetchJSON(api.servo, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      
      updateServoStatus(result);
    } catch (err) {
      console.error('Ошибка установки углов сервоприводов:', err);
      if (els.errorMessage) {
        els.errorMessage.textContent = `Ошибка сервоприводов: ${err.message}`;
      }
    }
  }

  async function refreshTrackers(manual = false) {
    try {
      const data = await fetchJSON(api.trackers);
      state.trackers = Array.isArray(data.trackers) ? data.trackers : [];
      // Получаем target из detection service
      const targetFromService = data.target_track_id ?? data.targetTrackId ?? null;
      if (Number.isFinite(targetFromService)) {
        state.selectedTrackId = Number(targetFromService);
      } else if (!state.selectedTrackId && state.trackers.length) {
        // Если нет target, выбираем первый трекер
        state.selectedTrackId = state.trackers[0].trackId;
      }
      renderTrackers();
      drawTrackers();
      if (manual) {
        els.errorMessage.textContent = 'Список трекеров обновлён';
      }
    } catch (err) {
      console.error('Ошибка загрузки трекеров', err);
      if (manual) {
        els.errorMessage.textContent = err.message;
      }
      state.trackers = [];
      renderTrackers();
      drawTrackers();
    } finally {
      setTimeout(refreshTrackers, 1500);
    }
  }

  function renderTrackers() {
    const container = els.trackerList;
    
    // Сохраняем информацию о фокусировке перед обновлением
    const activeElement = document.activeElement;
    let focusedTrackerId = null;
    if (activeElement && activeElement.classList.contains('name-input')) {
      const card = activeElement.closest('.tracker-card');
      if (card) {
        const trackId = card.dataset.trackId || card.getAttribute('data-track-id');
        focusedTrackerId = trackId ? Number(trackId) : null;
      }
    }
    const focusedInputValue = activeElement && activeElement.classList.contains('name-input')
      ? activeElement.value
      : null;
    const cursorPosition = activeElement && activeElement.classList.contains('name-input')
      ? activeElement.selectionStart
      : null;
    
    if (!state.trackers.length) {
      container.innerHTML = '';
      container.classList.add('empty-state');
      container.textContent = 'Нет активных трекеров';
      els.targetSelect.innerHTML = '';
      els.targetSelect.disabled = true;
      els.applyTargetBtn.disabled = true;
      els.saveDetectionBtn.disabled = true;
      return;
    }
    container.classList.remove('empty-state');
    
    // Сортируем трекеры: сначала target, затем по trackId
    const sortedTrackers = [...state.trackers].sort((a, b) => {
      if (a.isTarget && !b.isTarget) return -1;
      if (!a.isTarget && b.isTarget) return 1;
      return (a.trackId || 0) - (b.trackId || 0);
    });
    
    // Получаем существующие карточки
    const existingCards = new Map();
    Array.from(container.querySelectorAll('.tracker-card')).forEach(card => {
      // Пытаемся найти trackId разными способами для совместимости
      let trackId = card.dataset.trackId || card.getAttribute('data-track-id');
      // Если не нашли, пытаемся извлечь из текста заголовка
      if (!trackId) {
        const titleEl = card.querySelector('.tracker-header strong');
        if (titleEl) {
          const match = titleEl.textContent.match(/Track #(\d+)/);
          if (match) {
            trackId = match[1];
          }
        }
      }
      if (trackId) {
        const trackIdNum = Number(trackId);
        existingCards.set(trackIdNum, card);
        // Устанавливаем атрибут для будущих обновлений
        card.dataset.trackId = trackIdNum;
      }
    });
    
    // Обновляем или создаем карточки
    const newTrackIds = new Set();
    sortedTrackers.forEach((tracker) => {
      newTrackIds.add(tracker.trackId);
      let card = existingCards.get(tracker.trackId);
      
      if (!card) {
        // Создаем новую карточку
        card = document.createElement('div');
        card.className = 'tracker-card';
        card.dataset.trackId = tracker.trackId;
        
        const header = document.createElement('div');
        header.className = 'tracker-header';
        const title = document.createElement('strong');
        const confidence = document.createElement('span');
        header.append(title, confidence);
        
        const meta = document.createElement('div');
        meta.className = 'tracker-meta';
        
        const nameInput = document.createElement('input');
        nameInput.type = 'text';
        nameInput.className = 'name-input';
        nameInput.placeholder = 'Название цели';
        nameInput.addEventListener('change', () => updateTrackerName(tracker.trackId, nameInput.value));
        nameInput.addEventListener('click', (e) => e.stopPropagation());
        
        card.append(header, meta, nameInput);
        card.addEventListener('click', () => selectTracker(tracker.trackId));
        container.appendChild(card);
      }
      
      // Обновляем содержимое карточки
      card.classList.toggle('selected-target', tracker.isTarget || tracker.trackId === state.selectedTrackId);
      
      const header = card.querySelector('.tracker-header');
      const title = header.querySelector('strong');
      const confidence = header.querySelector('span');
      title.textContent = `Track #${tracker.trackId}${tracker.isTarget ? ' 🎯' : ''}`;
      const confValue = Number(tracker.confidence || tracker.lastConfidence || 0) * 100;
      confidence.textContent = `${confValue.toFixed(1)}%`;
      
      const meta = card.querySelector('.tracker-meta');
      meta.innerHTML = `
        <span>${tracker.label || 'object'}</span>
        <span>Hits: ${tracker.hits ?? '—'}</span>
        <span>Age: ${tracker.misses ?? '0'}</span>
      `;
      
      const nameInput = card.querySelector('.name-input');
      // Обновляем значение только если оно изменилось и поле не в фокусе
      if (nameInput !== activeElement) {
        nameInput.value = tracker.name || '';
      }
    });
    
    // Удаляем карточки трекеров, которых больше нет
    existingCards.forEach((card, trackId) => {
      if (!newTrackIds.has(trackId)) {
        card.remove();
      }
    });
    
    // Восстанавливаем фокусировку
    if (focusedTrackerId) {
      const focusedCard = container.querySelector(`[data-track-id="${focusedTrackerId}"]`) 
        || container.querySelector(`.tracker-card[data-track-id="${focusedTrackerId}"]`);
      if (focusedCard) {
        const focusedInput = focusedCard.querySelector('.name-input');
        if (focusedInput) {
          // Восстанавливаем значение и позицию курсора
          if (focusedInputValue !== null) {
            focusedInput.value = focusedInputValue;
          }
          // Используем setTimeout для восстановления фокуса после обновления DOM
          setTimeout(() => {
            focusedInput.focus();
            if (cursorPosition !== null && cursorPosition !== undefined) {
              focusedInput.setSelectionRange(cursorPosition, cursorPosition);
            }
          }, 0);
        }
      }
    }

    // Обновляем select для выбора target
    const currentSelectValue = els.targetSelect.value;
    els.targetSelect.innerHTML = sortedTrackers.map(t => {
      const displayName = t.name || `Track #${t.trackId}`;
      const targetMarker = t.isTarget ? ' 🎯' : '';
      return `<option value="${t.trackId}">${displayName}${targetMarker}</option>`;
    }).join('');
    els.targetSelect.disabled = false;
    els.applyTargetBtn.disabled = false;
    els.saveDetectionBtn.disabled = false;

    // Восстанавливаем значение select, если оно было установлено
    if (currentSelectValue && els.targetSelect.querySelector(`option[value="${currentSelectValue}"]`)) {
      els.targetSelect.value = currentSelectValue;
    } else if (state.selectedTrackId) {
      els.targetSelect.value = String(state.selectedTrackId);
    }
  }

  function selectTracker(trackId) {
    state.selectedTrackId = Number(trackId);
    els.targetSelect.value = String(trackId);
    drawTrackers();
  }

  async function updateTrackerName(trackId, name) {
    try {
      await fetchJSON(api.trackerName, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ trackId, name }),
      });
      const tracker = state.trackers.find(t => t.trackId === trackId);
      if (tracker) tracker.name = name;
      els.errorMessage.textContent = 'Имя обновлено';
    } catch (err) {
      els.errorMessage.textContent = `Не удалось обновить имя: ${err.message}`;
    }
  }

  async function handleTargetAssign() {
    const trackId = Number(els.targetSelect.value);
    if (!trackId) {
      els.errorMessage.textContent = 'Выберите трекер';
      return;
    }
    try {
      els.applyTargetBtn.disabled = true;
      await fetchJSON(api.trackerTarget, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ trackId }),
      });
      state.selectedTrackId = trackId;
      drawTrackers();
      els.errorMessage.textContent = 'Таргет назначен, серво подвес активен';
    } catch (err) {
      els.errorMessage.textContent = `Ошибка таргета: ${err.message}`;
    } finally {
      els.applyTargetBtn.disabled = false;
    }
  }

  async function handleSaveDetection() {
    const trackId = Number(els.targetSelect.value);
    if (!trackId) {
      els.errorMessage.textContent = 'Выберите трекер для сохранения';
      return;
    }
    try {
      els.saveDetectionBtn.disabled = true;
      els.errorMessage.textContent = 'Сохранение...';
      
      // Получаем имя трекера если есть
      const tracker = state.trackers.find(t => t.trackId === trackId);
      const name = tracker?.name || null;
      
      await fetchJSON(api.detectionsSave, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ trackId, name }),
      });
      els.errorMessage.textContent = 'Детекция сохранена успешно';
      
      // Обновляем список сохранённых если открыта вкладка
      const archiveTab = document.getElementById('tab-archive');
      if (archiveTab && archiveTab.classList.contains('active')) {
        loadSavedDetections();
      }
    } catch (err) {
      els.errorMessage.textContent = `Ошибка сохранения: ${err.message}`;
    } finally {
      els.saveDetectionBtn.disabled = false;
    }
  }

  // Saved detections
  async function loadSavedDetections() {
    try {
      const params = new URLSearchParams();
      if (els.savedDate.value) params.set('date', els.savedDate.value);
      const data = await fetchJSON(`${api.detectionsSaved}?${params.toString()}`);
      const items = Array.isArray(data.items) ? data.items : [];
      renderSavedList(items);
    } catch (err) {
      console.error('Ошибка загрузки сохранённых', err);
      renderSavedList([]);
    }
  }

  function renderSavedList(items) {
    const container = els.savedList;
    if (!container) return; // Элемент может отсутствовать на некоторых страницах
    container.innerHTML = '';
    if (!items.length) {
      const p = document.createElement('p');
      p.textContent = 'Нет сохранённых элементов';
      p.style.textAlign = 'center';
      p.style.color = '#94a3b8';
      p.style.padding = '24px';
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
      img.alt = item.id || 'gif';
      img.loading = 'lazy';
      thumb.appendChild(img);
      const caption = document.createElement('div');
      caption.className = 'saved-caption';
      caption.textContent = item.name || item.id || 'GIF';
      card.append(thumb, caption);
      card.addEventListener('click', () => openGifModal(item));
      container.appendChild(card);
    });
  }

  async function openGifModal(item) {
    const modal = document.getElementById('gif-modal');
    const img = document.getElementById('gif-modal-image');
    const list = document.getElementById('gif-modal-dl');
    if (!modal || !img || !list) return;
    
    const gifUrl = item.gifPath ? `${backendOrigin}${item.gifPath}` : '';
    img.src = gifUrl;
    img.alt = item.id || 'gif';
    
    // Показываем модальное окно сразу
    modal.classList.remove('hidden');
    modal.setAttribute('aria-hidden', 'false');
    
    // Показываем загрузку данных
    list.innerHTML = '<dt>Загрузка...</dt><dd>Загрузка данных...</dd>';
    
    // Загружаем полные данные из JSON файла
    try {
      const jsonUrl = item.jsonPath ? `${backendOrigin}${item.jsonPath}` : null;
      if (jsonUrl) {
        const fullData = await fetchJSON(jsonUrl);
        // Передаем только данные из detection, исключая метаданные
        setMetaList(list, fullData);
      } else {
        // Если нет jsonPath, используем то что есть
        setMetaList(list, item);
      }
    } catch (err) {
      console.error('Ошибка загрузки данных детекции:', err);
      list.innerHTML = '<dt>Ошибка</dt><dd>Не удалось загрузить данные</dd>';
    }
    
    document.getElementById('gif-modal-close').onclick = closeGifModal;
    document.getElementById('gif-modal-backdrop').onclick = closeGifModal;
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') closeGifModal();
    }, { once: true });
  }

  function closeGifModal() {
    const modal = document.getElementById('gif-modal');
    if (!modal) return;
    modal.classList.add('hidden');
    modal.setAttribute('aria-hidden', 'true');
    const img = document.getElementById('gif-modal-image');
    if (img) img.src = '';
  }

  function setMetaList(container, payload = {}) {
    container.innerHTML = '';
    
    // Форматирование даты и времени
    const formatTimestamp = (timestamp) => {
      if (timestamp === null || timestamp === undefined) return '—';
      const date = new Date(typeof timestamp === 'number' ? timestamp * 1000 : timestamp);
      if (isNaN(date.getTime())) return '—';
      return date.toLocaleString('ru-RU', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        hour12: false
      });
    };
    
    // Форматирование координат bbox
    const formatBbox = (bbox) => {
      if (!Array.isArray(bbox) || bbox.length < 4) return '—';
      const [x1, y1, x2, y2] = bbox.map(v => Math.round(Number(v) || 0));
      const width = x2 - x1;
      const height = y2 - y1;
      return `[${x1}, ${y1}, ${x2}, ${y2}] (${width}×${height}px)`;
    };
    
    // Форматирование уверенности в процентах
    const formatConfidence = (conf) => {
      if (conf === null || conf === undefined) return '—';
      return `${(Number(conf) * 100).toFixed(2)}%`;
    };
    
    // Получаем данные из detection, исключая метаданные (id, date, savedAt, gifPath, jsonPath)
    const detection = payload.detection || {};
    
    // Выводим только данные из detection, которые были сохранены
    const pairs = [];
    
    // Track ID
    if (detection.trackId !== null && detection.trackId !== undefined) {
      pairs.push(['Track ID', String(detection.trackId)]);
    }
    
    // ID трекера (если есть)
    if (detection.id) {
      pairs.push(['ID трекера', String(detection.id)]);
    }
    
    // Метка (label)
    if (detection.label) {
      pairs.push(['Тип объекта', String(detection.label)]);
    }
    
    // Class ID
    if (detection.classId !== null && detection.classId !== undefined) {
      pairs.push(['Class ID', String(detection.classId)]);
    }
    
    // Уверенность
    if (detection.confidence !== null && detection.confidence !== undefined) {
      pairs.push(['Уверенность', formatConfidence(detection.confidence)]);
    }
    
    // Координаты bbox
    if (detection.bbox && Array.isArray(detection.bbox) && detection.bbox.length >= 4) {
      pairs.push(['Координаты (bbox)', formatBbox(detection.bbox)]);
    }
    
    // Время захвата
    if (detection.capturedAt !== null && detection.capturedAt !== undefined) {
      pairs.push(['Время захвата', formatTimestamp(detection.capturedAt)]);
    }
    
    // Первый раз замечен
    if (detection.firstSeen !== null && detection.firstSeen !== undefined) {
      pairs.push(['Первый раз замечен', formatTimestamp(detection.firstSeen)]);
    }
    
    // Последний раз замечен
    if (detection.lastSeen !== null && detection.lastSeen !== undefined) {
      pairs.push(['Последний раз замечен', formatTimestamp(detection.lastSeen)]);
    }
    
    // Количество попаданий
    if (detection.hits !== null && detection.hits !== undefined) {
      pairs.push(['Количество попаданий', String(detection.hits)]);
    } else if (detection.frames !== null && detection.frames !== undefined) {
      pairs.push(['Количество кадров', String(detection.frames)]);
    }
    
    // Модель
    if (detection.model) {
      pairs.push(['Модель', String(detection.model)]);
    }
    
    // Индекс камеры
    if (detection.cameraIndex !== null && detection.cameraIndex !== undefined) {
      pairs.push(['Индекс камеры', String(detection.cameraIndex)]);
    }
    
    // Имя (если есть)
    if (detection.name) {
      pairs.push(['Имя', String(detection.name)]);
    }
    
    // Если нет данных, показываем сообщение
    if (pairs.length === 0) {
      const dte = document.createElement('dt');
      dte.textContent = 'Нет данных';
      const dde = document.createElement('dd');
      dde.textContent = 'Данные детекции отсутствуют';
      container.append(dte, dde);
      return;
    }
    
    // Выводим все пары
    pairs.forEach(([dt, dd]) => {
      const dte = document.createElement('dt');
      dte.textContent = dt;
      const dde = document.createElement('dd');
      dde.textContent = dd;
      container.append(dte, dde);
    });
  }

  // ========== Функции автосохранения ==========
  async function loadAutosaveConfig() {
    try {
      console.log('[Autosave] Загрузка настроек автосохранения...');
      const data = await fetchJSON(api.autosaveConfig);
      
      const autoSave = data || {
        enabled: true,
        minConfidence: 0.3,
        minHits: 1,
        delay: 2000
      };

      console.log('[Autosave] Настройки загружены:', autoSave);
      updateAutosaveUI(autoSave);
      
      return autoSave;
    } catch (err) {
      console.error('Ошибка загрузки настроек автосохранения', err);
      // Используем значения по умолчанию
      const defaultConfig = {
        enabled: true,
        minConfidence: 0.3,
        minHits: 1,
        delay: 2000
      };
      console.log('[Autosave] Используем настройки по умолчанию:', defaultConfig);
      updateAutosaveUI(defaultConfig);
      return defaultConfig;
    }
  }

  async function saveAutosaveConfig() {
    if (!els.autosaveEnabled || !els.autosaveMinConfidence || !els.autosaveMinHits || !els.autosaveDelay) {
      console.warn('[Autosave] Элементы не найдены');
      return;
    }

    const autoSave = {
      enabled: els.autosaveEnabled.checked,
      minConfidence: Number(els.autosaveMinConfidence.value) || 0.3,
      minHits: Number(els.autosaveMinHits.value) || 1,
      delay: Number(els.autosaveDelay.value) || 2000
    };

    try {
      const data = await fetchJSON(api.autosaveConfig, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(autoSave)
      });

      els.errorMessage.textContent = '';
      
      // Обновляем UI после успешного сохранения
      updateAutosaveUI(data);
      
      // Показываем уведомление
      if (els.autosaveSaveBtn) {
        const originalText = els.autosaveSaveBtn.textContent;
        els.autosaveSaveBtn.textContent = '✓ Сохранено';
        els.autosaveSaveBtn.style.opacity = '0.7';
        setTimeout(() => {
          els.autosaveSaveBtn.textContent = originalText;
          els.autosaveSaveBtn.style.opacity = '1';
        }, 2000);
      }
    } catch (err) {
      console.error('Ошибка сохранения настроек автосохранения', err);
      els.errorMessage.textContent = `Не удалось сохранить настройки автосохранения: ${err.message}`;
    }
  }

  function updateAutosaveUI(autoSave) {
    console.log('[Autosave UI] Обновление интерфейса с настройками:', autoSave);
    
    if (els.autosaveEnabled) {
      els.autosaveEnabled.checked = !!autoSave.enabled;
      console.log('[Autosave UI] Чекбокс установлен:', els.autosaveEnabled.checked);
      updateAutosaveSettingsVisibility();
    } else {
      console.warn('[Autosave UI] Элемент autosave-enabled не найден');
    }
    
    if (els.autosaveMinConfidence) {
      els.autosaveMinConfidence.value = String(autoSave.minConfidence || 0.3);
      updateSliderValue('autosave-min-confidence-value', els.autosaveMinConfidence.value);
      console.log('[Autosave UI] Минимальная уверенность установлена:', els.autosaveMinConfidence.value);
    } else {
      console.warn('[Autosave UI] Элемент autosave-min-confidence не найден');
    }
    
    if (els.autosaveMinHits) {
      els.autosaveMinHits.value = String(autoSave.minHits || 1);
      updateSliderValue('autosave-min-hits-value', els.autosaveMinHits.value);
      console.log('[Autosave UI] Минимальное количество попаданий установлено:', els.autosaveMinHits.value);
    } else {
      console.warn('[Autosave UI] Элемент autosave-min-hits не найден');
    }
    
    if (els.autosaveDelay) {
      els.autosaveDelay.value = String(autoSave.delay || 2000);
      updateSliderValue('autosave-delay-value', els.autosaveDelay.value);
      console.log('[Autosave UI] Задержка установлена:', els.autosaveDelay.value);
    } else {
      console.warn('[Autosave UI] Элемент autosave-delay не найден');
    }
  }
  
  // Флаг для отслеживания инициализации обработчиков
  let autosaveHandlersInitialized = false;

  function initAutosaveHandlers() {
    // Предотвращаем повторную инициализацию
    if (autosaveHandlersInitialized) {
      console.log('[Autosave] Обработчики уже инициализированы');
      return;
    }

    // Инициализация обработчиков вкладки автосохранения
    if (els.autosaveSaveBtn) {
      els.autosaveSaveBtn.addEventListener('click', saveAutosaveConfig);
    }

    if (els.autosaveEnabled) {
      els.autosaveEnabled.addEventListener('change', () => {
        updateAutosaveSettingsVisibility();
        // Автоматически сохраняем при изменении чекбокса
        saveAutosaveConfig();
      });
      updateAutosaveSettingsVisibility();
    }

    // Обновление значений ползунков в реальном времени и автоматическое сохранение
    if (els.autosaveMinConfidence) {
      let confidenceTimeout;
      els.autosaveMinConfidence.addEventListener('input', (e) => {
        updateSliderValue('autosave-min-confidence-value', e.target.value);
        // Автосохранение с задержкой (debounce) после остановки изменения
        clearTimeout(confidenceTimeout);
        confidenceTimeout = setTimeout(() => {
          saveAutosaveConfig();
        }, 500);
      });
    }

    if (els.autosaveMinHits) {
      let hitsTimeout;
      els.autosaveMinHits.addEventListener('input', (e) => {
        updateSliderValue('autosave-min-hits-value', e.target.value);
        // Автосохранение с задержкой (debounce) после остановки изменения
        clearTimeout(hitsTimeout);
        hitsTimeout = setTimeout(() => {
          saveAutosaveConfig();
        }, 500);
      });
    }

    if (els.autosaveDelay) {
      let delayTimeout;
      els.autosaveDelay.addEventListener('input', (e) => {
        updateSliderValue('autosave-delay-value', e.target.value);
        // Автосохранение с задержкой (debounce) после остановки изменения
        clearTimeout(delayTimeout);
        delayTimeout = setTimeout(() => {
          saveAutosaveConfig();
        }, 500);
      });
    }

    autosaveHandlersInitialized = true;
    console.log('[Autosave] Обработчики инициализированы');
  }

  function updateAutosaveSettingsVisibility() {
    if (els.autosaveEnabled && els.autosaveSettingsGroup) {
      const isEnabled = els.autosaveEnabled.checked;
      console.log('[Autosave UI] Обновление видимости настроек, enabled:', isEnabled);
      if (isEnabled) {
        els.autosaveSettingsGroup.style.opacity = '1';
        els.autosaveSettingsGroup.style.pointerEvents = 'auto';
        // Также включаем все input элементы внутри
        els.autosaveSettingsGroup.querySelectorAll('input[type="range"]').forEach(input => {
          input.disabled = false;
        });
      } else {
        els.autosaveSettingsGroup.style.opacity = '0.5';
        els.autosaveSettingsGroup.style.pointerEvents = 'none';
        // Отключаем все input элементы внутри
        els.autosaveSettingsGroup.querySelectorAll('input[type="range"]').forEach(input => {
          input.disabled = true;
        });
      }
    } else {
      console.warn('[Autosave UI] Элементы для обновления видимости не найдены', {
        enabledEl: !!els.autosaveEnabled,
        settingsGroup: !!els.autosaveSettingsGroup
      });
    }
  }

  function updateSliderValue(valueId, value) {
    const valueEl = document.getElementById(valueId);
    if (valueEl) {
      if (valueId.includes('confidence')) {
        valueEl.textContent = Number(value).toFixed(2);
      } else if (valueId.includes('delay')) {
        valueEl.textContent = Number(value).toLocaleString('ru-RU');
      } else if (valueId.includes('fps')) {
        valueEl.textContent = Number(value).toFixed(1);
      } else {
        valueEl.textContent = Number(value);
      }
    }
  }

  // Функции для работы с настройками производительности
  async function loadPerformanceConfig() {
    try {
      const config = await fetchJSON(api.performanceConfig);
      updatePerformanceUI(config);
    } catch (err) {
      console.error('Ошибка загрузки настроек производительности:', err);
      updateStatus('Ошибка загрузки настроек производительности', 'error');
    }
  }

  function updatePerformanceUI(config) {
    if (els.performanceInferFps) {
      els.performanceInferFps.value = config.infer_fps || 5.0;
      updateSliderValue('performance-infer-fps-value', config.infer_fps || 5.0);
    }
    if (els.performanceConfidence) {
      els.performanceConfidence.value = config.confidence_threshold || 0.5;
      updateSliderValue('performance-confidence-value', config.confidence_threshold || 0.5);
    }
    if (els.performanceJpegStream) {
      els.performanceJpegStream.value = config.jpeg_quality_stream || 60;
      updateSliderValue('performance-jpeg-stream-value', config.jpeg_quality_stream || 60);
    }
    if (els.performanceQueueSize) {
      els.performanceQueueSize.value = config.max_infer_queue_size || 2;
      updateSliderValue('performance-queue-size-value', config.max_infer_queue_size || 2);
    }
    if (els.performanceInputSize) {
      els.performanceInputSize.value = config.input_size || 640;
      updateSliderValue('performance-input-size-value', config.input_size || 640);
    }
    if (els.performanceDrawDetections) {
      els.performanceDrawDetections.checked = config.draw_detections !== false;
    }
  }

  async function savePerformanceConfig() {
    try {
      const config = {
        infer_fps: parseFloat(els.performanceInferFps.value),
        confidence_threshold: parseFloat(els.performanceConfidence.value),
        jpeg_quality_stream: parseInt(els.performanceJpegStream.value),
        max_infer_queue_size: parseInt(els.performanceQueueSize.value),
        input_size: parseInt(els.performanceInputSize.value),
        draw_detections: els.performanceDrawDetections.checked,
      };

      const result = await fetchJSON(api.performanceConfig, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config),
      });

      if (result.success) {
        updateStatus('Настройки производительности применены', 'detected');
        // Обновляем метрики
        await loadPerformanceConfig();
      }
    } catch (err) {
      console.error('Ошибка сохранения настроек производительности:', err);
      updateStatus(`Ошибка: ${err.message}`, 'error');
    }
  }

  function initPerformanceHandlers() {
    // Загружаем метрики при открытии вкладки
    refreshStatus();
    // Обновление значений слайдеров
    if (els.performanceInferFps) {
      els.performanceInferFps.addEventListener('input', (e) => {
        updateSliderValue('performance-infer-fps-value', e.target.value);
      });
    }
    if (els.performanceConfidence) {
      els.performanceConfidence.addEventListener('input', (e) => {
        updateSliderValue('performance-confidence-value', e.target.value);
      });
    }
    if (els.performanceJpegStream) {
      els.performanceJpegStream.addEventListener('input', (e) => {
        updateSliderValue('performance-jpeg-stream-value', e.target.value);
      });
    }
    if (els.performanceQueueSize) {
      els.performanceQueueSize.addEventListener('input', (e) => {
        updateSliderValue('performance-queue-size-value', e.target.value);
      });
    }
    if (els.performanceInputSize) {
      els.performanceInputSize.addEventListener('input', (e) => {
        updateSliderValue('performance-input-size-value', e.target.value);
      });
    }
    if (els.performanceApplyBtn) {
      els.performanceApplyBtn.addEventListener('click', async () => {
        els.performanceApplyBtn.disabled = true;
        try {
          await savePerformanceConfig();
        } finally {
          els.performanceApplyBtn.disabled = false;
        }
      });
    }
  }

  function initTabs() {
    els.tabButtons.forEach(btn => {
      btn.addEventListener('click', () => {
        const target = btn.dataset.tab;
        els.tabButtons.forEach(b => b.classList.toggle('active', b === btn));
        els.tabPanels.forEach(panel => panel.classList.toggle('active', panel.id === `tab-${target}`));
        if (target === 'archive') loadSavedDetections();
      });
    });
    
    // Инициализация вкладок панели управления
    const panelTabButtons = document.querySelectorAll('.panel-tab-button');
    const panelTabPanels = document.querySelectorAll('.panel-tab-panel');
    
    panelTabButtons.forEach(btn => {
      btn.addEventListener('click', () => {
        const target = btn.dataset.panelTab;
        panelTabButtons.forEach(b => b.classList.toggle('active', b === btn));
        panelTabPanels.forEach(panel => {
          const isActive = panel.id === `panel-tab-${target}`;
          panel.classList.toggle('active', isActive);
        });
        // Загружаем сохраненные детекции при открытии вкладки "База"
        if (target === 'database') {
          loadSavedDetections();
        }
        // Загружаем настройки автосохранения при открытии вкладки "Автосохранение"
        if (target === 'autosave') {
          // Сначала инициализируем обработчики, потом загружаем настройки
          initAutosaveHandlers();
          loadAutosaveConfig().catch(err => {
            console.error('Ошибка загрузки настроек автосохранения при открытии вкладки:', err);
          });
        }
        // Загружаем настройки производительности при открытии вкладки "Производительность"
        if (target === 'performance') {
          initPerformanceHandlers();
          loadPerformanceConfig().catch(err => {
            console.error('Ошибка загрузки настроек производительности:', err);
          });
        }
      });
    });
  }

  function initEvents() {
    window.addEventListener('resize', resizeCanvas);
    if (els.img) {
      els.img.onload = () => {
        resizeCanvas();
        updateStatus('Поток подключен', 'detected');
      };
      els.img.onerror = () => {
        updateStatus('Ошибка потока', 'error');
        if (els.errorMessage) {
          els.errorMessage.textContent = 'Не удалось подключиться к потоку';
        }
        setTimeout(startStream, 2000);
      };
    }
    els.modelForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const model = els.modelSelect.value;
      if (!model) {
        els.errorMessage.textContent = 'Выберите модель';
        return;
      }
      try {
        els.modelApplyBtn.disabled = true;
        els.modelSelect.disabled = true;
        await fetchJSON(api.models, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ name: model }),
        });
        els.errorMessage.textContent = 'Модель переключена';
        await refreshModels();
      } catch (err) {
        els.errorMessage.textContent = `Ошибка модели: ${err.message}`;
      } finally {
        els.modelApplyBtn.disabled = false;
        els.modelSelect.disabled = false;
      }
    });
    els.trackerRefresh.addEventListener('click', () => refreshTrackers(true));
    els.applyTargetBtn.addEventListener('click', handleTargetAssign);
    els.saveDetectionBtn.addEventListener('click', handleSaveDetection);
    els.savedRefresh.addEventListener('click', loadSavedDetections);
    
    // Обработчики для сервоприводов
    if (els.servoPan) {
      els.servoPan.addEventListener('input', (e) => {
        const value = Number(e.target.value);
        if (els.servoPanValue) {
          els.servoPanValue.textContent = `${value}°`;
        }
        // Отправляем изменение с небольшой задержкой (debounce)
        clearTimeout(els.servoPan._timeout);
        els.servoPan._timeout = setTimeout(() => {
          setServoAngles(value, null);
        }, 100);
      });
    }
    
    if (els.servoTilt) {
      els.servoTilt.addEventListener('input', (e) => {
        const value = Number(e.target.value);
        if (els.servoTiltValue) {
          els.servoTiltValue.textContent = `${value}°`;
        }
        // Отправляем изменение с небольшой задержкой (debounce)
        clearTimeout(els.servoTilt._timeout);
        els.servoTilt._timeout = setTimeout(() => {
          setServoAngles(null, value);
        }, 100);
      });
    }
    
    if (els.servoResetBtn) {
      els.servoResetBtn.addEventListener('click', () => {
        setServoAngles(90, 90);
        if (els.servoPan) {
          els.servoPan.value = 90;
          if (els.servoPanValue) els.servoPanValue.textContent = '90°';
        }
        if (els.servoTilt) {
          els.servoTilt.value = 90;
          if (els.servoTiltValue) els.servoTiltValue.textContent = '90°';
        }
      });
    }
    if (els.savedClear) {
      els.savedClear.addEventListener('click', () => {
        els.savedDate.value = '';
        loadSavedDetections();
      });
    }
  }

  function startStream() {
    els.img.src = `${api.stream}?t=${Date.now()}`;
  }

  function init() {
    initTabs();
    initEvents();
    startStream();
    refreshStatus();
    refreshModels();
    refreshTrackers();
    // Обновляем статус MavLink и GPS каждые 3 секунды
    refreshMavLinkAndGPS();
    setInterval(refreshMavLinkAndGPS, 3000);
    // Обновляем детальный статус сервоприводов каждые 5 секунд
    refreshServoStatus();
    setInterval(refreshServoStatus, 5000);
  }

  init();
})();
