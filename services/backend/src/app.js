import express from 'express'
import cors from 'cors'
import morgan from 'morgan'
import { config } from './config.js'
import { camerasRouter } from './routes/cameras.js'
import { detectionsRouter } from './routes/detections.js'
import { internalRouter } from './routes/internal.js'

export function createApp() {
  const app = express()
  app.use(cors())
  app.use(express.json({ limit: config.jsonLimit }))
  app.use(morgan(config.logFormat))

  app.get('/health', (_req, res) => {
    res.json({ status: 'ok' })
  })

  app.use('/api/cameras', camerasRouter)
  app.use('/api/detections', detectionsRouter)
  app.use('/internal', internalRouter)

  // eslint-disable-next-line no-unused-vars
  app.use((err, _req, res, _next) => {
    console.error(err)
    res.status(500).json({ error: 'Internal Server Error' })
  })

  return app
}


