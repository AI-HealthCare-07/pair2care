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
        name: 'Pair n Care',            // 서비스 이름 (팀 이름 Pair 2 Care와 다름, 11/24 결정)
        short_name: 'Pair n Care',      // 홈 화면 아이콘 밑에 들어갈 짧은 이름
        lang: 'ko',
        start_url: '/',
        display: 'standalone',          // 주소창 없이 앱처럼 열리게 하는 값
        theme_color: '#1e3bd6',
        background_color: '#f4f5fc',
        // 흰 배경 + 여백 넉넉히 → 안드로이드가 원·둥근 사각형으로 잘라도(maskable) 심볼이 안 잘림
        icons: [
          { src: '/icon-192.png', sizes: '192x192', type: 'image/png', purpose: 'any maskable' },
          { src: '/icon-512.png', sizes: '512x512', type: 'image/png', purpose: 'any maskable' },
        ],
      },
    }),
  ],
  server: {
    proxy: {
      '/api': 'http://localhost',
    },
  },
})