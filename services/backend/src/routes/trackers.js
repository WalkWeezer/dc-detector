import express from 'express'
import { getTrackerName, setTrackerName, listTrackerNames } from '../storage/trackerMetaStore.js'
import { callDetectionJson } from '../utils/detectionClient.js'
import { selectTrackerByCriteria } from '../utils/trackerSelector.js'
import { loadTrackerConfig } from '../config/trackerConfig.js'

export const trackersRouter = express.Router()

trackersRouter.get('/', async (_req, res) => {
  try {
    const detectionTrackers = await callDetectionJson('/api/trackers')
    const trackers = Array.isArray(detectionTrackers.trackers) ? detectionTrackers.trackers : []
    const names = await listTrackerNames()
    const enriched = trackers.map((tracker) => {
      const trackId = tracker.trackId
      const customName = names[String(trackId)]
      return {
        ...tracker,
        name: customName ?? tracker.name ?? null
      }
    })
    
    // Автоматический выбор целевого трекера, если включен
    const trackerConfig = await loadTrackerConfig()
    const autoConfig = trackerConfig.autoTargetSelection || {}
    let targetTrackId = detectionTrackers.target_track_id ?? detectionTrackers.targetTrackId ?? null
    
    if (autoConfig.enabled && autoConfig.selectionMode !== 'manual') {
      const currentTarget = targetTrackId
      const bestTracker = selectTrackerByCriteria(enriched, {
        minConfidence: autoConfig.minConfidence || 0.3,
        minHits: autoConfig.minHits || 1,
        preferredTrackId: currentTarget, // Сохраняем текущий, если он валиден
        autoSelect: true,
        selectionMode: autoConfig.selectionMode || 'priority'
      })
      
      if (bestTracker) {
        const bestTrackId = Number(bestTracker.trackId)
        // Обновляем цель только если она изменилась или не была установлена
        if (targetTrackId !== bestTrackId) {
          try {
            await callDetectionJson('/api/trackers/target', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ trackId: bestTrackId })
            })
            targetTrackId = bestTrackId
          } catch (err) {
            console.warn('Failed to auto-update target tracker:', err.message)
            // Продолжаем с текущим targetTrackId
          }
        }
      }
    }
    
    res.json({
      trackers: enriched,
      targetTrackId: targetTrackId
    })
  } catch (err) {
    console.error('Failed to load trackers', err)
    res.status(err.status ?? 502).json({ error: err.message || 'Failed to load trackers', details: err.payload })
  }
})

trackersRouter.post('/name', async (req, res) => {
  try {
    const { trackId, name } = req.body ?? {}
    const numericId = Number.parseInt(trackId, 10)
    if (!Number.isFinite(numericId)) {
      return res.status(400).json({ error: 'trackId is required' })
    }
    const stored = await setTrackerName(numericId, typeof name === 'string' ? name : '')
    res.json({ success: true, trackId: numericId, name: stored })
  } catch (err) {
    console.error('Failed to save tracker name', err)
    res.status(500).json({ error: 'Failed to save tracker name', details: err.message })
  }
})

trackersRouter.post('/target', async (req, res) => {
  try {
    const { trackId, autoSelect } = req.body ?? {}
    
    // Если trackId не указан, но autoSelect=true, выбираем автоматически
    if (autoSelect && (trackId === null || trackId === undefined)) {
      try {
        const detectionTrackers = await callDetectionJson('/api/trackers')
        const trackers = Array.isArray(detectionTrackers.trackers) ? detectionTrackers.trackers : []
        const trackerConfig = await loadTrackerConfig()
        const autoConfig = trackerConfig.autoTargetSelection || {}
        
        const bestTracker = selectTrackerByCriteria(trackers, {
          minConfidence: autoConfig.minConfidence || 0.3,
          minHits: autoConfig.minHits || 1,
          autoSelect: true,
          selectionMode: autoConfig.selectionMode || 'priority'
        })
        
        if (!bestTracker) {
          return res.status(404).json({ error: 'No suitable tracker found for auto-selection' })
        }
        
        const numericId = Number(bestTracker.trackId)
        const payload = await callDetectionJson('/api/trackers/target', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ trackId: numericId })
        })
        return res.json({ ...payload, autoSelected: true, selectedTrackId: numericId })
      } catch (err) {
        console.error('Failed to auto-select target', err)
        return res.status(500).json({ error: err.message || 'Failed to auto-select target', details: err.payload })
      }
    }
    
    // Если trackId === null, сбрасываем целевой трекер
    if (trackId === null) {
      const payload = await callDetectionJson('/api/trackers/target', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ trackId: null })
      })
      return res.json(payload)
    }
    
    // Ручной выбор трекера
    const numericId = Number.parseInt(trackId, 10)
    if (!Number.isFinite(numericId)) {
      return res.status(400).json({ error: 'trackId is required and must be a number' })
    }
    const payload = await callDetectionJson('/api/trackers/target', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ trackId: numericId })
    })
    res.json(payload)
  } catch (err) {
    console.error('Failed to assign target', err)
    res.status(err.status ?? 502).json({ error: err.message || 'Failed to assign target', details: err.payload })
  }
})

