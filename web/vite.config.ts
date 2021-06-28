import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react-swc'

export default defineConfig({
  plugins: [react()],
  css: {
    postcss: './postcss.config.cjs',
  },
  test: {
    environment: 'jsdom',
    setupFiles: './src/test/setup.ts',
    globals: true,
    testTimeout: 15000,
    hookTimeout: 15000,
    pool: 'threads',
    maxWorkers: 1,
    coverage: {
      provider: 'v8',
      include: ['src/**/*.{ts,tsx}'],
      exclude: [
        'src/**/*.test.{ts,tsx}',
        'src/**/__tests__/**',
        'src/assets/**',
        'src/test/**',
        'src/vite-env.d.ts',
        'src/main.tsx',
        'src/constants/review-report-response.ts',
      ],
    },
  },
})
