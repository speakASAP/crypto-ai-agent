import { NextResponse } from 'next/server'
import type { NextRequest } from 'next/server'

export function middleware(request: NextRequest) {
  const authStorage = request.cookies.get('auth-storage')?.value
  let isAuthenticated = false
  
  if (authStorage) {
    try {
      const parsed = JSON.parse(authStorage)
      isAuthenticated = parsed.state?.isAuthenticated || false
    } catch (e) {
      // Invalid auth storage
    }
  }

  const { pathname } = request.nextUrl

  // Define protected routes
  const protectedRoutes = ['/', '/profile']
  const authRoutes = ['/login', '/register', '/forgot-password', '/reset-password']

  // Redirect unauthenticated users from protected routes to login
  if (protectedRoutes.includes(pathname) && !isAuthenticated) {
    const url = request.nextUrl.clone()
    url.pathname = '/login'
    return NextResponse.redirect(url)
  }

  // Redirect authenticated users from auth routes to home
  if (authRoutes.includes(pathname) && isAuthenticated) {
    const url = request.nextUrl.clone()
    url.pathname = '/'
    return NextResponse.redirect(url)
  }

  return NextResponse.next()
}

export const config = {
  matcher: ['/', '/login', '/register', '/profile', '/forgot-password', '/reset-password'],
}
