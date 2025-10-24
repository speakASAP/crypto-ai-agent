'use client'

import { useEffect, useState } from 'react'
import { useAuthStore } from '@/stores/authStore'

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const { setHydrated, isHydrated } = useAuthStore()
  const [mounted, setMounted] = useState(false)

  useEffect(() => {
    // Set mounted to true after component mounts
    setMounted(true)
    
    // Set hydrated state after a brief delay to allow store rehydration
    const timer = setTimeout(() => {
      setHydrated(true)
    }, 100)
    
    return () => clearTimeout(timer)
  }, [setHydrated])

  // Don't render children until both mounted and hydrated to prevent hydration mismatches
  if (!mounted || !isHydrated) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto"></div>
          <p className="mt-2 text-gray-600">Loading...</p>
        </div>
      </div>
    )
  }

  return <>{children}</>
}
