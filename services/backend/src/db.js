import pg from 'pg'
import { config } from './config.js'

const pool = new pg.Pool({ connectionString: config.databaseUrl })

pool.on('error', (err) => {
  console.error('Unexpected Postgres error', err)
})

export const query = (text, params = []) => pool.query(text, params)
export const getClient = () => pool.connect()


