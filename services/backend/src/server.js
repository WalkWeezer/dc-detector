import { createApp } from './app.js'
import { config } from './config.js'
import { startAutoTargetSelection } from './utils/autoTargetManager.js'

const app = createApp()
app.listen(config.port, async () => {
  console.log(`Backend listening on :${config.port}`)
  console.log(`Detection Service URL: ${config.detectionServiceUrl}`)
  console.log(`Detections data directory: ${config.detectionsDataDir}`)
  
  // Запускаем автоматический выбор целевого трекера
  try {
    await startAutoTargetSelection()
  } catch (err) {
    console.warn('Failed to start auto target selection:', err.message)
  }
})


