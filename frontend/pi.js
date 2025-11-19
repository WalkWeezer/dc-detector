(() => {
  const els = {
    img: document.getElementById('server-stream'),
    overlay: document.getElementById('overlay'),
    statusIndicator: document.getElementById('status-indicator'),
    cameraType: document.getElementById('camera-type'),
    activeModel: document.getElementById('active-model'),
    detectionCount: document.getElementById('detection-count'),
    detectionConfidence: document.getElementById('detection-confidence'),
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
  const detectionOrigin = computeOrigin(8001);

  // Прямой доступ к detection service (как указано в требованиях)
  const api = {
    detection: `${detectionOrigin}/api/detection`,
    trackers: `${detectionOrigin}/api/trackers`,
    trackerName: `${backendOrigin}/api/trackers/name`, // Имена хранятся в backend
    trackerTarget: `${detectionOrigin}/api/trackers/target`,
    detectionsSave: `${backendOrigin}/api/detections/save`, // Сохранение через backend
    detectionsSaved: `${backendOrigin}/api/detections/saved`,
    models: `${detectionOrigin}/models`,
    stream: `${detectionOrigin}/video_feed_raw`,
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
    } catch (err) {
      updateStatus('Нет связи', 'error');
      els.errorMessage.textContent = err.message;
    } finally {
      setTimeout(refreshStatus, 2000);
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

  function openGifModal(item) {
    const modal = document.getElementById('gif-modal');
    const img = document.getElementById('gif-modal-image');
    const list = document.getElementById('gif-modal-dl');
    if (!modal || !img || !list) return;
    const gifUrl = item.gifPath ? `${backendOrigin}${item.gifPath}` : '';
    img.src = gifUrl;
    img.alt = item.id || 'gif';
    setMetaList(list, item);
    modal.classList.remove('hidden');
    modal.setAttribute('aria-hidden', 'false');
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
    const pairs = [
      ['ID', payload.id || '—'],
      ['Дата', payload.date || '—'],
      ['Метка', payload.detection?.label || '—'],
      ['TrackId', payload.detection?.trackId ?? '—'],
      ['Уверенность', payload.detection?.confidence ?? '—'],
    ];
    pairs.forEach(([dt, dd]) => {
      const dte = document.createElement('dt'); dte.textContent = dt;
      const dde = document.createElement('dd'); dde.textContent = dd;
      container.append(dte, dde);
    });
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
  }

  init();
})();
