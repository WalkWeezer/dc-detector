import 'dotenv/config'

const DEFAULT_DATABASE_URL = 'postgres://postgres:postgres@localhost:5432/postgres'
const DEFAULT_DETECTION_URL = 'http://localhost:8001'

export const config = {
  port: Number.parseInt(process.env.PORT ?? '8080', 10),
  databaseUrl: process.env.DATABASE_URL ?? DEFAULT_DATABASE_URL,
  detectionServiceUrl: process.env.DETECTION_URL ?? DEFAULT_DETECTION_URL,
  jsonLimit: process.env.JSON_LIMIT ?? '1mb',
  logFormat: process.env.LOG_FORMAT ?? 'dev'
}


