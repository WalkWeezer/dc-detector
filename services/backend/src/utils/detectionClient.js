import { config } from '../config.js'

export async function callDetectionJson(pathname, { method = 'GET', headers, body } = {}, timeoutMs = 3000) {
  const controller = new AbortController()
  const timeout = setTimeout(() => controller.abort(), timeoutMs)
  const url = `${config.detectionServiceUrl}${pathname}`
  
  // Логируем попытку подключения (только в dev режиме или при ошибках)
  if (process.env.NODE_ENV === 'development' || process.env.DEBUG) {
    console.debug(`[DetectionClient] ${method} ${url}`)
  }
  
  try {
    const response = await fetch(url, {
      method,
      headers,
      body,
      signal: controller.signal
    })
    const payload = await response.json().catch(() => ({}))
    if (!response.ok) {
      const error = new Error(payload.error || response.statusText)
      error.status = response.status
      error.payload = payload
      console.error(`[DetectionClient] ${method} ${url} failed:`, response.status, payload)
      throw error
    }
    return payload
  } catch (err) {
    // Логируем ошибки подключения
    console.error(`[DetectionClient] Connection error to ${url}:`, err.message)
    // Обработка сетевых ошибок и таймаутов
    if (err.name === 'AbortError' || err.name === 'TimeoutError') {
      const error = new Error(`Detection service request timeout (${timeoutMs}ms)`)
      error.status = 504
      error.payload = { url, timeout: timeoutMs }
      throw error
    }
    
    // Обработка "fetch failed" - общая ошибка подключения в Node.js 18+
    const errMessage = err.message?.toLowerCase() || ''
    const errCode = err.code || ''
    
    if (errMessage.includes('fetch failed') || 
        errMessage.includes('econnrefused') || 
        errCode === 'ECONNREFUSED' ||
        errMessage.includes('connection refused')) {
      const error = new Error(`Cannot connect to detection service at ${url}`)
      error.status = 503
      error.payload = { 
        url, 
        detectionServiceUrl: config.detectionServiceUrl,
        message: 'Detection service is not reachable. Check DETECTION_URL configuration and ensure the service is running.',
        hint: 'On Raspberry Pi with Docker, use host.docker.internal or host IP address instead of localhost'
      }
      throw error
    }
    
    if (errMessage.includes('enotfound') || 
        errCode === 'ENOTFOUND' ||
        errMessage.includes('getaddrinfo failed')) {
      const error = new Error(`Cannot resolve detection service host: ${url}`)
      error.status = 503
      error.payload = { 
        url, 
        detectionServiceUrl: config.detectionServiceUrl,
        message: 'Cannot resolve hostname. Check DETECTION_URL configuration.',
        hint: 'On Raspberry Pi with Docker, use host.docker.internal or host IP address instead of localhost'
      }
      throw error
    }
    
    // Пробрасываем другие ошибки, но добавляем контекст
    if (!err.status) {
      err.status = 500
    }
    if (!err.payload) {
      err.payload = { url, detectionServiceUrl: config.detectionServiceUrl }
    }
    throw err
  } finally {
    clearTimeout(timeout)
  }
}

