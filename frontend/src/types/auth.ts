export interface User {
  id: number
  email: string
  username: string
  full_name?: string
  preferred_currency: string
  is_active: boolean
  created_at: string
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
}

export interface PasswordChange {
  current_password: string
  new_password: string
}
