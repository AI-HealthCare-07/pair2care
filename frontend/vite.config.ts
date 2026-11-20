import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      strategies: 'injectManifest',     // REQ-NOTI-003: 웹 푸시를 직접 처리하려고 injectManifest
      srcDir: 'src',
      filename: 'sw.ts',
      registerType: 'autoUpdate',
      manifest: {
        name: 'Pair 2 Care',
        short_name: 'Pair 2 Care',      // 홈 화면 아이콘 밑에 들어갈 짧은 이름
        lang: 'ko',
        start_url: '/',
        display: 'standalone',          // 주소창 없이 앱처럼 열리게 하는 값
        theme_color: '#1a2fc4',
        background_color: '#f4f5fc',
        icons: [],                      // 아이콘은 다음에 로고로 채움
      },
    }),
  ],
  server: {
    proxy: {
      '/api': 'http://localhost',
    },
  },
})