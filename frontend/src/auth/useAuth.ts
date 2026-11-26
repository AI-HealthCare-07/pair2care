import { useContext } from 'react'
import { AuthContext } from './authContext'

export function useAuth() {
  const value = useContext(AuthContext)
  if (!value) throw new Error('AuthProvider 안에서만 쓸 수 있어요')   // main.tsx에 Provider 빼먹으면 바로 알게
  return value
}