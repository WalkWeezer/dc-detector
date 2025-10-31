import express from 'express'
import { query } from '../db.js'

export const camerasRouter = express.Router()

camerasRouter.get('/', async (_req, res) => {
  const { rows } = await query('SELECT id, name, rtsp_url, mode, source, enabled, created_at FROM cameras ORDER BY created_at ASC')
  res.json(rows)
})

camerasRouter.post('/', async (req, res, next) => {
  try {
    const { name, rtspUrl = '', source = '0', mode = 'local', enabled = true } = req.body ?? {}
    if (!name) {
      return res.status(400).json({ error: 'name is required' })
    }
    const { rows } = await query(
      `INSERT INTO cameras (name, rtsp_url, source, mode, enabled)
       VALUES ($1, $2, $3, $4, $5)
       RETURNING id, name, rtsp_url, source, mode, enabled, created_at`,
      [name, rtspUrl, source, mode, enabled]
    )
    res.status(201).json(rows[0])
  } catch (err) {
    next(err)
  }
})

camerasRouter.patch('/:id', async (req, res, next) => {
  try {
    const { id } = req.params
    const { name, rtspUrl, source, mode, enabled } = req.body ?? {}
    const { rows } = await query(
      `UPDATE cameras
       SET name = COALESCE($2, name),
           rtsp_url = COALESCE($3, rtsp_url),
           source = COALESCE($4, source),
           mode = COALESCE($5, mode),
           enabled = COALESCE($6, enabled)
       WHERE id = $1
       RETURNING id, name, rtsp_url, source, mode, enabled, created_at`,
      [id, name, rtspUrl, source, mode, enabled]
    )
    if (rows.length === 0) {
      return res.status(404).json({ error: 'Camera not found' })
    }
    res.json(rows[0])
  } catch (err) {
    next(err)
  }
})

camerasRouter.get('/:id', async (req, res, next) => {
  try {
    const { id } = req.params
    const { rows } = await query(
      'SELECT id, name, rtsp_url, source, mode, enabled, created_at FROM cameras WHERE id = $1',
      [id]
    )
    if (rows.length === 0) {
      return res.status(404).json({ error: 'Camera not found' })
    }
    res.json(rows[0])
  } catch (err) {
    next(err)
  }
})


