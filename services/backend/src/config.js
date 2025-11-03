import 'dotenv/config'
import path from 'node:path'

const DEFAULT_DETECTION_URL = 'http://localhost:8001'

export const config = {
  port: Number.parseInt(process.env.PORT ?? '8080', 10),
  detectionServiceUrl: process.env.DETECTION_URL ?? DEFAULT_DETECTION_URL,
  detectionsDataDir: path.resolve(process.cwd(), process.env.DETECTIONS_DIR ?? 'data/detections'),
  // Увеличенный лимит для загрузки кадров (gif сохранение)
  jsonLimit: process.env.JSON_LIMIT ?? '25mb',
  logFormat: process.env.LOG_FORMAT ?? 'dev'
}


