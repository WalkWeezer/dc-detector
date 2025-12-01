import { callDetectionJson } from './detectionClient.js'
import { loadTrackerConfig } from '../config/trackerConfig.js'
import { saveUserDetection } from '../storage/detectionsStore.js'

// Отслеживание трекеров, которые уже были автосохранены
const autoSavedTrackIds = new Set()

// Интервал проверки трекеров (мс)
const CHECK_INTERVAL_MS = 3000

let autoSaveInterval = null
let isRunning = false

/**
 * Проверяет и автосохраняет трекеры, которые соответствуют критериям
 */
async function checkAndAutoSaveTrackers() {
  if (isRunning) {
    return // Предотвращаем параллельные запуски
  }
  
  isRunning = true
  try {
    // Загружаем конфиг автосохранения
    const trackerConfig = await loadTrackerConfig()
    const autoSaveConfig = trackerConfig.autoSave || {}
    
    // Проверяем, включено ли автосохранение
    if (!autoSaveConfig.enabled) {
      return
    }
    
    const minConfidence = Number(autoSaveConfig.minConfidence) || 0.3
    const minHits = Number(autoSaveConfig.minHits) || 1
    
    // Получаем список активных трекеров
    let trackersPayload
    try {
      trackersPayload = await callDetectionJson('/api/trackers', {}, 5000)
    } catch (err) {
      console.debug(`[Auto-save] Не удалось получить список трекеров: ${err.message}`)
      return
    }
    
    const trackers = Array.isArray(trackersPayload.trackers) ? trackersPayload.trackers : []
    
    // Проверяем каждый трекер
    for (const tracker of trackers) {
      const trackId = Number(tracker.trackId)
      
      // Пропускаем уже автосохраненные трекеры
      if (autoSavedTrackIds.has(trackId)) {
        continue
      }
      
      // Проверяем критерии
      const confidence = Number(tracker.confidence || tracker.lastConfidence || 0)
      const hits = Number(tracker.hits || tracker.frames || 0)
      
      if (confidence < minConfidence) {
        console.debug(`[Auto-save] Трекер ${trackId}: недостаточная уверенность (${confidence.toFixed(2)} < ${minConfidence.toFixed(2)})`)
        continue
      }
      
      if (hits < minHits) {
        console.debug(`[Auto-save] Трекер ${trackId}: недостаточно попаданий (${hits} < ${minHits})`)
        continue
      }
      
      // Трекер соответствует критериям, сохраняем его
      console.log(`[Auto-save] 🎯 Трекер ${trackId} соответствует критериям (confidence: ${confidence.toFixed(2)}, hits: ${hits}), начинаю сохранение...`)
      
      try {
        await autoSaveTracker(trackId, tracker, trackerConfig, autoSaveConfig, trackersPayload)
      } catch (err) {
        console.error(`[Auto-save] ❌ Ошибка при автосохранении трекера ${trackId}:`, err.message)
        // Не добавляем в autoSavedTrackIds при ошибке, чтобы попробовать снова
      }
    }
  } catch (err) {
    console.error(`[Auto-save] Критическая ошибка при проверке трекеров:`, err.message)
  } finally {
    isRunning = false
  }
}

/**
 * Автосохраняет конкретный трекер
 */
async function autoSaveTracker(trackId, tracker, trackerConfig, autoSaveConfig, trackersPayload) {
  // Задержка перед сохранением, чтобы накопились кадры
  const delay = Number(autoSaveConfig.delay) || 2000
  console.debug(`[Auto-save] Трекер ${trackId}: ожидание ${delay}мс для накопления кадров...`)
  await new Promise(resolve => setTimeout(resolve, delay))
  
  // После задержки проверяем актуальное состояние трекера
  let currentTrackersPayload
  try {
    currentTrackersPayload = await callDetectionJson('/api/trackers', {}, 5000)
  } catch (err) {
    throw new Error(`Не удалось получить список трекеров после задержки: ${err.message}`)
  }
  
  const currentTrackers = Array.isArray(currentTrackersPayload.trackers) ? currentTrackersPayload.trackers : []
  const currentTracker = currentTrackers.find(t => Number(t.trackId) === trackId)
  
  if (!currentTracker) {
    console.debug(`[Auto-save] Трекер ${trackId}: не найден после задержки (возможно, уже удален)`)
    return
  }
  
  // Повторно проверяем критерии после задержки
  const minConfidence = Number(autoSaveConfig.minConfidence) || 0.3
  const minHits = Number(autoSaveConfig.minHits) || 1
  
  const currentConfidence = Number(currentTracker.confidence || currentTracker.lastConfidence || 0)
  const currentHits = Number(currentTracker.hits || currentTracker.frames || 0)
  
  if (currentConfidence < minConfidence) {
    console.debug(`[Auto-save] Трекер ${trackId}: недостаточная уверенность после задержки (${currentConfidence.toFixed(2)} < ${minConfidence.toFixed(2)})`)
    return
  }
  
  if (currentHits < minHits) {
    console.debug(`[Auto-save] Трекер ${trackId}: недостаточно попаданий после задержки (${currentHits} < ${minHits})`)
    return
  }
  
  console.log(`[Auto-save] Трекер ${trackId}: условия выполнены (confidence: ${currentConfidence.toFixed(2)}, hits: ${currentHits}), получаю кадры...`)
  
  // Получаем frames из detection service
  let framesPayload
  try {
    framesPayload = await callDetectionJson(`/api/trackers/${trackId}/frames`, {}, 8000)
  } catch (err) {
    throw new Error(`Не удалось получить кадры: ${err.message}`)
  }
  
  const cachedFrames = Array.isArray(framesPayload.frames) ? framesPayload.frames : []
  if (cachedFrames.length === 0) {
    console.debug(`[Auto-save] Трекер ${trackId}: нет кадров для сохранения`)
    return
  }
  
  console.log(`[Auto-save] Трекер ${trackId}: получено ${cachedFrames.length} кадров, сохраняю...`)
  
  const detectionPayload = {
    id: currentTracker.id || `tracker-${trackId}`,
    trackId: trackId,
    label: currentTracker.label || 'object',
    classId: currentTracker.classId ?? null,
    confidence: currentConfidence,
    bbox: Array.isArray(currentTracker.bbox) ? currentTracker.bbox : null,
    model: currentTrackersPayload.active_model ?? currentTrackersPayload.activeModel ?? null,
    capturedAt: Number(currentTracker.lastSeen || Date.now() / 1000),
    cameraIndex: currentTracker.cameraIndex ?? null
  }
  
  // Сохраняем
  const fps = trackerConfig.capture_fps || 20
  await saveUserDetection({
    detection: detectionPayload,
    frames: cachedFrames,
    fps: Number(fps)
  })
  
  console.log(`[Auto-save] ✅ Трекер ${trackId} успешно сохранен (${currentTracker.label || 'object'}, confidence: ${currentConfidence.toFixed(2)}, hits: ${currentHits})`)
  
  // Помечаем трекер как автосохраненный
  autoSavedTrackIds.add(trackId)
}

/**
 * Запускает автоматическое сохранение трекеров
 */
export function startAutoSave() {
  if (autoSaveInterval) {
    console.warn('[Auto-save] Автосохранение уже запущено')
    return
  }
  
  console.log('[Auto-save] 🚀 Запуск автоматического сохранения трекеров...')
  
  // Первая проверка сразу
  checkAndAutoSaveTrackers().catch(err => {
    console.error('[Auto-save] Ошибка при первой проверке:', err.message)
  })
  
  // Затем периодически
  autoSaveInterval = setInterval(() => {
    checkAndAutoSaveTrackers().catch(err => {
      console.error('[Auto-save] Ошибка при периодической проверке:', err.message)
    })
  }, CHECK_INTERVAL_MS)
  
  console.log(`[Auto-save] ✅ Автосохранение запущено (интервал: ${CHECK_INTERVAL_MS}мс)`)
}

/**
 * Останавливает автоматическое сохранение трекеров
 */
export function stopAutoSave() {
  if (autoSaveInterval) {
    clearInterval(autoSaveInterval)
    autoSaveInterval = null
    console.log('[Auto-save] ⏹️  Автосохранение остановлено')
  }
}

/**
 * Сбрасывает список автосохраненных трекеров (для тестирования или при изменении настроек)
 */
export function resetAutoSavedTrackers() {
  autoSavedTrackIds.clear()
  console.log('[Auto-save] 🔄 Список автосохраненных трекеров сброшен')
}

