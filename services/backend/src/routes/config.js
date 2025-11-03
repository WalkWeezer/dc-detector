import express from 'express'
import { loadTrackerConfig, saveTrackerConfig } from '../config/trackerConfig.js'
import { config } from '../config.js'

export const configRouter = express.Router()

configRouter.get('/tracker', async (_req, res, next) => {
  try {
    const trackerConfig = await loadTrackerConfig()
    res.json(trackerConfig)
  } catch (err) {
    next(err)
  }
})

configRouter.patch('/tracker', async (req, res, next) => {
  try {
    const current = await loadTrackerConfig()
    const updates = req.body ?? {}
    
    const updated = {
      ...current,
      ...(updates.iou_threshold !== undefined && { iou_threshold: Number(updates.iou_threshold) }),
      ...(updates.max_age !== undefined && { max_age: Number(updates.max_age) }),
      ...(updates.min_hits !== undefined && { min_hits: Number(updates.min_hits) }),
      ...(updates.capture_fps !== undefined && { capture_fps: Number(updates.capture_fps) }),
      ...(updates.colors && typeof updates.colors === 'object' && {
        colors: { ...current.colors, ...updates.colors }
      })
    }
    
    const saved = await saveTrackerConfig(updated)
    
    // Если обновлены параметры трекера, синхронизируем с detection service
    if (updates.iou_threshold !== undefined || updates.max_age !== undefined || updates.min_hits !== undefined) {
      try {
        const controller = new AbortController()
        const timeout = setTimeout(() => controller.abort(), 2000)
        await fetch(`${config.detectionServiceUrl}/api/tracker/config`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            iou_threshold: saved.iou_threshold,
            max_age: saved.max_age,
            min_hits: saved.min_hits
          }),
          signal: controller.signal
        })
        clearTimeout(timeout)
      } catch (err) {
        console.warn('Failed to sync tracker config to detection service:', err.message)
        // Не возвращаем ошибку, т.к. конфиг сохранен локально
      }
    }
    
    res.json(saved)
  } catch (err) {
    if (err.message.includes('validation')) {
      return res.status(400).json({ error: err.message })
    }
    next(err)
  }
})

configRouter.patch('/tracker/colors', async (req, res, next) => {
  try {
    const current = await loadTrackerConfig()
    const colorUpdates = req.body ?? {}
    
    if (typeof colorUpdates !== 'object' || Array.isArray(colorUpdates)) {
      return res.status(400).json({ error: 'colors must be an object' })
    }
    
    const updated = {
      ...current,
      colors: { ...current.colors, ...colorUpdates }
    }
    
    const saved = await saveTrackerConfig(updated)
    
    res.json(saved.colors)
  } catch (err) {
    if (err.message.includes('validation')) {
      return res.status(400).json({ error: err.message })
    }
    next(err)
  }
})

