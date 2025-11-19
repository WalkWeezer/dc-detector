import express from 'express'
import { getTrackerName, setTrackerName, listTrackerNames } from '../storage/trackerMetaStore.js'
import { callDetectionJson } from '../utils/detectionClient.js'

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
    res.json({
      trackers: enriched,
      targetTrackId: detectionTrackers.target_track_id ?? detectionTrackers.targetTrackId ?? null
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
    const { trackId } = req.body ?? {}
    const numericId = Number.parseInt(trackId, 10)
    if (!Number.isFinite(numericId)) {
      return res.status(400).json({ error: 'trackId is required' })
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

