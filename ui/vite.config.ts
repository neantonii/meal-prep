import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  // Static SPA served by the FastAPI diary server (StaticFiles mount).
  build: {
    outDir: "../src/meal_prep/server/static",
    emptyOutDir: true,
  },
  server: {
    proxy: {
      "/api": "http://127.0.0.1:8000",
      "/cards": "http://127.0.0.1:8000",
    },
  },
})
