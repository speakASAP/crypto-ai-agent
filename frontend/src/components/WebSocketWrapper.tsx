'use client'

import { WebSocketProvider } from '@/contexts/WebSocketContext'

interface WebSocketWrapperProps {
  children: React.ReactNode
}

export const WebSocketWrapper: React.FC<WebSocketWrapperProps> = ({ children }) => {
  return (
    <WebSocketProvider>
      {children}
    </WebSocketProvider>
  )
}
