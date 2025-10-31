import { promises as fs } from 'fs'
import path from 'path'
import { fileURLToPath } from 'url'
import { query, getClient } from './db.js'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)
const migrationsDir = path.resolve(__dirname, '../infra/db/migrations')

export async function runMigrations() {
  await ensureMigrationsTable()

  const files = await listMigrationFiles()
  for (const file of files) {
    const applied = await isMigrationApplied(file)
    if (applied) continue

    const sql = await fs.readFile(path.join(migrationsDir, file), 'utf-8')
    const client = await getClient()
    try {
      await client.query('BEGIN')
      await client.query(sql)
      await client.query(
        'INSERT INTO schema_migrations(filename, applied_at) VALUES ($1, NOW())',
        [file]
      )
      await client.query('COMMIT')
      console.log(`Applied migration ${file}`)
    } catch (err) {
      await client.query('ROLLBACK')
      console.error(`Failed migration ${file}`, err)
      throw err
    } finally {
      client.release()
    }
  }
}

async function ensureMigrationsTable() {
  await query(`
    CREATE TABLE IF NOT EXISTS schema_migrations (
      id SERIAL PRIMARY KEY,
      filename TEXT UNIQUE NOT NULL,
      applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
  `)
}

async function listMigrationFiles() {
  try {
    const entries = await fs.readdir(migrationsDir)
    return entries.filter((file) => file.endsWith('.sql')).sort()
  } catch (err) {
    if (err.code === 'ENOENT') {
      return []
    }
    throw err
  }
}

async function isMigrationApplied(filename) {
  const { rows } = await query('SELECT 1 FROM schema_migrations WHERE filename = $1', [filename])
  return rows.length > 0
}


