import { test, beforeEach } from 'node:test'
import assert from 'node:assert/strict'
import { mkdtemp, rm } from 'node:fs/promises'
import os from 'node:os'
import path from 'node:path'

// Each test gets isolated storage under TMP
let tempDir

beforeEach(async () => {
  if (tempDir) {
    await rm(tempDir, { recursive: true, force: true })
  }
  tempDir = await mkdtemp(path.join(os.tmpdir(), 'tracker-meta-'))
  process.env.DETECTIONS_DIR = path.join(tempDir, 'detections')
})

test('trackerMetaStore persists names between calls', async () => {
  const store = await import('../src/storage/trackerMetaStore.js')
  await store.setTrackerName(101, 'Main gate')
  await store.setTrackerName(202, 'Roof')

  const names = await store.listTrackerNames()
  assert.equal(names['101'], 'Main gate')
  assert.equal(names['202'], 'Roof')

  // Re-import module to ensure persistence
  const freshStore = await import('../src/storage/trackerMetaStore.js?update=' + Date.now())
  const name = await freshStore.getTrackerName(101)
  assert.equal(name, 'Main gate')

  await freshStore.setTrackerName(101, '')
  const updated = await freshStore.getTrackerName(101)
  assert.equal(updated, undefined)
})

