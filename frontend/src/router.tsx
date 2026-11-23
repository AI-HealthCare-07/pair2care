import { createBrowserRouter } from 'react-router-dom'
import TabLayout from './layouts/TabLayout'
import StartPage from './pages/StartPage'
import SignupPage from './pages/SignupPage'
import LoginPage from './pages/LoginPage'
import HomePage from './pages/HomePage'
import ChallengesPage from './pages/ChallengesPage'
import PairsPage from './pages/PairsPage'
import RecordsPage from './pages/RecordsPage'
import MyPage from './pages/MyPage'
import NotFoundPage from './pages/NotFoundPage'
import MealsPage from './pages/MealsPage'
import MealPickPage from './pages/MealPickPage'

// TabLayout children 안, '/records' 아래에 추가
{ path: '/records/meals', element: <MealsPage /> },

// TabLayout 밖, '*' 바로 위에 추가
{ path: '/records/meals/:id', element: <MealPickPage /> },

export const router = createBrowserRouter([
  { path: '/', element: <StartPage /> },
  { path: '/signup', element: <SignupPage /> },
  { path: '/login', element: <LoginPage /> },
  {
    element: <TabLayout />,
    children: [
      { path: '/home', element: <HomePage /> },
      { path: '/challenges', element: <ChallengesPage /> },
      { path: '/pairs', element: <PairsPage /> },
      { path: '/records', element: <RecordsPage /> },
      { path: '/my', element: <MyPage /> },
    ],
  },
  { path: '*', element: <NotFoundPage /> },   // 위에 없는 "모든 주소"
])