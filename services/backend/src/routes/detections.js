import express from 'express'
import { Readable } from 'node:stream'
import { query } from '../db.js'
import { config } from '../config.js'

export const detectionsRouter = express.Router()
export const internalDetectionsRouter = express.Router()

detectionsRouter.get('/', async (req, res, next) => {
  try {
    const { from, to, limit = '100' } = req.query
    const conditions = []
    const values = []

    if (from) {
      values.push(new Date(from))
      conditions.push(`created_at >= $${values.length}`)
    }
    if (to) {
      values.push(new Date(to))
      conditions.push(`created_at <= $${values.length}`)
    }

    const sql = `
      SELECT id, detected, confidence, payload, captured_at, created_at
      FROM detections
      ${conditions.length ? `WHERE ${conditions.join(' AND ')}` : ''}
      ORDER BY created_at DESC
      LIMIT $${values.length + 1}
    `

    values.push(Math.min(Number(limit) || 100, 500))
    const { rows } = await query(sql, values)
    res.json(rows)
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

internalDetectionsRouter.post('/', async (req, res, next) => {
  try {
    const { detected, confidence, detections, capturedAt } = req.body ?? {}
    const payload = detections ?? []
    const capturedDate = capturedAt ? new Date(Number(capturedAt) * 1000) : null
    const { rows } = await query(
      `INSERT INTO detections (detected, confidence, payload, captured_at)
       VALUES ($1, $2, $3::jsonb, $4)
       RETURNING id` ,
      [Boolean(detected), Number(confidence ?? 0), JSON.stringify(payload), capturedDate]
    )
    res.status(201).json({ id: rows[0].id })
  } catch (err) {
    next(err)
  }
})


