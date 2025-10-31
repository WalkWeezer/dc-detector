import express from 'express'
import { query } from '../db.js'
import { config } from '../config.js'

export const detectionsRouter = express.Router()
export const internalDetectionsRouter = express.Router()

detectionsRouter.get('/', async (req, res, next) => {
  try {
    const { cameraId, from, to, limit = '100' } = req.query
    const conditions = []
    const values = []

    if (cameraId) {
      values.push(cameraId)
      conditions.push(`camera_id = $${values.length}`)
    }
    if (from) {
      values.push(new Date(from))
      conditions.push(`created_at >= $${values.length}`)
    }
    if (to) {
      values.push(new Date(to))
      conditions.push(`created_at <= $${values.length}`)
    }

    const sql = `
      SELECT id, camera_id, detected, confidence, payload, created_at
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
    const { cameraId, detected, confidence, detections, capturedAt } = req.body ?? {}
    if (!cameraId) {
      return res.status(400).json({ error: 'cameraId is required' })
    }
    const payload = detections ?? []
    const capturedDate = capturedAt ? new Date(Number(capturedAt) * 1000) : null
    const { rows } = await query(
      `INSERT INTO detections (camera_id, detected, confidence, payload, created_at)
       VALUES ($1, $2, $3, $4::jsonb, COALESCE($5, NOW()))
       RETURNING id` ,
      [cameraId, Boolean(detected), Number(confidence ?? 0), JSON.stringify(payload), capturedDate]
    )
    res.status(201).json({ id: rows[0].id })
  } catch (err) {
    next(err)
  }
})


