import { createApp } from './app.js'
import { config } from './config.js'
import { startAutoTargetSelection } from './utils/autoTargetManager.js'
import { startAutoSave } from './utils/autoSaveManager.js'

const app = createApp()
app.listen(config.port, async () => {
  console.log(`Backend listening on :${config.port}`)
  console.log(`Detection Service URL: ${config.detectionServiceUrl}`)
  console.log(`Detections data directory: ${config.detectionsDataDir}`)
  
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
})


