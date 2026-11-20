import { Outlet } from 'react-router-dom'
import BottomNav from '../components/common/BottomNav'

export default function TabLayout() {
  return (
    <div>
      <main style={{ maxWidth: 375, margin: '0 auto', minHeight: '100vh', paddingBottom: 'calc(76px + env(safe-area-inset-bottom))' }}>
        <Outlet />   {/* 지금 주소에 맞는 자식 페이지가 여기에 그려짐 */}
      </main>
      <BottomNav />
    </div>
  )
}