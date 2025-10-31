import { createApp } from './app.js'
import { config } from './config.js'
import { runMigrations } from './migrations.js'

async function bootstrap() {
  await runMigrations()
  const app = createApp()
  app.listen(config.port, () => {
    console.log(`Backend listening on :${config.port}`)
  })
}

bootstrap().catch((err) => {
  console.error('Failed to start backend', err)
  process.exit(1)
})


