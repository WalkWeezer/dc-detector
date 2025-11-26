/**
 * Менеджер автоматического выбора целевого трекера для серво-слежения
 */

import { callDetectionJson } from '../utils/detectionClient.js'
import { selectTrackerByCriteria } from './trackerSelector.js'
import { loadTrackerConfig } from '../config/trackerConfig.js'

let autoTargetInterval = null
let isRunning = false

/**
 * Запускает автоматическое обновление целевого трекера
 */
export async function startAutoTargetSelection() {
  if (isRunning) {
    return
  }

  const config = await loadTrackerConfig()
  const autoConfig = config.autoTargetSelection || {}
  
  if (!autoConfig.enabled || autoConfig.selectionMode === 'manual') {
    return
  }

  const updateInterval = autoConfig.updateInterval || 2000
  
  isRunning = true
  
  // Первое обновление сразу
  await updateAutoTarget()
  
  // Затем периодически
  autoTargetInterval = setInterval(async () => {
    try {
      await updateAutoTarget()
    } catch (err) {
      console.error('Auto target selection error:', err)
    }
  }, updateInterval)
  
  console.log(`Auto target selection started (interval: ${updateInterval}ms, mode: ${autoConfig.selectionMode})`)
}

/**
 * Останавливает автоматическое обновление
 */
export function stopAutoTargetSelection() {
  if (autoTargetInterval) {
    clearInterval(autoTargetInterval)
    autoTargetInterval = null
  }
  isRunning = false
  console.log('Auto target selection stopped')
}

/**
 * Обновляет целевой трекер автоматически
 */
async function updateAutoTarget() {
  try {
    const config = await loadTrackerConfig()
    const autoConfig = config.autoTargetSelection || {}
    
    if (!autoConfig.enabled || autoConfig.selectionMode === 'manual') {
      return
    }

    // Получаем текущие трекеры
    const detectionTrackers = await callDetectionJson('/api/trackers')
    const trackers = Array.isArray(detectionTrackers.trackers) ? detectionTrackers.trackers : []
    
    if (trackers.length === 0) {
      return
    }

    // Получаем текущий целевой трекер
    const currentTargetId = detectionTrackers.target_track_id ?? detectionTrackers.targetTrackId ?? null
    
    // Проверяем, валиден ли текущий целевой трекер
    const currentTarget = currentTargetId 
      ? trackers.find(t => Number(t.trackId) === Number(currentTargetId))
      : null
    
    // Если текущий целевой трекер все еще валиден и соответствует критериям, оставляем его
    if (currentTarget) {
      const confidence = Number(currentTarget.confidence || currentTarget.lastConfidence || 0)
      const hits = Number(currentTarget.hits || 0)
      
      if (confidence >= (autoConfig.minConfidence || 0.3) && 
          hits >= (autoConfig.minHits || 1) &&
          Array.isArray(currentTarget.bbox) && 
          currentTarget.bbox.length >= 4) {
        // Текущий трекер все еще хорош, не меняем
        return
      }
    }

    // Выбираем лучший трекер
    const bestTracker = selectTrackerByCriteria(trackers, {
      minConfidence: autoConfig.minConfidence || 0.3,
      minHits: autoConfig.minHits || 1,
      preferredTrackId: null, // Не сохраняем текущий, т.к. он не валиден
      autoSelect: true,
      selectionMode: autoConfig.selectionMode || 'priority'
    })

    if (bestTracker) {
      const bestTrackId = Number(bestTracker.trackId)
      
      // Обновляем только если выбран другой трекер
      if (bestTrackId !== currentTargetId) {
        await callDetectionJson('/api/trackers/target', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ trackId: bestTrackId })
        })
        console.log(`Auto-selected target tracker: ${bestTrackId} (confidence: ${bestTracker.confidence || bestTracker.lastConfidence}, hits: ${bestTracker.hits})`)
      }
    } else if (currentTargetId !== null) {
      // Если не нашли подходящий трекер, но был установлен целевой, сбрасываем
      await callDetectionJson('/api/trackers/target', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ trackId: null })
      })
      console.log('No suitable tracker found, target reset')
    }
  } catch (err) {
    // Игнорируем ошибки, чтобы не ломать основной процесс
    console.debug('Auto target update error:', err.message)
  }
}

/**
 * Принудительно обновляет целевой трекер (для ручного вызова)
 */
export async function forceUpdateAutoTarget() {
  await updateAutoTarget()
}

/**
 * Проверяет, запущен ли автоматический выбор
 */
export function isAutoTargetRunning() {
  return isRunning
}

