import { promises as fs } from 'node:fs'
import path from 'node:path'
import { randomUUID } from 'node:crypto'
import { config } from '../config.js'
import JPEG from 'jpeg-js'
import sharp from 'sharp'
import GIFEncoder from 'gifencoder'
import { ensureColorsForLabels } from '../config/trackerConfig.js'

const baseDir = config.detectionsDataDir
const savedBaseDir = path.join(baseDir, 'saved')

async function ensureBaseDir() {
  await fs.mkdir(baseDir, { recursive: true })
}

async function ensureSavedDir(dateKey) {
  const dir = path.join(savedBaseDir, dateKey)
  await fs.mkdir(dir, { recursive: true })
  return dir
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
  const dateKey = dateKeyInput || new Date().toISOString().slice(0, 10)
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
  const idx = String(dataUrl).indexOf(',')
  if (idx === -1) return Buffer.from([])
  return Buffer.from(dataUrl.slice(idx + 1), 'base64')
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

export async function saveUserDetection({ detection, frames = [], fps = 5 }) {
  if (!detection || !Array.isArray(frames) || frames.length === 0) {
    throw new Error('detection and frames are required')
  }

  const epochSeconds = Number.isFinite(detection?.capturedAt) ? detection.capturedAt : Date.now() / 1000
  const dateKey = toDateKey(epochSeconds)
  const dir = await ensureSavedDir(dateKey)

  const id = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
  const jsonFile = path.join(dir, `${id}.json`)
  const gifFile = path.join(dir, `${id}.gif`)

  const limit = Math.min(frames.length, 30)
  const pick = frames.slice(-limit)

  // Build GIF
  const targetWidth = 320
  const rgbaFrames = []
  for (const dataUrl of pick) {
    const jpegBuf = parseDataUrl(dataUrl)
    if (jpegBuf.length === 0) continue
    // eslint-disable-next-line no-await-in-loop
    const frame = await toRgbaBuffer(jpegBuf, targetWidth)
    rgbaFrames.push(frame)
  }
  if (rgbaFrames.length === 0) {
    throw new Error('no valid frames')
  }
  const w = rgbaFrames[0].width
  const h = rgbaFrames[0].height
  const encoder = new GIFEncoder(w, h)
  // Render to buffer via stream
  const gifChunks = []
  encoder.createReadStream().on('data', (c) => gifChunks.push(c))
  encoder.start()
  encoder.setRepeat(0)
  encoder.setDelay(Math.max(50, Math.round(1000 / Math.max(1, fps))))
  encoder.setQuality(10)
  for (const fr of rgbaFrames) {
    encoder.addFrame(fr.data)
  }
  encoder.finish()
  const gifBuffer = Buffer.concat(gifChunks)

  // Save JSON and GIF
  const payload = {
    id,
    date: dateKey,
    savedAt: Date.now() / 1000,
    detection,
    gifPath: `/files/detections/saved/${dateKey}/${id}.gif`,
    jsonPath: `/files/detections/saved/${dateKey}/${id}.json`
  }
  await fs.writeFile(jsonFile, JSON.stringify(payload, null, 2), 'utf8')
  await fs.writeFile(gifFile, gifBuffer)

  return payload
}


