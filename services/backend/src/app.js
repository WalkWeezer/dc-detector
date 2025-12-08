import express from 'express'
import cors from 'cors'
import morgan from 'morgan'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { Readable } from 'node:stream'
import fs from 'node:fs'
import { config } from './config.js'

// Получаем __dirname для ES modules
const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)
import { detectionsRouter, detectionStatusHandler } from './routes/detections.js'
import { internalRouter } from './routes/internal.js'
import { configRouter } from './routes/config.js'
import { trackersRouter } from './routes/trackers.js'
import { callDetectionJson } from './utils/detectionClient.js'

export function createApp() {
  try {
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

  // Раздача статики фронтенда (для продакшена)
  // На проде всегда используем исходники напрямую, без сборки Vite
  // Пробуем несколько вариантов пути к фронтенду
  let frontendPath
  const possiblePaths = [
    path.resolve(process.cwd(), '../../frontend'),  // Если запускаем из services/backend/
    path.resolve(process.cwd(), '../frontend'),    // Если запускаем из корня проекта
    path.resolve(process.cwd(), 'frontend'),       // Если запускаем из services/
    path.resolve(__dirname, '../../../frontend'), // Относительно текущего файла
  ]
  
  // Ищем первый существующий путь
  for (const possiblePath of possiblePaths) {
    const indexPath = path.join(possiblePath, 'index.html')
    if (fs.existsSync(indexPath)) {
      frontendPath = possiblePath
      break
    }
  }
  
  // Если не нашли - используем первый вариант по умолчанию
  if (!frontendPath) {
    frontendPath = possiblePaths[0]
  }
  
  // Логирование для отладки
  console.log(`📁 Current working directory: ${process.cwd()}`)
  console.log(`📁 Frontend path: ${frontendPath}`)
  console.log(`   Using source files directly (no Vite build on production)`)
  
  // Проверяем существование ключевых файлов
  const indexHtmlPath = path.join(frontendPath, 'index.html')
  const piJsPath = path.join(frontendPath, 'pi.js')
  const indexExists = fs.existsSync(indexHtmlPath)
  const piJsExists = fs.existsSync(piJsPath)
  
  console.log(`   index.html exists: ${indexExists}`)
  console.log(`   pi.js exists: ${piJsExists}`)
  
  if (!indexExists) {
    console.error(`❌ ERROR: Frontend index.html not found at: ${indexHtmlPath}`)
    console.error(`   Please check that frontend directory exists and contains index.html`)
  }
  
  if (indexExists) {
    const stats = fs.statSync(indexHtmlPath)
    console.log(`   index.html modified: ${stats.mtime.toISOString()}`)
  }
  if (piJsExists) {
    const stats = fs.statSync(piJsPath)
    console.log(`   pi.js modified: ${stats.mtime.toISOString()}`)
  }
  
  // Статика фронтенда (CSS, JS, изображения) - только для не-API запросов
  app.use((req, res, next) => {
    // Пропускаем API и внутренние маршруты
    if (req.path.startsWith('/api/') || req.path.startsWith('/internal/') || req.path.startsWith('/files/')) {
      return next()
    }
    
    // Для всех статических файлов отключаем кеширование на проде
    // чтобы изменения были видны сразу после обновления файлов
    res.setHeader('Cache-Control', 'no-cache, no-store, must-revalidate, max-age=0')
    res.setHeader('Pragma', 'no-cache')
    res.setHeader('Expires', '0')
    
    // Используем express.static, но с отключенным кешированием
    express.static(frontendPath, { 
      maxAge: 0, // Без кеширования
      etag: false, // Отключаем ETag
      lastModified: false, // Отключаем Last-Modified
      fallthrough: true,
      setHeaders: (res, filePath) => {
        // Добавляем версионирование через заголовок для отладки
        try {
          const stats = fs.statSync(filePath)
          const version = stats.mtime.getTime()
          res.setHeader('X-File-Version', version.toString())
        } catch (err) {
          // Игнорируем ошибки
        }
      }
    })(req, res, () => {
      // Если файл не найден - отдаем index.html или pi.html (SPA fallback)
      // Проверяем, запрашивается ли pi.html напрямую
      let indexPath
      if (req.path === '/pi.html' || req.path === '/pi') {
        indexPath = path.join(frontendPath, 'pi.html')
      } else {
        indexPath = path.join(frontendPath, 'index.html')
      }
      
      // Если запрошенный файл не существует, пробуем альтернативный
      if (!fs.existsSync(indexPath)) {
        const altPath = indexPath.endsWith('pi.html') 
          ? path.join(frontendPath, 'index.html')
          : path.join(frontendPath, 'pi.html')
        if (fs.existsSync(altPath)) {
          indexPath = altPath
        }
      }
      
      if (!fs.existsSync(indexPath)) {
        console.error(`❌ Frontend HTML not found. Tried: ${indexPath}`)
        return res.status(404).send('Frontend not found. Please check that frontend files exist.')
      }
      
      res.sendFile(indexPath, (err) => {
        if (err) {
          console.error(`Error serving frontend HTML:`, err)
          res.status(500).send('Internal Server Error')
        }
      })
    })
  })

  // eslint-disable-next-line no-unused-vars
  app.use((err, _req, res, _next) => {
    console.error(err)
    res.status(500).json({ error: 'Internal Server Error' })
  })

    return app
  } catch (err) {
    console.error('❌ Error creating Express app:', err)
    throw err
  }
}


