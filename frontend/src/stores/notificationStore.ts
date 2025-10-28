import { create } from 'zustand'
import { Notification, NotificationType } from '@/components/ui/notification'

interface NotificationStore {
  currentNotification: Notification | null
  showNotification: (message: string, type?: NotificationType, duration?: number) => void
  closeNotification: () => void
}

export const useNotificationStore = create<NotificationStore>((set) => ({
  currentNotification: null,
  showNotification: (message, type = 'info', duration) => {
    const id = Math.random().toString(36).substring(2, 15)
    set({
      currentNotification: {
        id,
        message,
        type,
        duration
      }
    })
  },
  closeNotification: () => {
    set({ currentNotification: null })
  }
}))

