import { readFile, writeFile, mkdir } from 'node:fs/promises'
import path from 'node:path'
import { config } from '../config.js'

const META_PATH = path.join(config.detectionsDataDir, 'tracker-meta.json')

let cache = { names: {} }
let loaded = false

async function ensureLoaded() {
  if (loaded) return
  try {
    const data = await readFile(META_PATH, 'utf8')
    const parsed = JSON.parse(data)
    if (parsed && typeof parsed === 'object') {
      cache = {
        names: typeof parsed.names === 'object' && parsed.names !== null ? parsed.names : {}
      }
    }
  } catch (err) {
    if (err.code !== 'ENOENT') {
      console.warn('Failed to read tracker meta file:', err.message)
    }
  }
  loaded = true
}

async function persist() {
  await mkdir(path.dirname(META_PATH), { recursive: true })
  await writeFile(META_PATH, JSON.stringify(cache, null, 2), 'utf8')
}

export async function listTrackerNames() {
  await ensureLoaded()
  return { ...cache.names }
}

export async function getTrackerName(trackId) {
  await ensureLoaded()
  const key = String(trackId)
  return cache.names[key]
}

export async function setTrackerName(trackId, name) {
  await ensureLoaded()
  const key = String(trackId)
  if (!name || !name.trim()) {
    delete cache.names[key]
  } else {
    cache.names[key] = name.trim()
  }
  await persist()
  return cache.names[key] ?? null
}

