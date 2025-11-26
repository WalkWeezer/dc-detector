import { promises as fs, createWriteStream } from 'node:fs'
import path from 'node:path'
import { randomUUID } from 'node:crypto'
import { config } from '../config.js'
import JPEG from 'jpeg-js'
import sharp from 'sharp'
import GIFEncoder from 'gif-encoder-2'
import { ensureColorsForLabels, loadTrackerConfig } from '../config/trackerConfig.js'
import { callDetectionJson } from '../utils/detectionClient.js'

const baseDir = config.detectionsDataDir
const savedBaseDir = path.join(baseDir, 'saved')

// Отслеживание трекеров, которые уже были автосохранены (чтобы не сохранять повторно)
const autoSavedTrackIds = new Set()

async function ensureBaseDir() {
  await fs.mkdir(baseDir, { recursive: true })
}

async function ensureSavedDir(dateKey) {
  try {
    // Сначала убеждаемся, что базовая директория существует
    await fs.mkdir(savedBaseDir, { recursive: true })
    const dir = path.join(savedBaseDir, dateKey)
    await fs.mkdir(dir, { recursive: true })
    
    // Проверяем права на запись
    try {
      const testFile = path.join(dir, '.write-test')
      await fs.writeFile(testFile, 'test', 'utf8')
      await fs.unlink(testFile)
    } catch (writeErr) {
      throw new Error(`No write permission in directory: ${dir}. Error: ${writeErr.message}`)
    }
    
    return dir
  } catch (err) {
    console.error('Failed to ensure saved directory:', {
      dateKey,
      savedBaseDir,
      error: err.message,
      code: err.code
    })
    throw new Error(`Failed to create saved directory: ${err.message}`)
  }
}

function toDateKey(input) {
  const date = input ? new Date(input * 1000) : new Date()
  if (Number.isNaN(date.getTime())) {
    return new Date().toISOString().slice(0, 10)
  }
  return date.toISOString().slice(0, 10)
}

function getFilePath(dateKey) {
  return path.join(baseDir, `${dateKey}.json`)
}

async function readDay(dateKey) {
  await ensureBaseDir()
  try {
    const buffer = await fs.readFile(getFilePath(dateKey), 'utf8')
    const parsed = JSON.parse(buffer)
    if (Array.isArray(parsed?.detections)) {
      return parsed
    }
  } catch (err) {
    if (err.code !== 'ENOENT') {
      console.warn('Unable to read detections file %s: %s', dateKey, err.message)
    }
  }
  return {
    date: dateKey,
    detections: []
  }
}

async function writeDay(dateKey, data) {
  await ensureBaseDir()
  const payload = {
    date: dateKey,
    detections: Array.isArray(data.detections) ? data.detections : []
  }
  await fs.writeFile(getFilePath(dateKey), JSON.stringify(payload, null, 2), 'utf8')
}

export async function listDetections(dateKeyInput) {
  const dateKey = dateKeyInput || new Date().toISOString().slice(0, 10)
  const day = await readDay(dateKey)
  const detections = day.detections.slice().sort((a, b) => {
    const left = b.lastSeen ?? 0
    const right = a.lastSeen ?? 0
    return left - right
  })
  return { date: day.date, detections }
}

function normalizeDetection(detection, defaults = {}) {
  if (!detection || typeof detection !== 'object') {
    return null
  }
  const {
    id,
    trackId,
    label,
    classId,
    confidence,
    bbox,
    cameraIndex,
    model,
    capturedAt,
    firstSeen,
    lastSeen,
    hits
  } = detection

  const numericTrackId = typeof trackId === 'number' ? trackId : Number.parseInt(trackId, 10)
  if (!Number.isFinite(numericTrackId)) {
    return null
  }

  const timestamp = Number.isFinite(capturedAt) ? capturedAt : defaults.capturedAt ?? Date.now() / 1000
  const firstSeenTs = Number.isFinite(firstSeen) ? firstSeen : defaults.firstSeen ?? timestamp
  const lastSeenTs = Number.isFinite(lastSeen) ? lastSeen : timestamp
  const hitCount = Number.isFinite(hits) ? Number(hits) : defaults.frames ?? 0
  const boxArray = Array.isArray(bbox) ? bbox.slice(0, 4).map((value) => Number(value) || 0) : null

  return {
    id: id ?? randomUUID(),
    trackId: numericTrackId,
    label: label ?? defaults.label ?? 'object',
    classId: Number.isFinite(classId) ? classId : defaults.classId ?? null,
    lastConfidence: Number.isFinite(confidence) ? confidence : defaults.confidence ?? 0,
    firstSeen: firstSeenTs,
    lastSeen: lastSeenTs,
    frames: hitCount,
    bbox: boxArray,
    cameraIndex: Number.isFinite(cameraIndex) ? cameraIndex : defaults.cameraIndex ?? null,
    model: model ?? defaults.model ?? null
  }
}

export async function upsertDetections(detections = [], meta = {}) {
  if (!Array.isArray(detections) || detections.length === 0) {
    return null
  }

  const epochSeconds = Number.isFinite(meta.capturedAt) ? meta.capturedAt : Date.now() / 1000
  const dateKey = toDateKey(epochSeconds)
  const day = await readDay(dateKey)
  const now = epochSeconds
  let changed = false

  for (const det of detections) {
    const normalized = normalizeDetection(det, {
      capturedAt: now,
      cameraIndex: meta.cameraIndex,
      model: meta.model,
      confidence: det?.confidence
    })

    if (!normalized) {
      continue
    }

    const existingIndex = day.detections.findIndex((entry) => entry.trackId === normalized.trackId)

    if (existingIndex >= 0) {
      const previous = day.detections[existingIndex]
      day.detections[existingIndex] = {
        ...previous,
        label: normalized.label ?? previous.label,
        classId: normalized.classId ?? previous.classId ?? null,
        lastConfidence: normalized.lastConfidence ?? previous.lastConfidence ?? 0,
        bbox: normalized.bbox ?? previous.bbox ?? null,
        firstSeen: previous.firstSeen ?? normalized.firstSeen,
        lastSeen: normalized.lastSeen,
        frames: Math.max(previous.frames ?? 0, normalized.frames ?? 0),
        model: normalized.model ?? previous.model ?? null,
        cameraIndex: normalized.cameraIndex ?? previous.cameraIndex ?? null
      }
    } else {
      const record = {
        id: normalized.id,
        trackId: normalized.trackId,
        label: normalized.label,
        classId: normalized.classId,
        lastConfidence: normalized.lastConfidence,
        firstSeen: normalized.firstSeen,
        lastSeen: normalized.lastSeen,
        frames: Math.max(1, normalized.frames ?? 1),
        bbox: normalized.bbox,
        model: normalized.model,
        cameraIndex: normalized.cameraIndex
      }
      day.detections.push(record)
      
      // Автоматическое сохранение нового трекера (асинхронно, не блокирует ответ)
      // Проверяем, не был ли уже автосохранен этот трекер
      if (!autoSavedTrackIds.has(normalized.trackId)) {
        console.log(`[Auto-save] Новый трекер обнаружен: ${normalized.trackId} (${normalized.label}, confidence: ${normalized.lastConfidence})`)
        autoSaveNewTracker(normalized, meta).catch(err => {
          console.warn('Failed to auto-save new tracker:', {
            trackId: normalized.trackId,
            error: err.message
          })
        })
      } else {
        console.log(`[Auto-save] Трекер ${normalized.trackId} уже был автосохранен ранее, пропускаем`)
      }
    }
    changed = true
  }

  if (changed) {
    await writeDay(dateKey, day)
    
    // Автоматически добавляем новые классы объектов в конфиг цветов
    // Делаем это асинхронно, не блокируя ответ
    const labels = day.detections
      .map(d => d.label)
      .filter(label => label && typeof label === 'string')
    
    if (labels.length > 0) {
      ensureColorsForLabels(labels).catch(err => {
        console.warn('Failed to ensure colors for labels:', err.message)
        // Не критичная ошибка, просто логируем
      })
    }
  }

  return { date: dateKey, detections: day.detections }
}

// -------- Saved detections (JSON + GIF) ---------

export async function listSavedDetections(dateKeyInput) {
  // Если дата не указана — вернуть все сохраненные за все дни
  if (!dateKeyInput) {
    try {
      const dirEntries = await fs.readdir(savedBaseDir, { withFileTypes: true })
      const items = []
      for (const ent of dirEntries) {
        if (!ent.isDirectory()) continue
        const dateKey = ent.name
        try {
          const files = await fs.readdir(path.join(savedBaseDir, dateKey), { withFileTypes: true })
          for (const f of files) {
            if (f.isFile() && f.name.endsWith('.json')) {
              const id = f.name.replace(/\.json$/, '')
              items.push({ id, date: dateKey, jsonPath: `/files/detections/saved/${dateKey}/${id}.json`, gifPath: `/files/detections/saved/${dateKey}/${id}.gif` })
            }
          }
        } catch {
          // ignore broken subdir
        }
      }
      // Отсортируем по дате (новые сверху) и id внутри даты
      items.sort((a, b) => {
        if (a.date !== b.date) return b.date.localeCompare(a.date)
        return b.id.localeCompare(a.id)
      })
      return { date: null, items }
    } catch (err) {
      if (err.code === 'ENOENT') {
        return { date: null, items: [] }
      }
      throw err
    }
  }

  // Иначе вернуть только за конкретный день
  const dateKey = dateKeyInput
  const dir = path.join(savedBaseDir, dateKey)
  try {
    const entries = await fs.readdir(dir, { withFileTypes: true })
    const items = []
    for (const entry of entries) {
      if (entry.isFile() && entry.name.endsWith('.json')) {
        const id = entry.name.replace(/\.json$/, '')
        items.push({ id, date: dateKey, jsonPath: `/files/detections/saved/${dateKey}/${id}.json`, gifPath: `/files/detections/saved/${dateKey}/${id}.gif` })
      }
    }
    items.sort((a, b) => a.id.localeCompare(b.id))
    return { date: dateKey, items }
  } catch (err) {
    if (err.code === 'ENOENT') {
      return { date: dateKey, items: [] }
    }
    throw err
  }
}

function parseDataUrl(dataUrl) {
  if (!dataUrl || typeof dataUrl !== 'string') {
    return Buffer.from([])
  }
  
  const str = String(dataUrl).trim()
  if (str.length === 0) {
    return Buffer.from([])
  }
  
  const idx = str.indexOf(',')
  if (idx === -1) {
    // Попробуем декодировать как чистый base64
    try {
      const buf = Buffer.from(str, 'base64')
      if (buf.length > 0) {
        return buf
      }
    } catch {
      // Игнорируем ошибку декодирования
    }
    return Buffer.from([])
  }
  
  try {
    const base64Part = str.slice(idx + 1)
    if (base64Part.length === 0) {
      return Buffer.from([])
    }
    return Buffer.from(base64Part, 'base64')
  } catch (err) {
    console.warn('Failed to parse data URL:', err.message)
    return Buffer.from([])
  }
}

async function toRgbaBuffer(jpegBuffer, targetWidth) {
  // Resize with sharp (keep aspect ratio), then decode to RGBA with jpeg-js
  let buf = jpegBuffer
  if (targetWidth && targetWidth > 0) {
    try {
      buf = await sharp(jpegBuffer).resize({ width: targetWidth }).jpeg({ quality: 85 }).toBuffer()
    } catch {
      // fallback: keep original buffer
    }
  }
  const decoded = JPEG.decode(buf, { useTArray: true })
  return { width: decoded.width, height: decoded.height, data: decoded.data }
}

function computeCropRectFromBBox(bbox, imgW, imgH) {
  if (!Array.isArray(bbox) || bbox.length < 4 || !Number.isFinite(imgW) || !Number.isFinite(imgH)) {
    return { left: 0, top: 0, width: Math.max(1, imgW || 1), height: Math.max(1, imgH || 1) }
  }
  const [x1, y1, x2, y2] = bbox.map(Number)
  let w = Math.max(1, Math.round(x2 - x1))
  let h = Math.max(1, Math.round(y2 - y1))
  // Паддинги, чтобы объект не обрезался при небольших сдвигах
  const padX = Math.max(10, Math.round(w * 0.1))
  const padY = Math.max(10, Math.round(h * 0.1))
  const cx = Math.round((x1 + x2) / 2)
  const cy = Math.round((y1 + y2) / 2)
  let left = Math.max(0, cx - Math.round(w / 2) - padX)
  let top = Math.max(0, cy - Math.round(h / 2) - padY)
  let right = Math.min(imgW, cx + Math.round(w / 2) + padX)
  let bottom = Math.min(imgH, cy + Math.round(h / 2) + padY)
  left = Math.max(0, left)
  top = Math.max(0, top)
  const width = Math.max(1, right - left)
  const height = Math.max(1, bottom - top)
  return { left: Math.floor(left), top: Math.floor(top), width: Math.floor(width), height: Math.floor(height) }
}

async function toRgbaBufferCropped(jpegBuffer, cropRect, targetWidth) {
  if (!jpegBuffer || jpegBuffer.length === 0) {
    throw new Error('Empty JPEG buffer')
  }
  
  let buf = jpegBuffer
  try {
    const s = sharp(jpegBuffer)
    const meta = await s.metadata()
    if (!meta || !meta.width || !meta.height) {
      throw new Error('Invalid image metadata')
    }
    const rect = cropRect || { left: 0, top: 0, width: meta.width, height: meta.height }
    buf = await s.extract(rect).resize({ width: targetWidth }).jpeg({ quality: 85 }).toBuffer()
  } catch (err) {
    // fallback: try simple resize
    try {
      buf = await sharp(jpegBuffer).resize({ width: targetWidth }).jpeg({ quality: 85 }).toBuffer()
    } catch (fallbackErr) {
      console.error('Sharp processing failed:', {
        original: err.message,
        fallback: fallbackErr.message,
        bufferSize: jpegBuffer.length
      })
      throw new Error(`Image processing failed: ${fallbackErr.message}`)
    }
  }
  
  if (!buf || buf.length === 0) {
    throw new Error('Empty processed buffer')
  }
  
  const decoded = JPEG.decode(buf, { useTArray: true })
  if (!decoded || !decoded.data || !decoded.width || !decoded.height) {
    throw new Error('Failed to decode JPEG')
  }
  
  return { width: decoded.width, height: decoded.height, data: decoded.data }
}

export async function saveUserDetection({ detection, frames = [], fps = 5 }) {
  if (!detection || !Array.isArray(frames) || frames.length === 0) {
    throw new Error('detection and frames are required')
  }

  try {
    const epochSeconds = Number.isFinite(detection?.capturedAt) ? detection.capturedAt : Date.now() / 1000
    const dateKey = toDateKey(epochSeconds)
    const dir = await ensureSavedDir(dateKey)

    const id = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
    const jsonFile = path.join(dir, `${id}.json`)
    const gifFile = path.join(dir, `${id}.gif`)

    const limit = Math.min(frames.length, 30)
    const pick = frames.slice(-limit)

    // Build GIF: кроп по bbox детекции
    const targetWidth = 320
    const rgbaFrames = []
    let cropRect = null
    
    // Рассчитать cropRect один раз по первой картинке и bbox
    if (Array.isArray(detection?.bbox) && pick.length > 0) {
      try {
        const firstBuf = parseDataUrl(pick[0])
        if (firstBuf.length > 0) {
          const meta = await sharp(firstBuf).metadata()
          cropRect = computeCropRectFromBBox(detection.bbox, meta.width || 0, meta.height || 0)
        }
      } catch (err) {
        console.warn('Failed to compute crop rect:', err.message)
        cropRect = null
      }
    }
    
    // Обрабатываем кадры
    for (let i = 0; i < pick.length; i++) {
      try {
        const dataUrl = pick[i]
        if (!dataUrl || typeof dataUrl !== 'string') {
          console.warn(`Skipping invalid frame ${i}`)
          continue
        }
        
        const jpegBuf = parseDataUrl(dataUrl)
        if (jpegBuf.length === 0) {
          console.warn(`Skipping empty frame ${i}`)
          continue
        }
        
        // eslint-disable-next-line no-await-in-loop
        const frame = await toRgbaBufferCropped(jpegBuf, cropRect, targetWidth)
        if (frame && frame.width > 0 && frame.height > 0) {
          rgbaFrames.push(frame)
        }
      } catch (err) {
        console.warn(`Error processing frame ${i}:`, err.message)
        // Продолжаем обработку остальных кадров
        continue
      }
    }
    
    if (rgbaFrames.length === 0) {
      throw new Error('no valid frames after processing')
    }
    
    const w = rgbaFrames[0].width
    const h = rgbaFrames[0].height
    
    if (!w || !h || w <= 0 || h <= 0) {
      throw new Error(`Invalid frame dimensions: ${w}x${h}`)
    }
    
    const encoder = new GIFEncoder(w, h)

    // Stream encoder output directly to the file and wait for finish to ensure integrity
    await new Promise((resolve, reject) => {
      const ws = createWriteStream(gifFile)
      let streamError = null
      
      encoder.createReadStream()
        .on('error', (err) => {
          streamError = err
          reject(err)
        })
        .pipe(ws)
        .on('finish', () => {
          if (!streamError) resolve()
        })
        .on('error', (err) => {
          streamError = err
          reject(err)
        })

      try {
        encoder.start()
        encoder.setRepeat(0)
        encoder.setDelay(Math.max(50, Math.round(1000 / Math.max(1, fps))))
        encoder.setQuality(10)
        for (const fr of rgbaFrames) {
          if (fr && fr.data && fr.data.length > 0) {
            encoder.addFrame(fr.data)
          }
        }
        encoder.finish()
      } catch (err) {
        reject(err)
      }
    })

    // Save JSON metadata
    const payload = {
      id,
      date: dateKey,
      savedAt: Date.now() / 1000,
      detection,
      gifPath: `/files/detections/saved/${dateKey}/${id}.gif`,
      jsonPath: `/files/detections/saved/${dateKey}/${id}.json`
    }
    await fs.writeFile(jsonFile, JSON.stringify(payload, null, 2), 'utf8')

    return payload
  } catch (err) {
    console.error('Error in saveUserDetection:', {
      message: err.message,
      stack: err.stack,
      detectionId: detection?.id || detection?.trackId,
      framesCount: frames?.length || 0
    })
    throw err
  }
}

// Автоматическое сохранение нового трекера
async function autoSaveNewTracker(normalized, meta) {
  const trackId = normalized.trackId
  try {
    const trackerConfig = await loadTrackerConfig()
    const autoSaveConfig = trackerConfig.autoSave || {}
    
    // Проверяем, включено ли автосохранение
    if (!autoSaveConfig.enabled) {
      console.log(`[Auto-save] Отключено для трекера ${trackId}`)
      return
    }
    
    console.log(`[Auto-save] Проверка трекера ${trackId}...`)
    
    // Проверяем минимальные требования
    const minConfidence = Number(autoSaveConfig.minConfidence) || 0.3
    const minHits = Number(autoSaveConfig.minHits) || 1
    
    // Сначала проверяем базовые условия
    if (normalized.lastConfidence < minConfidence) {
      console.log(`[Auto-save] Трекер ${trackId}: недостаточная уверенность (${normalized.lastConfidence} < ${minConfidence})`)
      return
    }
    
    // Задержка перед сохранением, чтобы накопились кадры
    const delay = Number(autoSaveConfig.delay) || 2000
    console.log(`[Auto-save] Трекер ${trackId}: ожидание ${delay}мс для накопления кадров...`)
    await new Promise(resolve => setTimeout(resolve, delay))
    
    // После задержки проверяем актуальное состояние трекера
    let trackersPayload
    try {
      trackersPayload = await callDetectionJson('/api/trackers')
    } catch (err) {
      console.warn(`[Auto-save] Трекер ${trackId}: не удалось получить список трекеров:`, err.message)
      return
    }
    
    const trackers = Array.isArray(trackersPayload.trackers) ? trackersPayload.trackers : []
    const currentTracker = trackers.find(t => Number(t.trackId) === trackId)
    
    if (!currentTracker) {
      console.log(`[Auto-save] Трекер ${trackId}: не найден после задержки (возможно, уже удален)`)
      return
    }
    
    // Проверяем количество попаданий из актуального состояния трекера
    const currentHits = Number(currentTracker.hits || currentTracker.frames || 0)
    if (currentHits < minHits) {
      console.log(`[Auto-save] Трекер ${trackId}: недостаточно попаданий (${currentHits} < ${minHits})`)
      return
    }
    
    // Проверяем уверенность из актуального состояния
    const currentConfidence = Number(currentTracker.confidence || currentTracker.lastConfidence || 0)
    if (currentConfidence < minConfidence) {
      console.log(`[Auto-save] Трекер ${trackId}: недостаточная уверенность после задержки (${currentConfidence} < ${minConfidence})`)
      return
    }
    
    console.log(`[Auto-save] Трекер ${trackId}: условия выполнены (hits: ${currentHits}, confidence: ${currentConfidence}), получаю кадры...`)
    
    // Получаем frames из detection service
    let framesPayload
    try {
      framesPayload = await callDetectionJson(`/api/trackers/${trackId}/frames`, {}, 8000)
    } catch (err) {
      console.warn(`[Auto-save] Трекер ${trackId}: не удалось получить кадры:`, err.message)
      return
    }
    
    const cachedFrames = Array.isArray(framesPayload.frames) ? framesPayload.frames : []
    if (cachedFrames.length === 0) {
      console.log(`[Auto-save] Трекер ${trackId}: нет кадров для сохранения`)
      return
    }
    
    console.log(`[Auto-save] Трекер ${trackId}: получено ${cachedFrames.length} кадров, сохраняю...`)
    
    const detectionPayload = {
      id: currentTracker.id || normalized.id,
      trackId: trackId,
      label: currentTracker.label || normalized.label,
      classId: currentTracker.classId ?? normalized.classId ?? null,
      confidence: currentConfidence,
      bbox: Array.isArray(currentTracker.bbox) ? currentTracker.bbox : normalized.bbox,
      model: trackersPayload.active_model ?? trackersPayload.activeModel ?? meta.model ?? null,
      capturedAt: Number(currentTracker.lastSeen || normalized.lastSeen),
      cameraIndex: currentTracker.cameraIndex ?? normalized.cameraIndex ?? null
    }
    
    // Сохраняем
    const fps = trackerConfig.capture_fps || 8
    await saveUserDetection({
      detection: detectionPayload,
      frames: cachedFrames,
      fps: Number(fps)
    })
    
    console.log(`[Auto-save] ✅ Трекер ${trackId} успешно сохранен (${currentTracker.label || 'object'}, confidence: ${currentConfidence.toFixed(2)}, hits: ${currentHits})`)
    
    // Помечаем трекер как автосохраненный, чтобы не сохранять повторно
    autoSavedTrackIds.add(trackId)
  } catch (err) {
    // Не критичная ошибка, просто логируем
    console.error(`[Auto-save] ❌ Ошибка сохранения трекера ${trackId}:`, {
      error: err.message,
      stack: err.stack
    })
  }
}


