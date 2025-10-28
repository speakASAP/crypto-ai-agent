'use client'

import { NotificationDialog } from '@/components/ui/notification'
import { useNotificationStore } from '@/stores/notificationStore'

export function NotificationWrapper({ children }: { children: React.ReactNode }) {
  const currentNotification = useNotificationStore((state) => state.currentNotification)
  const closeNotification = useNotificationStore((state) => state.closeNotification)

  return (
    <>
      {children}
      <NotificationDialog 
        notification={currentNotification} 
        onClose={closeNotification} 
      />
    </>
  )
}

