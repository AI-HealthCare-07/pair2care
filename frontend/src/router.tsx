import { createBrowserRouter } from 'react-router-dom'
import TabLayout from './layouts/TabLayout'
import StartPage from './pages/StartPage'
import SignupPage from './pages/SignupPage'
import LoginPage from './pages/LoginPage'
import SurveyPage from './pages/SurveyPage'
import PredictionPage from './pages/PredictionPage'
import HomePage from './pages/HomePage'
import ChallengesPage from './pages/ChallengesPage'
import ChallengeDetailPage from './pages/ChallengeDetailPage'
import PairsPage from './pages/PairsPage'
import RecordsPage from './pages/RecordsPage'
import MealsPage from './pages/MealsPage'
import MealPickPage from './pages/MealPickPage'
import MyPage from './pages/MyPage'
import NotFoundPage from './pages/NotFoundPage'
import RequireAuth from './auth/RequireAuth'
import GuestOnly from './auth/GuestOnly'


export const router = createBrowserRouter([
  {
    element: <GuestOnly />,                           // 이미 로그인했으면 홈(설문 전이면 설문)으로
    children: [
      { path: '/', element: <StartPage /> },
      { path: '/signup', element: <SignupPage /> },
      { path: '/login', element: <LoginPage /> },
    ],
  },
  {
    element: <RequireAuth />,                         // 아래 children은 로그인해야 들어감
    children: [
      { path: '/onboarding', element: <SurveyPage /> },   // S-06 가입 설문 (설문 전이면 가드가 여기로 보냄)
      { path: '/prediction', element: <PredictionPage /> },   // S-09 예측 결과 (설문 저장 뒤, 하단 탭 없음)
      { element: <TabLayout />,
        children: [
          { path: '/home', element: <HomePage /> },
          { path: '/challenges', element: <ChallengesPage /> },
          { path: '/challenges/:id', element: <ChallengeDetailPage /> },
          { path: '/pairs', element: <PairsPage /> },
          { path: '/records', element: <RecordsPage /> },
          { path: '/records/meals', element: <MealsPage /> },
          { path: '/my', element: <MyPage /> },
        ],
      },
      { path: '/records/meals/:id', element: <MealPickPage /> },
    ],
  },
  { path: '*', element: <NotFoundPage /> },   // 위에 없는 "모든 주소"
])