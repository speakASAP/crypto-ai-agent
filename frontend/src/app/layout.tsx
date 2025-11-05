import { Inter } from 'next/font/google'
import './globals.css'
import { AuthProvider } from '@/components/AuthProvider'
import { WebSocketWrapper } from '@/components/WebSocketWrapper'
import { NotificationWrapper } from '@/components/NotificationWrapper'

const inter = Inter({ subsets: ['latin'] })

export const metadata = {
  title: 'Crypto AI Agent v2.0',
  description: 'High-performance crypto portfolio management dashboard',
  icons: {
    icon: [
      { url: '/favicon.ico', sizes: 'any' },
      { url: '/icon-192.png', type: 'image/png', sizes: '192x192' },
      { url: '/icon-512.png', type: 'image/png', sizes: '512x512' },
    ],
    shortcut: '/favicon.ico',
    apple: '/apple-touch-icon.png',
  },
}

// Global viewport settings for proper mobile scaling across all pages
export const viewport = {
  width: 'device-width',
  initialScale: 1,
  maximumScale: 1,
  userScalable: false,
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body className={inter.className}>
        <AuthProvider>
          <WebSocketWrapper>
            <NotificationWrapper>
              <div className="min-h-screen bg-background">
                {children}
              </div>
            </NotificationWrapper>
          </WebSocketWrapper>
        </AuthProvider>
      </body>
    </html>
  )
}
