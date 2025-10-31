import express from 'express'
import { query } from '../db.js'
import { internalDetectionsRouter } from './detections.js'

export const internalRouter = express.Router()

internalRouter.get('/cameras/:id', async (req, res, next) => {
  try {
    const { id } = req.params
    const { rows } = await query(
      `SELECT id, name, rtsp_url, source, mode, enabled
       FROM cameras WHERE id = $1`,
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

internalRouter.use('/detections', internalDetectionsRouter)


