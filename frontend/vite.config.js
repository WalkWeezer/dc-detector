import { defineConfig } from 'vite'

export default defineConfig({
  base: './',
  server: {
    host: '0.0.0.0',
    port: 5173,
    watch: {
      // Better inside containers/WSL
      usePolling: true
    }
  },
  build: {
    outDir: 'dist',
    assetsDir: 'assets'
  }
})


