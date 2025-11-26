import express from 'express'
import cors from 'cors'
import morgan from 'morgan'
import path from 'node:path'
import { Readable } from 'node:stream'
import { config } from './config.js'
import { detectionsRouter, detectionStatusHandler } from './routes/detections.js'
import { internalRouter } from './routes/internal.js'
import { configRouter } from './routes/config.js'
import { trackersRouter } from './routes/trackers.js'
import { callDetectionJson } from './utils/detectionClient.js'

export function createApp() {
  const app = express()
  // Настройка CORS - важно, чтобы это было первым middleware
  app.use(cors({
    origin: (origin, callback) => {
      // Разрешаем все origins для разработки
      callback(null, true)
    },
    methods: ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS', 'PATCH'],
    allowedHeaders: ['Content-Type', 'Authorization', 'Accept', 'Origin', 'X-Requested-With'],
    exposedHeaders: ['Content-Type'],
    credentials: false,
    preflightContinue: false,
    optionsSuccessStatus: 204,
    maxAge: 86400 // Кешировать preflight на 24 часа
  }))
  app.use(express.json({ limit: config.jsonLimit }))
  app.use(morgan(config.logFormat))

  app.get('/health', (_req, res) => {
    res.json({ status: 'ok' })
  })

  app.use('/api/detections', detectionsRouter)
  app.use('/api/trackers', trackersRouter)
  app.get('/api/detection', detectionStatusHandler)
  app.use('/api/config', configRouter)
  app.use('/internal', internalRouter)

  // Прокси для /api/models (GET и POST) - для совместимости с pi.js
  app.get('/api/models', async (_req, res) => {
    try {
      const payload = await callDetectionJson('/models')
      res.json(payload)
    } catch (err) {
      console.error('Не удалось получить список моделей', err)
      res.status(err.status ?? 502).json({ error: err.message || 'Detection service unreachable', details: err.payload })
    }
  })

  app.post('/api/models', async (req, res) => {
    try {
      const payload = await callDetectionJson('/models', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(req.body ?? {})
      }, 5000)
      res.json(payload)
    } catch (err) {
      console.error('Не удалось переключить модель', err)
      res.status(err.status ?? 502).json({ error: err.message || 'Detection service unreachable', details: err.payload })
    }
  })

  // Прокси для /api/video_feed_raw - для совместимости с pi.js
  app.get('/api/video_feed_raw', async (req, res) => {
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

  // Раздача файлов данных (графики, сохраненные гифки и т.д.)
  const dataRoot = path.resolve(process.cwd(), 'data')
  app.use('/files', express.static(dataRoot, { fallthrough: true, index: false }))

  // eslint-disable-next-line no-unused-vars
  app.use((err, _req, res, _next) => {
    console.error(err)
    res.status(500).json({ error: 'Internal Server Error' })
  })

  return app
}


