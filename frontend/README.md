# frontend — Pair 2 Care 웹 (React + Vite + PWA)

모바일 우선 PWA. 화면 폭 375px 기준, PC에서는 가운데 정렬로 같은 화면을 보여 줌 (`docs/wireframe.md` 1장).

## 실행
```bash
cd frontend
npm install
npm run dev
```
- 브라우저에서 `http://localhost:5173/home` (하단 탭 화면). `/`는 시작 화면이라 탭이 없음
- `/api`로 시작하는 요청은 `vite.config.ts`의 프록시로 `http://localhost`(nginx → fastapi)에 넘어감 → 레포 루트에서 `docker compose up -d`가 켜져 있어야 함
- 패키지는 꼭 `frontend` 폴더 안에서 설치함 (루트에서 `npm install` 하면 루트에 `package.json`이 생김)

## 명령
| 명령 | 하는 일 |
|---|---|
| `npm run dev` | 개발 서버 (5173, 저장하면 바로 반영) |
| `npm run build` | 타입 검사 + 배포용 빌드 (`dist/`) |
| `npm run preview` | 빌드 결과 미리보기 (4173). PWA·서비스 워커는 여기서 확인 |
| `npm run lint` | ESLint |

## 구조
```
src/
├── main.tsx            # 라우터 연결
├── router.tsx          # 주소 ↔ 화면 (탭 화면은 TabLayout 안)
├── layouts/TabLayout.tsx
├── pages/              # 화면 하나에 파일 하나 (S번호는 wireframe.md 대응표)
├── components/         # 공통 컴포넌트 (BottomNav, NavIcons …)
├── api/client.ts       # apiFetch: /api/v1 + Bearer 토큰, 401이면 refresh 후 1번 재시도
├── sw.ts               # 서비스 워커 (지금은 캐시만, 웹 푸시는 S4)
└── index.css           # 색 변수 (Figma 기준)
```

## 규칙
- 색은 `index.css`의 변수(`--color-primary` 등)만 씀. 값을 직접 쓰지 않음
- access 토큰은 메모리에만 둠 (localStorage 금지). refresh 토큰은 httpOnly 쿠키라 JS에서 안 만짐
- 백엔드 응답 키는 snake_case (`access_token`)
- API 경로·필드는 `docs/api.md` 기준
- 화면은 Figma 와이어프레임과 S번호를 맞춤
