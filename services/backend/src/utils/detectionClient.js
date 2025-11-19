import { config } from '../config.js'

export async function callDetectionJson(pathname, { method = 'GET', headers, body } = {}, timeoutMs = 3000) {
  const controller = new AbortController()
  const timeout = setTimeout(() => controller.abort(), timeoutMs)
  try {
    const response = await fetch(`${config.detectionServiceUrl}${pathname}`, {
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
      throw error
    }
    return payload
  } finally {
    clearTimeout(timeout)
  }
}

