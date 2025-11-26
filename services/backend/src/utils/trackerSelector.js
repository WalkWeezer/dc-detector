/**
 * Утилита для автоматического выбора целевого трекера для слежения через серво
 */

/**
 * Вычисляет приоритет трекера на основе различных критериев
 * @param {Object} tracker - Объект трекера
 * @param {Object} options - Опции выбора
 * @returns {number} - Приоритет (больше = лучше)
 */
function calculateTrackerPriority(tracker, options = {}) {
  const {
    preferHighConfidence = true,
    preferHighHits = true,
    preferLargeSize = false,
    preferCenterPosition = false,
    confidenceWeight = 0.4,
    hitsWeight = 0.4,
    sizeWeight = 0.1,
    centerWeight = 0.1,
    frameWidth = 640,
    frameHeight = 480
  } = options

  let priority = 0

  // 1. Уверенность (confidence) - чем выше, тем лучше
  if (preferHighConfidence) {
    const confidence = Number(tracker.confidence || tracker.lastConfidence || 0)
    priority += confidence * confidenceWeight * 100
  }

  // 2. Количество хитов (hits) - чем больше, тем стабильнее трекер
  if (preferHighHits) {
    const hits = Number(tracker.hits || 0)
    // Нормализуем: считаем, что 10+ хитов = максимум
    const normalizedHits = Math.min(hits / 10, 1.0)
    priority += normalizedHits * hitsWeight * 100
  }

  // 3. Размер объекта (площадь bbox) - опционально
  if (preferLargeSize && Array.isArray(tracker.bbox) && tracker.bbox.length >= 4) {
    const [x1, y1, x2, y2] = tracker.bbox.map(Number)
    const area = (x2 - x1) * (y2 - y1)
    const frameArea = frameWidth * frameHeight
    const sizeRatio = area / frameArea
    priority += sizeRatio * sizeWeight * 100
  }

  // 4. Позиция относительно центра кадра - опционально
  if (preferCenterPosition && Array.isArray(tracker.bbox) && tracker.bbox.length >= 4) {
    const [x1, y1, x2, y2] = tracker.bbox.map(Number)
    const centerX = (x1 + x2) / 2
    const centerY = (y1 + y2) / 2
    const frameCenterX = frameWidth / 2
    const frameCenterY = frameHeight / 2
    
    // Расстояние от центра (чем ближе, тем лучше)
    const distance = Math.sqrt(
      Math.pow(centerX - frameCenterX, 2) + Math.pow(centerY - frameCenterY, 2)
    )
    const maxDistance = Math.sqrt(
      Math.pow(frameWidth, 2) + Math.pow(frameHeight, 2)
    )
    const centerScore = 1 - (distance / maxDistance)
    priority += centerScore * centerWeight * 100
  }

  return priority
}

/**
 * Выбирает лучший трекер из списка для автоматического слежения
 * @param {Array} trackers - Массив трекеров
 * @param {Object} options - Опции выбора
 * @returns {Object|null} - Выбранный трекер или null
 */
export function selectBestTracker(trackers, options = {}) {
  if (!Array.isArray(trackers) || trackers.length === 0) {
    return null
  }

  // Фильтруем только валидные трекеры с bbox
  const validTrackers = trackers.filter(t => {
    return (
      t &&
      typeof t.trackId !== 'undefined' &&
      Array.isArray(t.bbox) &&
      t.bbox.length >= 4
    )
  })

  if (validTrackers.length === 0) {
    return null
  }

  // Вычисляем приоритет для каждого трекера
  const trackersWithPriority = validTrackers.map(tracker => ({
    tracker,
    priority: calculateTrackerPriority(tracker, options)
  }))

  // Сортируем по приоритету (по убыванию)
  trackersWithPriority.sort((a, b) => b.priority - a.priority)

  // Возвращаем трекер с наивысшим приоритетом
  return trackersWithPriority[0].tracker
}

/**
 * Выбирает трекер по сложным критериям (комбинация условий)
 * @param {Array} trackers - Массив трекеров
 * @param {Object} criteria - Критерии выбора
 * @returns {Object|null} - Выбранный трекер или null
 */
export function selectTrackerByCriteria(trackers, criteria = {}) {
  if (!Array.isArray(trackers) || trackers.length === 0) {
    return null
  }

  const {
    minConfidence = 0.3,
    minHits = 1,
    preferredLabel = null,
    preferredTrackId = null,
    autoSelect = true,
    selectionMode = 'priority' // 'priority', 'hits', 'confidence', 'manual'
  } = criteria

  // Если указан конкретный trackId, используем его
  if (preferredTrackId !== null && preferredTrackId !== undefined) {
    const preferred = trackers.find(t => Number(t.trackId) === Number(preferredTrackId))
    if (preferred && Array.isArray(preferred.bbox) && preferred.bbox.length >= 4) {
      return preferred
    }
  }

  // Фильтруем трекеры по минимальным критериям
  let candidates = trackers.filter(t => {
    if (!t || !Array.isArray(t.bbox) || t.bbox.length < 4) {
      return false
    }

    const confidence = Number(t.confidence || t.lastConfidence || 0)
    const hits = Number(t.hits || 0)

    if (confidence < minConfidence) {
      return false
    }

    if (hits < minHits) {
      return false
    }

    if (preferredLabel && t.label !== preferredLabel) {
      return false
    }

    return true
  })

  if (candidates.length === 0) {
    return null
  }

  // Выбираем по режиму
  switch (selectionMode) {
    case 'hits':
      // Трекер с наибольшим количеством хитов
      candidates.sort((a, b) => {
        const hitsA = Number(a.hits || 0)
        const hitsB = Number(b.hits || 0)
        return hitsB - hitsA
      })
      return candidates[0]

    case 'confidence':
      // Трекер с наибольшей уверенностью
      candidates.sort((a, b) => {
        const confA = Number(a.confidence || a.lastConfidence || 0)
        const confB = Number(b.confidence || b.lastConfidence || 0)
        return confB - confA
      })
      return candidates[0]

    case 'priority':
    default:
      // Комплексный приоритет (по умолчанию)
      return selectBestTracker(candidates, {
        preferHighConfidence: true,
        preferHighHits: true,
        preferLargeSize: false,
        preferCenterPosition: false
      })

    case 'manual':
      // Ручной режим - не выбираем автоматически
      return null
  }
}

