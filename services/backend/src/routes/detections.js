import express from 'express'
import { Readable } from 'node:stream'
import { config } from '../config.js'
import { listDetections, upsertDetections, listSavedDetections, saveUserDetection } from '../storage/detectionsStore.js'

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

detectionsRouter.get('/status', async (_req, res) => {
  const controller = new AbortController()
  const timeout = setTimeout(() => controller.abort(), 2000)
  try {
    const response = await fetch(`${config.detectionServiceUrl}/api/detection`, {
      signal: controller.signal
    })
    if (!response.ok) {
      return res.status(502).json({ error: 'Detection service unavailable' })
    }
    const body = await response.json()
    res.json(body)
  } catch (err) {
    res.status(502).json({ error: 'Detection service unreachable', details: err.message })
  } finally {
    clearTimeout(timeout)
  }
})

detectionsRouter.get('/models', async (_req, res) => {
  const controller = new AbortController()
  const timeout = setTimeout(() => controller.abort(), 2000)
  try {
    const response = await fetch(`${config.detectionServiceUrl}/models`, {
      signal: controller.signal
    })
    const body = await response.json()
    if (!response.ok) {
      return res.status(response.status).json(body)
    }
    res.json(body)
  } catch (err) {
    res.status(502).json({ error: 'Detection service unreachable', details: err.message })
  } finally {
    clearTimeout(timeout)
  }
})

detectionsRouter.post('/models', async (req, res) => {
  const controller = new AbortController()
  const timeout = setTimeout(() => controller.abort(), 5000)
  try {
    const response = await fetch(`${config.detectionServiceUrl}/models`, {
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
    const { detection, frames, fps } = req.body ?? {}
    if (!detection || !Array.isArray(frames) || frames.length === 0) {
      return res.status(400).json({ error: 'detection and frames are required' })
    }
    const payload = await saveUserDetection({ detection, frames, fps: Number(fps) || 5 })
    res.status(201).json(payload)
  } catch (err) {
    console.error('Save error', err)
    res.status(500).json({ error: 'Unable to save detection', details: err.message })
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


