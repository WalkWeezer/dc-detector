import { readFile, writeFile, mkdir } from 'node:fs/promises'
import { dirname, join } from 'node:path'
import { config } from '../config.js'

const CONFIG_DIR = config.detectionsDataDir.replace(/[/\\]detections[/\\]?$/, '')
const CONFIG_PATH = join(CONFIG_DIR, 'tracker-config.json')

function getDefaultConfig() {
  return {
    iou_threshold: 0.3,
    max_age: 5,
    min_hits: 1,
    capture_fps: 12,
    colors: {
      fire: '#ff0000',
      smoke: '#808080',
      object: '#40ffbc'
    }
  }
}

function validateConfig(config) {
  const errors = []
  
  if (typeof config.iou_threshold !== 'number' || config.iou_threshold < 0 || config.iou_threshold > 1) {
    errors.push('iou_threshold must be a number between 0 and 1')
  }
  
  if (typeof config.max_age !== 'number' || config.max_age < 1 || config.max_age > 100) {
    errors.push('max_age must be a number between 1 and 100')
  }
  
  if (typeof config.min_hits !== 'number' || config.min_hits < 1 || config.min_hits > 100) {
    errors.push('min_hits must be a number between 1 and 100')
  }
  
  if (typeof config.capture_fps !== 'number' || config.capture_fps < 0.1 || config.capture_fps > 60) {
    errors.push('capture_fps must be a number between 0.1 and 60')
  }
  
  if (typeof config.colors !== 'object' || config.colors === null) {
    errors.push('colors must be an object')
  } else {
    for (const [key, value] of Object.entries(config.colors)) {
      if (typeof value !== 'string' || !/^#[0-9A-Fa-f]{6}$/.test(value)) {
        errors.push(`color for "${key}" must be a valid hex color (e.g., #ff0000)`)
      }
    }
  }
  
  return errors
}

export async function loadTrackerConfig() {
  try {
    const data = await readFile(CONFIG_PATH, 'utf-8')
    const config = JSON.parse(data)
    const errors = validateConfig(config)
    if (errors.length > 0) {
      console.warn('Config validation errors:', errors)
      return getDefaultConfig()
    }
    return { ...getDefaultConfig(), ...config }
  } catch (err) {
    if (err.code === 'ENOENT') {
      const defaultConfig = getDefaultConfig()
      await saveTrackerConfig(defaultConfig)
      return defaultConfig
    }
    console.error('Failed to load tracker config:', err)
    return getDefaultConfig()
  }
}

export async function saveTrackerConfig(config) {
  const errors = validateConfig(config)
  if (errors.length > 0) {
    throw new Error(`Config validation failed: ${errors.join(', ')}`)
  }
  
  try {
    await mkdir(dirname(CONFIG_PATH), { recursive: true })
    await writeFile(CONFIG_PATH, JSON.stringify(config, null, 2), 'utf-8')
    return config
  } catch (err) {
    console.error('Failed to save tracker config:', err)
    throw err
  }
}

export function getConfigPath() {
  return CONFIG_PATH
}

/**
 * Генерирует цвет для label на основе хеша строки
 * Обеспечивает консистентность: одинаковый label всегда получает одинаковый цвет
 */
export function generateColorForLabel(label) {
  if (!label || typeof label !== 'string') {
    return '#40ffbc' // дефолтный цвет
  }
  
  const normalizedLabel = label.toLowerCase().trim()
  
  // Простая хеш-функция (djb2 variant)
  let hash = 5381
  for (let i = 0; i < normalizedLabel.length; i++) {
    hash = ((hash << 5) + hash) + normalizedLabel.charCodeAt(i)
  }
  
  // Генерируем яркие различимые цвета используя HSL
  // Используем hue из хеша, фиксированные saturation и lightness для яркости
  const hue = Math.abs(hash) % 360
  const saturation = 70 + (Math.abs(hash) % 20) // 70-90% для яркости
  const lightness = 45 + (Math.abs(hash) % 15) // 45-60% для видимости на темном фоне
  
  // Конвертируем HSL в RGB, затем в HEX
  const h = hue / 360
  const s = saturation / 100
  const l = lightness / 100
  
  const c = (1 - Math.abs(2 * l - 1)) * s
  const x = c * (1 - Math.abs((h * 6) % 2 - 1))
  const m = l - c / 2
  
  let r, g, b
  if (h < 1/6) {
    r = c; g = x; b = 0
  } else if (h < 2/6) {
    r = x; g = c; b = 0
  } else if (h < 3/6) {
    r = 0; g = c; b = x
  } else if (h < 4/6) {
    r = 0; g = x; b = c
  } else if (h < 5/6) {
    r = x; g = 0; b = c
  } else {
    r = c; g = 0; b = x
  }
  
  r = Math.round((r + m) * 255)
  g = Math.round((g + m) * 255)
  b = Math.round((b + m) * 255)
  
  return `#${r.toString(16).padStart(2, '0')}${g.toString(16).padStart(2, '0')}${b.toString(16).padStart(2, '0')}`
}

/**
 * Проверяет наличие цветов для всех labels и добавляет отсутствующие
 * Возвращает обновленный конфиг с новыми цветами
 */
export async function ensureColorsForLabels(labels) {
  if (!Array.isArray(labels) || labels.length === 0) {
    return null
  }
  
  const currentConfig = await loadTrackerConfig()
  const colors = { ...currentConfig.colors }
  let hasChanges = false
  
  // Фильтруем валидные labels и извлекаем уникальные
  const uniqueLabels = [...new Set(
    labels
      .filter(label => label && typeof label === 'string' && label.trim().length > 0)
      .map(label => label.toLowerCase().trim())
  )]
  
  for (const label of uniqueLabels) {
    if (!colors[label]) {
      colors[label] = generateColorForLabel(label)
      hasChanges = true
    }
  }
  
  if (hasChanges) {
    const updatedConfig = {
      ...currentConfig,
      colors
    }
    await saveTrackerConfig(updatedConfig)
    return updatedConfig
  }
  
  return null
}

