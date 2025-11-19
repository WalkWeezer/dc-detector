import express from 'express'
import { Readable } from 'node:stream'
import { config } from '../config.js'
import { listDetections, upsertDetections, listSavedDetections, saveUserDetection } from '../storage/detectionsStore.js'
import { loadTrackerConfig } from '../config/trackerConfig.js'
import { callDetectionJson } from '../utils/detectionClient.js'

export const detectionsRouter = express.Router()
export const internalDetectionsRouter = express.Router()

detectionsRouter.get('/', async (req, res, next) => {
  try {
    const { date } = req.query
    const normalizedDate = typeof date === 'string' && date.trim() ? date.trim() : undefined
    const result = await listDetections(normalizedDate)
    res.json(result)
  } catch (err) {
    next(err)
  }
})

export async function detectionStatusHandler(_req, res) {
  try {
    const payload = await callDetectionJson('/api/detection')
    res.json(payload)
  } catch (err) {
    console.error('Detection status error', err)
    res.status(err.status ?? 502).json({ error: err.message || 'Detection service unavailable', details: err.payload })
  }
}

detectionsRouter.get('/status', detectionStatusHandler)

detectionsRouter.get('/models', async (_req, res) => {
  try {
    const payload = await callDetectionJson('/models')
    // Нормализуем формат ответа для фронтенда
    const normalized = {
      models: Array.isArray(payload.available_models) ? payload.available_models : (Array.isArray(payload.models) ? payload.models : []),
      active: typeof payload.active_model === 'string' ? payload.active_model : (typeof payload.active === 'string' ? payload.active : null)
    }
    res.json(normalized)
  } catch (err) {
    console.error('Не удалось получить список моделей', err)
    res.status(err.status ?? 502).json({ error: err.message || 'Detection service unreachable', details: err.payload })
  }
})

detectionsRouter.post('/models', async (req, res) => {
  try {
    const switchPayload = await callDetectionJson('/models', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req.body ?? {})
    }, 5000)
    
    // После переключения получаем обновленный список моделей
    const modelsPayload = await callDetectionJson('/models')
    
    // Нормализуем формат ответа для фронтенда
    const normalized = {
      models: Array.isArray(modelsPayload.available_models) ? modelsPayload.available_models : (Array.isArray(modelsPayload.models) ? modelsPayload.models : []),
      active: typeof switchPayload.active_model === 'string' ? switchPayload.active_model : (typeof modelsPayload.active_model === 'string' ? modelsPayload.active_model : (typeof switchPayload.active === 'string' ? switchPayload.active : null))
    }
    res.json(normalized)
  } catch (err) {
    console.error('Не удалось переключить модель', err)
    res.status(err.status ?? 502).json({ error: err.message || 'Detection service unreachable', details: err.payload })
  }
})

detectionsRouter.get('/stream', async (req, res) => {
  const controller = new AbortController()
  const timeout = setTimeout(() => controller.abort(), 5000)
  try {
    const response = await fetch(`${config.detectionServiceUrl}/video_feed`, {
      signal: controller.signal
    })

    if (!response.ok || !response.body) {
      clearTimeout(timeout)
      return res.status(502).json({ error: 'Detection service stream unavailable' })
    }

    clearTimeout(timeout)

    res.setHeader('Content-Type', response.headers.get('content-type') ?? 'multipart/x-mixed-replace; boundary=frame')
    res.setHeader('Cache-Control', 'no-cache')
    res.setHeader('Connection', 'keep-alive')

    const stream = Readable.fromWeb(response.body)

    const cleanup = () => {
      stream.destroy()
    }

    req.on('close', cleanup)
    stream.on('error', () => {
      res.destroy()
    })

    stream.pipe(res)
  } catch (err) {
    res.status(502).json({ error: 'Detection service unreachable', details: err.message })
  } finally {
    clearTimeout(timeout)
  }
})
// Raw stream without server-drawn boxes (proxied to /video_feed_raw)
detectionsRouter.get('/stream-raw', async (req, res) => {
  const controller = new AbortController()
  const timeout = setTimeout(() => controller.abort(), 5000)
  try {
    const response = await fetch(`${config.detectionServiceUrl}/video_feed_raw`, {
      signal: controller.signal
    })

    if (!response.ok || !response.body) {
      clearTimeout(timeout)
      return res.status(502).json({ error: 'Detection service raw stream unavailable' })
    }

    clearTimeout(timeout)

    res.setHeader('Content-Type', response.headers.get('content-type') ?? 'multipart/x-mixed-replace; boundary=frame')
    res.setHeader('Cache-Control', 'no-cache')
    res.setHeader('Connection', 'keep-alive')

    const stream = Readable.fromWeb(response.body)

    const cleanup = () => {
      stream.destroy()
    }

    req.on('close', cleanup)
    stream.on('error', () => {
      res.destroy()
    })

    stream.pipe(res)
  } catch (err) {
    res.status(502).json({ error: 'Detection service unreachable', details: err.message })
  } finally {
    clearTimeout(timeout)
  }
})

// Новый поток для кадров с фронтенда - максимальная скорость
detectionsRouter.get('/stream-frontend', async (req, res) => {
  const controller = new AbortController()
  const timeout = setTimeout(() => controller.abort(), 5000)
  try {
    const response = await fetch(`${config.detectionServiceUrl}/video_feed_frontend`, {
      signal: controller.signal
    })

    if (!response.ok || !response.body) {
      clearTimeout(timeout)
      return res.status(502).json({ error: 'Detection service frontend stream unavailable' })
    }

    clearTimeout(timeout)

    res.setHeader('Content-Type', response.headers.get('content-type') ?? 'multipart/x-mixed-replace; boundary=frame')
    res.setHeader('Cache-Control', 'no-cache, no-store, must-revalidate')
    res.setHeader('Pragma', 'no-cache')
    res.setHeader('Connection', 'keep-alive')

    const stream = Readable.fromWeb(response.body)

    const cleanup = () => {
      stream.destroy()
    }

    req.on('close', cleanup)
    stream.on('error', () => {
      res.destroy()
    })

    stream.pipe(res)
  } catch (err) {
    res.status(502).json({ error: 'Detection service unreachable', details: err.message })
  } finally {
    clearTimeout(timeout)
  }
})

// Новый endpoint для отправки кадров с фронтенда - асинхронная обработка
detectionsRouter.post('/stream-frame', async (req, res) => {
  const controller = new AbortController()
  const timeout = setTimeout(() => controller.abort(), 5000)
  try {
    const response = await fetch(`${config.detectionServiceUrl}/stream_frame`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req.body ?? {}),
      signal: controller.signal
    })
    const result = await response.json()
    if (!response.ok) {
      return res.status(response.status).json(result)
    }
    res.json(result)
  } catch (err) {
    res.status(502).json({ error: 'Detection service unreachable', details: err.message })
  } finally {
    clearTimeout(timeout)
  }
})

detectionsRouter.post('/run', async (req, res) => {
  const controller = new AbortController()
  const timeout = setTimeout(() => controller.abort(), 5000)
  try {
    const response = await fetch(`${config.detectionServiceUrl}/detect`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req.body ?? {}),
      signal: controller.signal
    })
    const result = await response.json()
    if (!response.ok) {
      return res.status(response.status).json(result)
    }
    res.json(result)
  } catch (err) {
    res.status(502).json({ error: 'Detection service unreachable', details: err.message })
  } finally {
    clearTimeout(timeout)
  }
})

// Saved detections API
detectionsRouter.get('/saved', async (req, res, next) => {
  try {
    const { date } = req.query
    const normalizedDate = typeof date === 'string' && date.trim() ? date.trim() : undefined
    const result = await listSavedDetections(normalizedDate)
    res.json(result)
  } catch (err) {
    next(err)
  }
})

detectionsRouter.post('/save', async (req, res) => {
  try {
    const { detection, frames, fps, trackId, name } = req.body ?? {}

    if (detection && Array.isArray(frames) && frames.length > 0) {
      const payload = await saveUserDetection({ detection, frames, fps: Number(fps) || 5 })
      return res.status(201).json(payload)
    }

    const numericTrackId = Number.parseInt(trackId, 10)
    if (!Number.isFinite(numericTrackId)) {
      return res.status(400).json({ error: 'trackId is required when frames are not provided' })
    }

    const [trackersPayload, framesPayload, trackerConfig] = await Promise.all([
      callDetectionJson('/api/trackers'),
      callDetectionJson(`/api/trackers/${numericTrackId}/frames`, {}, 5000),
      loadTrackerConfig()
    ])

    const trackers = Array.isArray(trackersPayload.trackers) ? trackersPayload.trackers : []
    const target = trackers.find((t) => Number(t.trackId) === numericTrackId)
    if (!target) {
      return res.status(404).json({ error: 'Tracker not found' })
    }
    const cachedFrames = Array.isArray(framesPayload.frames) ? framesPayload.frames : []
    if (cachedFrames.length === 0) {
      return res.status(503).json({ error: 'Detection service did not return frames' })
    }

    const detectionPayload = {
      id: target.id,
      trackId: target.trackId,
      label: target.label,
      classId: target.classId ?? null,
      confidence: target.confidence ?? target.lastConfidence ?? 0,
      bbox: target.bbox,
      model: trackersPayload.active_model ?? trackersPayload.activeModel ?? null,
      capturedAt: target.lastSeen ?? Date.now() / 1000,
      cameraIndex: target.cameraIndex ?? null,
      name: name ?? target.name ?? null
    }

    const payload = await saveUserDetection({
      detection: detectionPayload,
      frames: cachedFrames,
      fps: Number(fps) || trackerConfig.capture_fps || 8
    })
    res.status(201).json(payload)
  } catch (err) {
    console.error('Save error', err)
    res.status(err.status ?? 500).json({ error: err.message || 'Unable to save detection', details: err.payload ?? err.stack })
  }
})

internalDetectionsRouter.post('/', async (req, res, next) => {
  try {
    const { detections, capturedAt, cameraIndex, model } = req.body ?? {}
    if (!Array.isArray(detections) || detections.length === 0) {
      return res.status(400).json({ error: 'detections array is required' })
    }

    const result = await upsertDetections(detections, {
      capturedAt: Number(capturedAt) || Date.now() / 1000,
      cameraIndex: typeof cameraIndex === 'number' ? cameraIndex : null,
      model: typeof model === 'string' ? model : null
    })

    res.status(201).json({ date: result?.date, count: result?.detections?.length ?? 0 })
  } catch (err) {
    next(err)
  }
})


