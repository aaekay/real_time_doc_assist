import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      '/ws': {
        target: `ws://localhost:${process.env.OPD_PORT || '8080'}`,
        ws: true,
      },
    },
  },
})
