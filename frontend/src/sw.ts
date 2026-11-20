/// <reference lib="webworker" />
import { precacheAndRoute } from 'workbox-precaching'

declare const self: ServiceWorkerGlobalScope

// 빌드 때 vite-plugin-pwa가 캐시할 파일 목록을 여기에 넣어 줌
precacheAndRoute(self.__WB_MANIFEST)

// 웹 푸시(push·notificationclick)는 S4에서 여기에 추가