'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { beginHostedAuth } from '@/lib/hostedAuth'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'

export default function RegisterPage() {
  const [redirecting, setRedirecting] = useState(false)
  const [nextPath, setNextPath] = useState('/dashboard')

  useEffect(() => {
    const next = new URLSearchParams(window.location.search).get('next') || '/dashboard'
    setNextPath(next)
    setRedirecting(true)
    beginHostedAuth('register', next)
  }, [])

  const handleRetry = () => {
    setRedirecting(true)
    beginHostedAuth('register', nextPath)
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-md w-full">
        <Card>
          <CardHeader className="space-y-1">
            <CardTitle className="text-2xl font-bold text-center">Create account</CardTitle>
            <CardDescription className="text-center">
              Redirecting to Alfares Auth for secure registration.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <Button type="button" className="w-full" onClick={handleRetry} disabled={redirecting}>
              {redirecting ? 'Redirecting...' : 'Continue with Alfares Auth'}
            </Button>
            <div className="text-center text-sm text-gray-600">
              Already have an account?{' '}
              <Link href={`/login?next=${encodeURIComponent(nextPath)}`} className="text-blue-600 hover:text-blue-500">
                Sign in
              </Link>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
