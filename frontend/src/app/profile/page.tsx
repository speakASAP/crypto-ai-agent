'use client'

import { useState, useEffect } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { useAuthStore } from '@/stores/authStore'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog'
import { apiClient } from '../../lib/api'

export default function ProfilePage() {
  const [profileData, setProfileData] = useState({
    email: '',
    username: '',
    fullName: '',
    preferredCurrency: 'USD',
    telegramBotToken: '',
    telegramChatId: '',
    defaultAlertPercentageAbove: '60',
    defaultAlertPercentageBelow: '20'
  })
  const [binanceData, setBinanceData] = useState({
    apiKey: '',
    apiSecret: ''
  })
  const [binanceStatus, setBinanceStatus] = useState<{
    hasCredentials: boolean
    message: string
    accountInfo?: any
  } | null>(null)
  const [binanceTestLoading, setBinanceTestLoading] = useState(false)
  const [bitfinexData, setBitfinexData] = useState({
    apiKey: '',
    apiSecret: ''
  })
  const [bitfinexStatus, setBitfinexStatus] = useState<{
    hasCredentials: boolean
    message: string
    accountInfo?: any
  } | null>(null)
  const [bitfinexTestLoading, setBitfinexTestLoading] = useState(false)
  const [passwordData, setPasswordData] = useState({
    currentPassword: '',
    newPassword: '',
    confirmPassword: ''
  })
  const [activeTab, setActiveTab] = useState<'profile' | 'password' | 'telegram' | 'binance' | 'bitfinex' | 'system'>('profile')
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [dbType, setDbType] = useState<string>('')
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)
  const [confirmationText, setConfirmationText] = useState('')
  const [deleteLoading, setDeleteLoading] = useState(false)
  const [cryptoRefreshLoading, setCryptoRefreshLoading] = useState(false)
  const [cryptoRefreshResult, setCryptoRefreshResult] = useState<{
    message: string
    count: number
    last_updated: string
  } | null>(null)
  const { user, updateProfile, changePassword, logout, deleteAccount, testTelegramConnection, loading } = useAuthStore()
  const router = useRouter()
  const searchParams = useSearchParams()

  // Set initial tab from URL parameter
  useEffect(() => {
    const tab = searchParams.get('tab')
    if (tab && ['profile', 'password', 'telegram', 'binance', 'bitfinex', 'system'].includes(tab)) {
      setActiveTab(tab as 'profile' | 'password' | 'telegram' | 'binance' | 'bitfinex' | 'system')
    }
  }, [searchParams])

  // Load backend health to determine DB type dynamically
  useEffect(() => {
    apiClient.client.get('/health')
      .then(resp => {
        if (resp?.data?.database) setDbType(resp.data.database as string)
      })
      .catch(() => {})
  }, [])

  useEffect(() => {
    if (user) {
      setProfileData({
        email: user.email,
        username: user.username,
        fullName: user.full_name || '',
        preferredCurrency: user.preferred_currency || 'USD',
        telegramBotToken: user.telegram_bot_token || '',
        telegramChatId: user.telegram_chat_id || '',
        defaultAlertPercentageAbove: (user.default_alert_percentage_above || 60).toString(),
        defaultAlertPercentageBelow: (user.default_alert_percentage_below || 20).toString()
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
        telegram_bot_token: profileData.telegramBotToken || '',
        telegram_chat_id: profileData.telegramChatId || '',
        default_alert_percentage_above: profileData.defaultAlertPercentageAbove ? parseFloat(profileData.defaultAlertPercentageAbove) : undefined,
        default_alert_percentage_below: profileData.defaultAlertPercentageBelow ? parseFloat(profileData.defaultAlertPercentageBelow) : undefined
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
        telegram_bot_token: profileData.telegramBotToken || '',
        telegram_chat_id: profileData.telegramChatId || ''
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

  const handleRefreshCryptoSymbols = async () => {
    setCryptoRefreshLoading(true)
    setError('')
    setSuccess('')
    setCryptoRefreshResult(null)
    
    try {
      const result = await apiClient.refreshCryptoSymbols()
      setCryptoRefreshResult(result)
      setSuccess(`Successfully refreshed ${result.count} cryptocurrency symbols!`)
    } catch (error: any) {
      setError(error.message || 'Failed to refresh crypto symbols')
    } finally {
      setCryptoRefreshLoading(false)
    }
  }

  const handleBinanceChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setBinanceData(prev => ({
      ...prev,
      [e.target.name]: e.target.value
    }))
  }

  const handleBinanceSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setSuccess('')
    
    try {
      const result = await apiClient.saveBinanceCredentials(binanceData.apiKey, binanceData.apiSecret)
      setSuccess('Binance credentials saved successfully!')
      setBinanceStatus({
        hasCredentials: true,
        message: result.message,
        accountInfo: result.account_info
      })
      // Clear the form
      setBinanceData({ apiKey: '', apiSecret: '' })
    } catch (error: any) {
      setError(error.detail || error.message || 'Failed to save Binance credentials')
    }
  }

  const handleTestBinance = async () => {
    setBinanceTestLoading(true)
    setError('')
    setSuccess('')
    
    try {
      const result = await apiClient.testBinanceConnection()
      if (result.success) {
        setSuccess('Binance connection test successful!')
        setBinanceStatus(prev => prev ? {
          ...prev,
          accountInfo: result.account_info
        } : null)
      } else {
        setError(result.message || 'Binance connection test failed')
      }
    } catch (error: any) {
      setError(error.message || 'Failed to test Binance connection')
    } finally {
      setBinanceTestLoading(false)
    }
  }

  const handleDeleteBinance = async () => {
    setError('')
    setSuccess('')
    
    try {
      await apiClient.deleteBinanceCredentials()
      setSuccess('Binance credentials deleted successfully!')
      setBinanceStatus({
        hasCredentials: false,
        message: 'No Binance credentials configured'
      })
    } catch (error: any) {
      setError(error.detail || error.message || 'Failed to delete Binance credentials')
    }
  }

  const handleBitfinexChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setBitfinexData(prev => ({
      ...prev,
      [e.target.name]: e.target.value
    }))
  }

  const handleBitfinexSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setSuccess('')
    
    try {
      const result = await apiClient.saveBitfinexCredentials(bitfinexData.apiKey, bitfinexData.apiSecret)
      setSuccess('Bitfinex credentials saved successfully!')
      setBitfinexStatus({
        hasCredentials: true,
        message: result.message,
        accountInfo: result.account_info
      })
      // Clear the form
      setBitfinexData({ apiKey: '', apiSecret: '' })
    } catch (error: any) {
      setError(error.detail || error.message || 'Failed to save Bitfinex credentials')
    }
  }

  const handleTestBitfinex = async () => {
    setBitfinexTestLoading(true)
    setError('')
    setSuccess('')
    
    try {
      const result = await apiClient.testBitfinexConnection()
      if (result.success) {
        setSuccess('Bitfinex connection test successful!')
        setBitfinexStatus(prev => prev ? {
          ...prev,
          accountInfo: result.account_info
        } : null)
      } else {
        setError(result.message || 'Bitfinex connection test failed')
      }
    } catch (error: any) {
      setError(error.message || 'Failed to test Bitfinex connection')
    } finally {
      setBitfinexTestLoading(false)
    }
  }

  const handleDeleteBitfinex = async () => {
    setError('')
    setSuccess('')
    
    try {
      await apiClient.deleteBitfinexCredentials()
      setSuccess('Bitfinex credentials deleted successfully!')
      setBitfinexStatus({
        hasCredentials: false,
        message: 'No Bitfinex credentials configured'
      })
    } catch (error: any) {
      setError(error.detail || error.message || 'Failed to delete Bitfinex credentials')
    }
  }

  // Load Binance status when user is authenticated
  useEffect(() => {
    if (!user) return
    
    const loadBinanceStatus = async () => {
      try {
        const result = await apiClient.getBinanceCredentials()
        setBinanceStatus({
          hasCredentials: result.has_credentials,
          message: result.message,
          accountInfo: result.account_info
        })
      } catch (error) {
        console.error('Failed to load Binance status:', error)
      }
    }
    
    loadBinanceStatus()
  }, [user])

  // Load Bitfinex status when user is authenticated
  useEffect(() => {
    if (!user) return
    
    const loadBitfinexStatus = async () => {
      try {
        const result = await apiClient.getBitfinexCredentials()
        setBitfinexStatus({
          hasCredentials: result.has_credentials,
          message: result.message,
          accountInfo: result.account_info
        })
      } catch (error) {
        console.error('Failed to load Bitfinex status:', error)
      }
    }
    
    loadBitfinexStatus()
  }, [user])

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
              <button
                onClick={() => setActiveTab('binance')}
                className={`py-2 px-1 border-b-2 font-medium text-sm ${
                  activeTab === 'binance'
                    ? 'border-blue-500 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                Binance Settings
              </button>
              <button
                onClick={() => setActiveTab('bitfinex')}
                className={`py-2 px-1 border-b-2 font-medium text-sm ${
                  activeTab === 'bitfinex'
                    ? 'border-blue-500 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                Bitfinex Settings
              </button>
              <button
                onClick={() => setActiveTab('system')}
                className={`py-2 px-1 border-b-2 font-medium text-sm ${
                  activeTab === 'system'
                    ? 'border-blue-500 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                System Settings
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

                <div className="grid grid-cols-2 gap-6 items-start">
                  <div className="space-y-2">
                    <Label htmlFor="defaultAlertPercentageBelow">Default Alert Percentage (Below)</Label>
                    <div className="flex items-center gap-2">
                      <Input
                        id="defaultAlertPercentageBelow"
                        name="defaultAlertPercentageBelow"
                        type="number"
                        min="0"
                        max="1000"
                        step="0.1"
                        value={profileData.defaultAlertPercentageBelow}
                        onChange={handleProfileChange}
                        disabled={loading}
                        className="w-24"
                      />
                      <span className="text-gray-500">%</span>
                    </div>
                    <p className="text-xs text-gray-500">
                      This percentage will be used when creating new "Below" price alerts
                    </p>
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="defaultAlertPercentageAbove">Default Alert Percentage (Above)</Label>
                    <div className="flex items-center gap-2">
                      <Input
                        id="defaultAlertPercentageAbove"
                        name="defaultAlertPercentageAbove"
                        type="number"
                        min="0"
                        max="1000"
                        step="0.1"
                        value={profileData.defaultAlertPercentageAbove}
                        onChange={handleProfileChange}
                        disabled={loading}
                        className="w-24"
                      />
                      <span className="text-gray-500">%</span>
                    </div>
                    <p className="text-xs text-gray-500">
                      This percentage will be used when creating new "Above" price alerts
                    </p>
                  </div>
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

        {activeTab === 'profile' && (
          <Card className="mt-8">
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

        {activeTab === 'binance' && (
          <Card>
            <CardHeader>
              <CardTitle>Binance API Settings</CardTitle>
              <CardDescription>
                Configure your personal Binance API credentials for portfolio import
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4 mb-6">
                <h3 className="text-sm font-medium text-yellow-800 mb-2">🔐 Security Notice</h3>
                <div className="text-sm text-yellow-700 space-y-2">
                  <p><strong>Your API credentials are encrypted and stored securely.</strong></p>
                  <ul className="list-disc list-inside space-y-1">
                    <li>API keys are encrypted using industry-standard encryption</li>
                    <li>Only you can access your credentials</li>
                    <li>Credentials are never shared or logged</li>
                    <li>You can delete your credentials at any time</li>
                  </ul>
                </div>
              </div>

              <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-6">
                <h3 className="text-sm font-medium text-blue-800 mb-2">📱 How to Get Your Binance API Credentials</h3>
                <div className="text-sm text-blue-700 space-y-2">
                  <p><strong>Step 1 - Create API Key:</strong></p>
                  <ol className="list-decimal list-inside ml-4 space-y-1">
                    <li>Log in to your Binance account</li>
                    <li>
                      Go to{' '}
                      <a
                        href="https://www.binance.com/en/my/settings/api-management"
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-blue-600 hover:text-blue-800 underline font-medium"
                      >
                        Account → API Management
                      </a>
                    </li>
                    <li>Click "Create API"</li>
                    <li>Enter a label (e.g., "Crypto AI Agent")</li>
                    <li>Complete 2FA verification</li>
                    <li>Copy your API Key and Secret Key</li>
                  </ol>
                  <p className="mt-3"><strong>Step 2 - Set Permissions:</strong></p>
                  <ol className="list-decimal list-inside ml-4 space-y-1">
                    <li>Enable "Enable Reading" permission</li>
                    <li>Disable "Enable Spot & Margin Trading" (for security)</li>
                    <li>Disable "Enable Futures" (for security)</li>
                    <li>Disable "Enable Withdrawals" (for security)</li>
                  </ol>
                  <p className="mt-3 text-xs text-blue-600">
                    <strong>Note:</strong> Only "Enable Reading" permission is required for portfolio import.
                  </p>
                </div>
              </div>

              <form onSubmit={handleBinanceSubmit} className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="binanceApiKey">Binance API Key</Label>
                  <Input
                    id="binanceApiKey"
                    name="apiKey"
                    type="password"
                    value={binanceData.apiKey}
                    onChange={handleBinanceChange}
                    placeholder="Enter your Binance API key"
                    disabled={loading}
                  />
                  <p className="text-xs text-gray-500">
                    Your Binance API key (will be encrypted and stored securely)
                  </p>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="binanceApiSecret">Binance API Secret</Label>
                  <Input
                    id="binanceApiSecret"
                    name="apiSecret"
                    type="password"
                    value={binanceData.apiSecret}
                    onChange={handleBinanceChange}
                    placeholder="Enter your Binance API secret"
                    disabled={loading}
                  />
                  <p className="text-xs text-gray-500">
                    Your Binance API secret (will be encrypted and stored securely)
                  </p>
                </div>

                <div className="flex space-x-3">
                  <Button type="submit" disabled={loading || !binanceData.apiKey || !binanceData.apiSecret}>
                    {loading ? 'Saving...' : 'Save Binance Credentials'}
                  </Button>
                  <Button 
                    type="button" 
                    variant="outline" 
                    onClick={handleTestBinance}
                    disabled={binanceTestLoading || !binanceStatus?.hasCredentials}
                  >
                    {binanceTestLoading ? 'Testing...' : 'Test Connection'}
                  </Button>
                  {binanceStatus?.hasCredentials && (
                    <Button 
                      type="button" 
                      variant="destructive" 
                      onClick={handleDeleteBinance}
                      disabled={loading}
                    >
                      Delete Credentials
                    </Button>
                  )}
                </div>

                {binanceStatus && (
                  <div className={`border rounded-lg p-4 ${
                    binanceStatus.hasCredentials 
                      ? 'bg-green-50 border-green-200' 
                      : 'bg-gray-50 border-gray-200'
                  }`}>
                    <h4 className={`text-sm font-medium mb-2 ${
                      binanceStatus.hasCredentials ? 'text-green-800' : 'text-gray-800'
                    }`}>
                      {binanceStatus.hasCredentials ? '✅ Credentials Status' : 'ℹ️ No Credentials'}
                    </h4>
                    <div className={`text-sm space-y-1 ${
                      binanceStatus.hasCredentials ? 'text-green-700' : 'text-gray-600'
                    }`}>
                      <p><strong>Status:</strong> {binanceStatus.message}</p>
                      {binanceStatus.accountInfo && (
                        <>
                          <p><strong>Account Type:</strong> {binanceStatus.accountInfo.account_type || 'Unknown'}</p>
                          <p><strong>Can Trade:</strong> {binanceStatus.accountInfo.can_trade ? 'Yes' : 'No'}</p>
                          <p><strong>Balances:</strong> {binanceStatus.accountInfo.balances_count || 0} assets</p>
                        </>
                      )}
                    </div>
                  </div>
                )}

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

        {activeTab === 'bitfinex' && (
          <Card>
            <CardHeader>
              <CardTitle>Bitfinex API Settings</CardTitle>
              <CardDescription>
                Configure your personal Bitfinex API credentials for portfolio import
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4 mb-6">
                <h3 className="text-sm font-medium text-yellow-800 mb-2">🔐 Security Notice</h3>
                <div className="text-sm text-yellow-700 space-y-2">
                  <p><strong>Your API credentials are encrypted and stored securely.</strong></p>
                  <ul className="list-disc list-inside space-y-1">
                    <li>API keys are encrypted using industry-standard encryption</li>
                    <li>Only you can access your credentials</li>
                    <li>Credentials are never shared or logged</li>
                    <li>You can delete your credentials at any time</li>
                  </ul>
                </div>
              </div>

              <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-6">
                <h3 className="text-sm font-medium text-blue-800 mb-2">📱 How to Get Your Bitfinex API Credentials</h3>
                <div className="text-sm text-blue-700 space-y-2">
                  <p><strong>Step 1 - Create API Key:</strong></p>
                  <ol className="list-decimal list-inside ml-4 space-y-1">
                    <li>Log in to your Bitfinex account</li>
                    <li>
                      Go to{' '}
                      <a
                        href="https://setting.bitfinex.com/api#my-keys"
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-blue-600 hover:text-blue-800 underline font-medium"
                      >
                        Account → API Key Management
                      </a>
                    </li>
                    <li>Click "Create New Key"</li>
                    <li>Enter a label (e.g., "Crypto AI Agent")</li>
                    <li>Complete 2FA verification</li>
                    <li>Copy your API Key and API Secret</li>
                  </ol>
                  <p className="mt-3"><strong>Step 2 - Set Permissions:</strong></p>
                  <ol className="list-decimal list-inside ml-4 space-y-1">
                    <li>Enable "Account Info" permission</li>
                    <li>Enable "Account History" permission</li>
                    <li>Enable "Wallets" permission</li>
                    <li>Disable trading and withdrawal permissions (for security)</li>
                  </ol>
                  <p className="mt-3 text-xs text-blue-600">
                    <strong>Note:</strong> Only "Account Info", "Account History", and "Wallets" permissions are required for portfolio import.
                  </p>
                </div>
              </div>

              <form onSubmit={handleBitfinexSubmit} className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="bitfinexApiKey">Bitfinex API Key</Label>
                  <Input
                    id="bitfinexApiKey"
                    name="apiKey"
                    type="password"
                    value={bitfinexData.apiKey}
                    onChange={handleBitfinexChange}
                    placeholder="Enter your Bitfinex API key"
                    disabled={loading}
                  />
                  <p className="text-xs text-gray-500">
                    Your Bitfinex API key (will be encrypted and stored securely)
                  </p>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="bitfinexApiSecret">Bitfinex API Secret</Label>
                  <Input
                    id="bitfinexApiSecret"
                    name="apiSecret"
                    type="password"
                    value={bitfinexData.apiSecret}
                    onChange={handleBitfinexChange}
                    placeholder="Enter your Bitfinex API secret"
                    disabled={loading}
                  />
                  <p className="text-xs text-gray-500">
                    Your Bitfinex API secret (will be encrypted and stored securely)
                  </p>
                </div>

                <div className="flex space-x-3">
                  <Button type="submit" disabled={loading || !bitfinexData.apiKey || !bitfinexData.apiSecret}>
                    {loading ? 'Saving...' : 'Save Bitfinex Credentials'}
                  </Button>
                  <Button 
                    type="button" 
                    variant="outline" 
                    onClick={handleTestBitfinex}
                    disabled={bitfinexTestLoading || !bitfinexStatus?.hasCredentials}
                  >
                    {bitfinexTestLoading ? 'Testing...' : 'Test Connection'}
                  </Button>
                  {bitfinexStatus?.hasCredentials && (
                    <Button 
                      type="button" 
                      variant="destructive" 
                      onClick={handleDeleteBitfinex}
                      disabled={loading}
                    >
                      Delete Credentials
                    </Button>
                  )}
                </div>

                {bitfinexStatus && (
                  <div className={`border rounded-lg p-4 ${
                    bitfinexStatus.hasCredentials 
                      ? 'bg-green-50 border-green-200' 
                      : 'bg-gray-50 border-gray-200'
                  }`}>
                    <h4 className={`text-sm font-medium mb-2 ${
                      bitfinexStatus.hasCredentials ? 'text-green-800' : 'text-gray-800'
                    }`}>
                      {bitfinexStatus.hasCredentials ? '✅ Credentials Status' : 'ℹ️ No Credentials'}
                    </h4>
                    <div className={`text-sm space-y-1 ${
                      bitfinexStatus.hasCredentials ? 'text-green-700' : 'text-gray-600'
                    }`}>
                      <p><strong>Status:</strong> {bitfinexStatus.message}</p>
                      {bitfinexStatus.accountInfo && (
                        <>
                          <p><strong>User ID:</strong> {bitfinexStatus.accountInfo.id || 'Unknown'}</p>
                          <p><strong>Email:</strong> {bitfinexStatus.accountInfo.email || 'Unknown'}</p>
                        </>
                      )}
                    </div>
                  </div>
                )}

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

        {activeTab === 'system' && (
          <Card>
            <CardHeader>
              <CardTitle>System Settings</CardTitle>
              <CardDescription>
                Manage system data and configurations
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-6">
                <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                  <h3 className="text-sm font-medium text-blue-800 mb-2">🔄 Cryptocurrency Symbols Database</h3>
                  <div className="text-sm text-blue-700 space-y-2">
                    <p>Refresh the cryptocurrency symbols database to ensure you have access to the latest cryptocurrencies for creating price alerts.</p>
                    <p className="text-xs text-blue-600">
                      <strong>Note:</strong> This will fetch the top 750 cryptocurrencies by market cap from CoinGecko API and update the local database.
                    </p>
                  </div>
                </div>

                <div className="space-y-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <h4 className="text-sm font-medium text-gray-900">Refresh Crypto Symbols</h4>
                      <p className="text-sm text-gray-500">
                        Update the database with the latest cryptocurrency symbols and names
                      </p>
                    </div>
                    <Button 
                      onClick={handleRefreshCryptoSymbols}
                      disabled={cryptoRefreshLoading}
                      className="flex items-center gap-2"
                    >
                      {cryptoRefreshLoading ? (
                        <>
                          <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
                          Refreshing...
                        </>
                      ) : (
                        <>
                          🔄 Refresh Symbols
                        </>
                      )}
                    </Button>
                  </div>

                  {cryptoRefreshResult && (
                    <div className="bg-green-50 border border-green-200 rounded-lg p-4">
                      <h4 className="text-sm font-medium text-green-800 mb-2">✅ Refresh Complete</h4>
                      <div className="text-sm text-green-700 space-y-1">
                        <p><strong>Message:</strong> {cryptoRefreshResult.message}</p>
                        <p><strong>Symbols Count:</strong> {cryptoRefreshResult.count}</p>
                        <p><strong>Last Updated:</strong> {new Date(cryptoRefreshResult.last_updated).toLocaleString()}</p>
                      </div>
                    </div>
                  )}

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

                <div className="border-t pt-4">
                  <h4 className="text-sm font-medium text-gray-900 mb-2">System Information</h4>
                  <div className="text-sm text-gray-600 space-y-1">
                    <p><strong>Database:</strong> {dbType ? (dbType === 'postgres' ? 'PostgreSQL' : 'SQLite') : '...'}</p>
                    <p><strong>API Source:</strong> CoinGecko API</p>
                    <p><strong>Update Frequency:</strong> Manual (on-demand)</p>
                    <p><strong>Symbols Limit:</strong> 750 cryptocurrencies</p>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        )}

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
