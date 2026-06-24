'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { consumeHostedAuthCallback } from '@/lib/hostedAuth'
import { useAuthStore } from '@/stores/authStore'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'

export default function AuthCallbackPage() {
  const router = useRouter()
  const completeHostedAuth = useAuthStore((state) => state.completeHostedAuth)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false

    const finishCallback = async () => {
      try {
        const session = consumeHostedAuthCallback()
        await completeHostedAuth(session)

        if (!cancelled) {
          router.replace(session.returnPath)
        }
      } catch (callbackError: any) {
        if (!cancelled) {
          setError(callbackError?.message || 'Hosted Auth sign in failed')
        }
      }
    }

    finishCallback()

    return () => {
      cancelled = true
    }
  }, [completeHostedAuth, router])

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-md w-full">
        <Card>
          <CardHeader className="space-y-1">
            <CardTitle className="text-2xl font-bold text-center">
              {error ? 'Sign in failed' : 'Signing you in'}
            </CardTitle>
            <CardDescription className="text-center">
              {error ? 'Start a new hosted Auth session to continue.' : 'Finishing your secure Auth handoff.'}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {error && <div className="text-red-600 text-sm text-center">{error}</div>}
            {error && (
              <Button asChild className="w-full">
                <Link href="/login">Back to sign in</Link>
              </Button>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
