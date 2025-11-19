import express from 'express'
import cors from 'cors'
import morgan from 'morgan'
import path from 'node:path'
import { config } from './config.js'
import { detectionsRouter, detectionStatusHandler } from './routes/detections.js'
import { internalRouter } from './routes/internal.js'
import { configRouter } from './routes/config.js'
import { trackersRouter } from './routes/trackers.js'

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


