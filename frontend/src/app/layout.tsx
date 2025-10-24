import { Inter } from 'next/font/google'
import './globals.css'
import { AuthProvider } from '@/components/AuthProvider'
import { WebSocketWrapper } from '@/components/WebSocketWrapper'

const inter = Inter({ subsets: ['latin'] })

export const metadata = {
  title: 'Crypto AI Agent v2.0',
  description: 'High-performance crypto portfolio management dashboard',
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
            <div className="min-h-screen bg-background">
              {children}
            </div>
          </WebSocketWrapper>
        </AuthProvider>
      </body>
    </html>
  )
}
