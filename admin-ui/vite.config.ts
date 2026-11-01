/// <reference types="vitest/config" />
import { fileURLToPath, URL } from 'node:url'
import tailwindcss from '@tailwindcss/vite'
import { tanstackRouter } from '@tanstack/router-plugin/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// STAFF_BACKEND — другой адрес Django, если 8000 занят (например, Docker).
const backend = process.env.STAFF_BACKEND ?? 'http://127.0.0.1:8000'
const proxied = ['/api', '/admin', '/media', '/static']

export default defineConfig({
  base: '/panel/',
  plugins: [
    // Router plugin must come before the React plugin.
    tanstackRouter({ target: 'react', autoCodeSplitting: true }),
    react(),
    tailwindcss(),
  ],
  resolve: {
    alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
  },
  server: {
    port: 5173,
    strictPort: true,
    proxy: Object.fromEntries(
      proxied.map((path) => [path, { target: backend, changeOrigin: false }]),
    ),
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    include: ['src/**/*.test.{ts,tsx}'],
    css: false,
  },
})
