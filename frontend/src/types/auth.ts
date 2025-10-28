export interface User {
  id: number
  email: string
  username: string
  full_name?: string
  preferred_currency: string
  is_active: boolean
  created_at: string
  telegram_bot_token?: string
  telegram_chat_id?: string
  default_alert_percentage_above?: number
  default_alert_percentage_below?: number
  preferred_portfolio_view?: 'cards' | 'table'
  portfolio_sort?: { by: string; dir: string }
  portfolio_filters?: Record<string, any>
}

export interface UserLogin {
  email: string
  password: string
}

export interface UserRegister {
  email: string
  username: string
  password: string
  full_name?: string
}

export interface TokenResponse {
  access_token: string
  refresh_token: string
  token_type: string
  user: User
}

export interface PasswordResetRequest {
  email: string
}

export interface PasswordResetConfirm {
  token: string
  new_password: string
}

export interface UserProfileUpdate {
  email?: string
  username?: string
  full_name?: string
  preferred_currency?: string
  telegram_bot_token?: string
  telegram_chat_id?: string
  default_alert_percentage_above?: number
  default_alert_percentage_below?: number
  preferred_portfolio_view?: 'cards' | 'table'
  portfolio_sort?: { by: string; dir: string }
  portfolio_filters?: Record<string, any>
}

export interface PasswordChange {
  current_password: string
  new_password: string
}

export interface BinanceCredentialsResponse {
  message: string
  has_credentials: boolean
  account_info?: any
}

export interface BinanceTestResponse {
  success: boolean
  message: string
  account_info?: any
}
