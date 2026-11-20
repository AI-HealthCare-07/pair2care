import { Outlet } from 'react-router-dom'
import BottomNav from '../components/BottomNav'

export default function TabLayout() {
  return (
    <div>
      <main style={{ maxWidth: 375, margin: '0 auto', minHeight: '100vh', paddingBottom: 76 }}>
        <Outlet />   {/* 지금 주소에 맞는 자식 페이지가 여기에 그려짐 */}
      </main>
      <BottomNav />
    </div>
  )
}