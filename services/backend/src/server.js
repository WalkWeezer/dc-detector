import { createApp } from './app.js'
import { config } from './config.js'
import { startAutoTargetSelection } from './utils/autoTargetManager.js'
import { startAutoSave } from './utils/autoSaveManager.js'

console.log('🚀 Starting backend server...')
console.log(`📋 Configuration:`)
console.log(`   Port: ${config.port}`)
console.log(`   Detection Service URL: ${config.detectionServiceUrl}`)
console.log(`   Detections Dir: ${config.detectionsDataDir}`)
console.log(`   Working Directory: ${process.cwd()}`)

// Обработка необработанных ошибок
process.on('uncaughtException', (err) => {
  console.error('❌ Uncaught Exception:', err)
  process.exit(1)
})

process.on('unhandledRejection', (reason, promise) => {
  console.error('❌ Unhandled Rejection at:', promise, 'reason:', reason)
  process.exit(1)
})

let app
try {
  app = createApp()
} catch (err) {
  console.error('❌ Failed to create app:', err)
  console.error(err.stack)
  process.exit(1)
}

// Слушаем на всех интерфейсах (0.0.0.0) для доступа извне
app.listen(config.port, '0.0.0.0', async () => {
  console.log(`\n🚀 Backend listening on 0.0.0.0:${config.port}`)
  console.log(`📱 Frontend available at: http://localhost:${config.port}`)
  console.log(`🌐 Or from network: http://<your-ip>:${config.port}`)
  console.log(`\n📡 Detection Service URL: ${config.detectionServiceUrl}`)
  console.log(`📁 Detections data directory: ${config.detectionsDataDir}`)
  
  // Проверяем доступность detection service при запуске
  try {
    const testUrl = `${config.detectionServiceUrl}/health`
    const response = await fetch(testUrl, { signal: AbortSignal.timeout(3000) })
    if (response.ok) {
      console.log(`✅ Detection service is reachable at ${config.detectionServiceUrl}`)
    } else {
      console.warn(`⚠️  Detection service responded with status ${response.status}`)
    }
  } catch (err) {
    console.error(`❌ Cannot connect to detection service at ${config.detectionServiceUrl}`)
    console.error(`   Error: ${err.message}`)
    console.error(`   Hint: Ensure detection service is running and DETECTION_URL is correct`)
    console.error(`   Current DETECTION_URL: ${config.detectionServiceUrl}`)
  }
  
  // Запускаем автоматический выбор целевого трекера
  try {
    await startAutoTargetSelection()
  } catch (err) {
    console.warn('Failed to start auto target selection:', err.message)
  }
  
  // Запускаем автоматическое сохранение трекеров
  try {
    startAutoSave()
  } catch (err) {
    console.warn('Failed to start auto save:', err.message)
  }
}).on('error', (err) => {
  if (err.code === 'EADDRINUSE') {
    console.error(`❌ Port ${config.port} is already in use`)
    console.error(`   Please stop the process using this port or change BACKEND_PORT in .env`)
    console.error(`   To find the process: lsof -i :${config.port} or netstat -tulpn | grep ${config.port}`)
  } else {
    console.error(`❌ Failed to start server on port ${config.port}:`, err.message)
    console.error(err.stack)
  }
  process.exit(1)
})


