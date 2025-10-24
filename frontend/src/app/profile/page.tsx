'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { useAuthStore } from '@/stores/authStore'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog'

export default function ProfilePage() {
  const [profileData, setProfileData] = useState({
    email: '',
    username: '',
    fullName: '',
    preferredCurrency: 'USD',
    telegramBotToken: '',
    telegramChatId: ''
  })
  const [passwordData, setPasswordData] = useState({
    currentPassword: '',
    newPassword: '',
    confirmPassword: ''
  })
  const [activeTab, setActiveTab] = useState<'profile' | 'password' | 'telegram'>('profile')
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)
  const [confirmationText, setConfirmationText] = useState('')
  const [deleteLoading, setDeleteLoading] = useState(false)
  const { user, updateProfile, changePassword, logout, deleteAccount, testTelegramConnection, loading } = useAuthStore()
  const router = useRouter()

  useEffect(() => {
    if (user) {
      setProfileData({
        email: user.email,
        username: user.username,
        fullName: user.full_name || '',
        preferredCurrency: user.preferred_currency || 'USD',
        telegramBotToken: user.telegram_bot_token || '',
        telegramChatId: user.telegram_chat_id || ''
      })
    }
  }, [user])

  const handleProfileChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    setProfileData(prev => ({
      ...prev,
      [e.target.name]: e.target.value
    }))
  }

  const handlePasswordChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setPasswordData(prev => ({
      ...prev,
      [e.target.name]: e.target.value
    }))
  }

  const handleProfileSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setSuccess('')
    
    try {
      await updateProfile({
        email: profileData.email,
        username: profileData.username,
        full_name: profileData.fullName || undefined,
        preferred_currency: profileData.preferredCurrency,
        telegram_bot_token: profileData.telegramBotToken || undefined,
        telegram_chat_id: profileData.telegramChatId || undefined
      })
      setSuccess('Profile updated successfully')
    } catch (error: any) {
      setError(error.message || 'Profile update failed')
    }
  }

  const handlePasswordSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setSuccess('')
    
    if (passwordData.newPassword !== passwordData.confirmPassword) {
      setError('New passwords do not match')
      return
    }
    
    if (passwordData.newPassword.length < 8) {
      setError('New password must be at least 8 characters')
      return
    }
    
    try {
      await changePassword({
        current_password: passwordData.currentPassword,
        new_password: passwordData.newPassword
      })
      setSuccess('Password changed successfully')
      setPasswordData({
        currentPassword: '',
        newPassword: '',
        confirmPassword: ''
      })
    } catch (error: any) {
      setError(error.message || 'Password change failed')
    }
  }

  const handleLogout = () => {
    logout()
    router.push('/login')
  }

  const handleDeleteAccount = async () => {
    if (confirmationText !== 'DELETE') {
      setError('Please type "DELETE" to confirm account deletion')
      return
    }

    setDeleteLoading(true)
    setError('')
    
    try {
      await deleteAccount(confirmationText)
      setSuccess('Account deleted successfully')
      setShowDeleteConfirm(false)
      setConfirmationText('')
      // Redirect to login after a short delay
      setTimeout(() => {
        router.push('/login')
      }, 2000)
    } catch (error: any) {
      setError(error.message || 'Account deletion failed')
    } finally {
      setDeleteLoading(false)
    }
  }

  const handleDeleteConfirm = () => {
    setShowDeleteConfirm(true)
    setError('')
    setConfirmationText('')
  }

  const handleDeleteCancel = () => {
    setShowDeleteConfirm(false)
    setConfirmationText('')
    setError('')
  }

  const handleTestTelegram = async () => {
    setError('')
    setSuccess('')
    
    try {
      // First, save the current Telegram settings
      await updateProfile({
        email: profileData.email,
        username: profileData.username,
        full_name: profileData.fullName || undefined,
        preferred_currency: profileData.preferredCurrency,
        telegram_bot_token: profileData.telegramBotToken || undefined,
        telegram_chat_id: profileData.telegramChatId || undefined
      })
      
      // Then test the connection
      const result = await testTelegramConnection()
      if (result.success) {
        setSuccess('Telegram settings saved and test message sent successfully! Check your Telegram chat.')
      } else {
        setError(result.message)
      }
    } catch (error: any) {
      setError(error.message || 'Telegram test failed')
    }
  }

  if (!user) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <h1 className="text-2xl font-bold text-gray-900">Loading...</h1>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-50 py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-2xl mx-auto">
        <div className="mb-8">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-bold text-gray-900">Profile Settings</h1>
              <p className="mt-2 text-gray-600">Manage your account settings and preferences</p>
            </div>
            <Button
              onClick={() => router.push('/')}
              variant="outline"
              className="flex items-center gap-2"
            >
              ← Return to Dashboard
            </Button>
          </div>
        </div>

        <div className="mb-6">
          <div className="border-b border-gray-200">
            <nav className="-mb-px flex space-x-8">
              <button
                onClick={() => setActiveTab('profile')}
                className={`py-2 px-1 border-b-2 font-medium text-sm ${
                  activeTab === 'profile'
                    ? 'border-blue-500 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                Profile Information
              </button>
              <button
                onClick={() => setActiveTab('password')}
                className={`py-2 px-1 border-b-2 font-medium text-sm ${
                  activeTab === 'password'
                    ? 'border-blue-500 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                Change Password
              </button>
              <button
                onClick={() => setActiveTab('telegram')}
                className={`py-2 px-1 border-b-2 font-medium text-sm ${
                  activeTab === 'telegram'
                    ? 'border-blue-500 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                Telegram Settings
              </button>
            </nav>
          </div>
        </div>

        {activeTab === 'profile' && (
          <Card>
            <CardHeader>
              <CardTitle>Profile Information</CardTitle>
              <CardDescription>
                Update your personal information
              </CardDescription>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleProfileSubmit} className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="email">Email</Label>
                  <Input
                    id="email"
                    name="email"
                    type="email"
                    value={profileData.email}
                    onChange={handleProfileChange}
                    autoComplete="email"
                    required
                    disabled={loading}
                  />
                </div>
                
                <div className="space-y-2">
                  <Label htmlFor="username">Username</Label>
                  <Input
                    id="username"
                    name="username"
                    type="text"
                    value={profileData.username}
                    onChange={handleProfileChange}
                    autoComplete="username"
                    required
                    disabled={loading}
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="fullName">Full Name</Label>
                  <Input
                    id="fullName"
                    name="fullName"
                    type="text"
                    value={profileData.fullName}
                    onChange={handleProfileChange}
                    autoComplete="name"
                    disabled={loading}
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="preferredCurrency">Preferred Currency</Label>
                  <select
                    id="preferredCurrency"
                    name="preferredCurrency"
                    value={profileData.preferredCurrency}
                    onChange={handleProfileChange}
                    disabled={loading}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:opacity-50"
                  >
                    <option value="USD">USD - US Dollar</option>
                    <option value="EUR">EUR - Euro</option>
                    <option value="CZK">CZK - Czech Koruna</option>
                  </select>
                </div>

                {error && (
                  <div className="text-red-600 text-sm">
                    {error}
                  </div>
                )}

                {success && (
                  <div className="text-green-600 text-sm">
                    {success}
                  </div>
                )}

                <Button type="submit" disabled={loading}>
                  {loading ? 'Updating...' : 'Update Profile'}
                </Button>
              </form>
            </CardContent>
          </Card>
        )}

        {activeTab === 'password' && (
          <Card>
            <CardHeader>
              <CardTitle>Change Password</CardTitle>
              <CardDescription>
                Update your password to keep your account secure
              </CardDescription>
            </CardHeader>
            <CardContent>
              <form onSubmit={handlePasswordSubmit} className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="currentPassword">Current Password</Label>
                  <Input
                    id="currentPassword"
                    name="currentPassword"
                    type="password"
                    value={passwordData.currentPassword}
                    onChange={handlePasswordChange}
                    autoComplete="current-password"
                    required
                    disabled={loading}
                  />
                </div>
                
                <div className="space-y-2">
                  <Label htmlFor="newPassword">New Password</Label>
                  <Input
                    id="newPassword"
                    name="newPassword"
                    type="password"
                    value={passwordData.newPassword}
                    onChange={handlePasswordChange}
                    autoComplete="new-password"
                    required
                    disabled={loading}
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="confirmPassword">Confirm New Password</Label>
                  <Input
                    id="confirmPassword"
                    name="confirmPassword"
                    type="password"
                    value={passwordData.confirmPassword}
                    onChange={handlePasswordChange}
                    autoComplete="new-password"
                    required
                    disabled={loading}
                  />
                </div>

                {error && (
                  <div className="text-red-600 text-sm">
                    {error}
                  </div>
                )}

                {success && (
                  <div className="text-green-600 text-sm">
                    {success}
                  </div>
                )}

                <Button type="submit" disabled={loading}>
                  {loading ? 'Changing...' : 'Change Password'}
                </Button>
              </form>
            </CardContent>
          </Card>
        )}

        {activeTab === 'telegram' && (
          <Card>
            <CardHeader>
              <CardTitle>Telegram Settings</CardTitle>
              <CardDescription>
                Configure your personal Telegram bot for price alert notifications
              </CardDescription>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleProfileSubmit} className="space-y-4">
                <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-6">
                  <h3 className="text-sm font-medium text-blue-800 mb-2">📱 How to Get Your Telegram Credentials</h3>
                  <div className="text-sm text-blue-700 space-y-2">
                    <p><strong>Step 1 - Create a Bot:</strong></p>
                    <ol className="list-decimal list-inside ml-4 space-y-1">
                      <li>Open Telegram and search for <code className="bg-blue-100 px-1 rounded">@BotFather</code></li>
                      <li>Start a chat with @BotFather</li>
                      <li>Send <code className="bg-blue-100 px-1 rounded">/newbot</code> command</li>
                      <li>Follow the instructions to create your bot</li>
                      <li>Copy the bot token (format: 123456789:ABCdefGHIjklMNOpqrsTUVwxyz)</li>
                    </ol>
                    <p className="mt-3"><strong>Step 2 - Get Your Chat ID:</strong></p>
                    <ol className="list-decimal list-inside ml-4 space-y-1">
                      <li>Start a chat with your bot (search for the bot name you created)</li>
                      <li>Send any message to the bot</li>
                      <li>Visit: <code className="bg-blue-100 px-1 rounded">https://api.telegram.org/bot&lt;YOUR_BOT_TOKEN&gt;/getUpdates</code></li>
                      <li>Find your chat ID in the response (look for &quot;chat&quot;:&quot;id&quot;:123456789)</li>
                      <li>Copy the chat ID number</li>
                    </ol>
                    <p className="mt-3 text-xs text-blue-600">
                      <strong>Note:</strong> These settings are optional. If not configured, the system will use global settings for notifications.
                    </p>
                  </div>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="telegramBotToken">Telegram Bot Token</Label>
                  <Input
                    id="telegramBotToken"
                    name="telegramBotToken"
                    type="text"
                    value={profileData.telegramBotToken}
                    onChange={handleProfileChange}
                    placeholder="123456789:ABCdefGHIjklMNOpqrsTUVwxyz"
                    disabled={loading}
                  />
                  <p className="text-xs text-gray-500">
                    Your personal Telegram bot token from @BotFather
                  </p>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="telegramChatId">Telegram Chat ID</Label>
                  <Input
                    id="telegramChatId"
                    name="telegramChatId"
                    type="text"
                    value={profileData.telegramChatId}
                    onChange={handleProfileChange}
                    placeholder="123456789"
                    disabled={loading}
                  />
                  <p className="text-xs text-gray-500">
                    Your personal chat ID with the bot
                  </p>
                </div>

                <div className="flex space-x-3">
                  <Button type="submit" disabled={loading}>
                    {loading ? 'Saving...' : 'Save Telegram Settings'}
                  </Button>
                  <Button 
                    type="button" 
                    variant="outline" 
                    onClick={handleTestTelegram}
                    disabled={loading || (!profileData.telegramBotToken || !profileData.telegramChatId)}
                  >
                    {loading ? 'Saving & Testing...' : 'Save & Test Connection'}
                  </Button>
                </div>

                {error && (
                  <div className="text-red-600 text-sm">
                    {error}
                  </div>
                )}

                {success && (
                  <div className="text-green-600 text-sm">
                    {success}
                  </div>
                )}
              </form>
            </CardContent>
          </Card>
        )}

        <div className="mt-8">
          <Card>
            <CardHeader>
              <CardTitle className="text-red-600">Danger Zone</CardTitle>
              <CardDescription>
                Irreversible and destructive actions
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                <div className="text-sm text-gray-600">
                  <p className="mb-2">This action will permanently delete your account and all associated data including:</p>
                  <ul className="list-disc list-inside space-y-1 text-xs text-gray-500">
                    <li>Portfolio items and transaction history</li>
                    <li>Price alerts and notification settings</li>
                    <li>Tracked symbols and preferences</li>
                    <li>All personal information and settings</li>
                  </ul>
                  <p className="mt-2 font-medium text-red-600">This action cannot be undone.</p>
                </div>
                <Button 
                  variant="destructive" 
                  onClick={handleDeleteConfirm}
                  disabled={loading || deleteLoading}
                >
                  Remove my account
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>

      {/* Account Deletion Confirmation Dialog */}
      <Dialog open={showDeleteConfirm} onOpenChange={handleDeleteCancel}>
        <DialogContent className="sm:max-w-[425px]">
          <DialogHeader>
            <DialogTitle className="text-red-600">Delete Account</DialogTitle>
          </DialogHeader>
          <div className="py-4">
            <div className="space-y-4">
              <div className="bg-red-50 border border-red-200 rounded-lg p-4">
                <div className="flex items-start">
                  <div className="flex-shrink-0">
                    <svg className="h-5 w-5 text-red-400" viewBox="0 0 20 20" fill="currentColor">
                      <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
                    </svg>
                  </div>
                  <div className="ml-3">
                    <h3 className="text-sm font-medium text-red-800">
                      Are you absolutely sure?
                    </h3>
                    <div className="mt-2 text-sm text-red-700">
                      <p>This action will permanently delete your account and all associated data. This cannot be undone.</p>
                    </div>
                  </div>
                </div>
              </div>
              
              <div className="space-y-2">
                <Label htmlFor="confirmation-text">
                  Type <span className="font-mono font-bold text-red-600">DELETE</span> to confirm:
                </Label>
                <Input
                  id="confirmation-text"
                  type="text"
                  value={confirmationText}
                  onChange={(e) => setConfirmationText(e.target.value)}
                  placeholder="DELETE"
                  className="font-mono"
                  disabled={deleteLoading}
                />
              </div>

              {error && (
                <div className="text-red-600 text-sm">
                  {error}
                </div>
              )}

              {success && (
                <div className="text-green-600 text-sm">
                  {success}
                </div>
              )}
            </div>
          </div>
          
          <DialogFooter>
            <Button 
              type="button" 
              variant="outline" 
              onClick={handleDeleteCancel}
              disabled={deleteLoading}
            >
              Cancel
            </Button>
            <Button 
              type="button"
              variant="destructive" 
              onClick={handleDeleteAccount}
              disabled={confirmationText !== 'DELETE' || deleteLoading}
            >
              {deleteLoading ? 'Deleting...' : 'Delete Account'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
