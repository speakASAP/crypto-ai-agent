'use client'

import { useEffect } from 'react'
import { useAuthStore } from '@/stores/authStore'

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const { setHydrated } = useAuthStore()

  useEffect(() => {
    setHydrated(true)
  }, [setHydrated])

  return <>{children}</>
}
