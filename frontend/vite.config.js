import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/chat':           'http://localhost:8000',
      '/confirm-email':  'http://localhost:8000',
      '/health':         'http://localhost:8000',
      '/auth':           'http://localhost:8000',
      '/agent-card':     'http://localhost:8000',
      '/briefings':      'http://localhost:8000',
      '/users':          'http://localhost:8000',
      '/admin':             'http://localhost:8000',
      '/briefing':          'http://localhost:8000',
      '/proposed-actions':  'http://localhost:8000',
      '/nudges':            'http://localhost:8000',
    },
  },
})
