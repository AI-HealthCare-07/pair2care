import { createBrowserRouter } from 'react-router-dom'
import TabLayout from './layouts/TabLayout'
import StartPage from './pages/StartPage'
import SignupPage from './pages/SignupPage'
import LoginPage from './pages/LoginPage'
import OnboardingPage from './pages/OnboardingPage'
import HomePage from './pages/HomePage'
import ChallengesPage from './pages/ChallengesPage'
import PairsPage from './pages/PairsPage'
import RecordsPage from './pages/RecordsPage'
import MealsPage from './pages/MealsPage'
import MealPickPage from './pages/MealPickPage'
import MyPage from './pages/MyPage'
import NotFoundPage from './pages/NotFoundPage'


export const router = createBrowserRouter([
  { path: '/', element: <StartPage /> },
  { path: '/signup', element: <SignupPage /> },
  { path: '/login', element: <LoginPage /> },
  { path: '/onboarding', element: <OnboardingPage /> },   // S-06 가입 설문 (가입·로그인 후 설문 전이면)
  {
    element: <TabLayout />,
    children: [
      { path: '/home', element: <HomePage /> },
      { path: '/challenges', element: <ChallengesPage /> },
      { path: '/pairs', element: <PairsPage /> },
      { path: '/records', element: <RecordsPage /> },
      { path: '/records/meals', element: <MealsPage /> },
      { path: '/my', element: <MyPage /> },
    ],
  },
  { path: '/records/meals/:id', element: <MealPickPage /> },
  { path: '*', element: <NotFoundPage /> },   // 위에 없는 "모든 주소"
])