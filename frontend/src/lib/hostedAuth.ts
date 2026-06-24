const AUTH_BASE_URL = process.env.NEXT_PUBLIC_AUTH_URL || 'https://auth.alfares.cz'
const CLIENT_ID = 'crypto-ai-agent'
const CALLBACK_PATH = '/auth/callback'
const STATE_STORAGE_KEY = 'crypto-ai-agent.hostedAuthState'
const STATE_TTL_MS = 15 * 60 * 1000

type HostedAuthMode = 'login' | 'register'

type StoredAuthState = {
  state: string
  returnPath: string
  mode: HostedAuthMode
  createdAt: number
}

export type HostedAuthSession = {
  accessToken: string
  refreshToken: string | null
  expiresAt: string | null
  authMethod: string | null
  returnPath: string
}

const safeReturnPath = (value: string | null | undefined): string => {
  if (!value || !value.startsWith('/') || value.startsWith('//') || value.startsWith(CALLBACK_PATH)) {
    return '/dashboard'
  }

  return value
}

const randomState = (): string => {
  const bytes = new Uint8Array(24)
  window.crypto.getRandomValues(bytes)
  return Array.from(bytes, (byte) => byte.toString(16).padStart(2, '0')).join('')
}

const getCallbackUrl = (): string => {
  return new URL(CALLBACK_PATH, window.location.origin).toString()
}

export const beginHostedAuth = (mode: HostedAuthMode, returnPath?: string | null): void => {
  if (typeof window === 'undefined') return

  const state = randomState()
  const storedState: StoredAuthState = {
    state,
    returnPath: safeReturnPath(returnPath),
    mode,
    createdAt: Date.now(),
  }

  window.localStorage.setItem(STATE_STORAGE_KEY, JSON.stringify(storedState))

  const authUrl = new URL(`/${mode}`, AUTH_BASE_URL)
  authUrl.searchParams.set('client_id', CLIENT_ID)
  authUrl.searchParams.set('return_url', getCallbackUrl())
  authUrl.searchParams.set('state', state)

  window.location.assign(authUrl.toString())
}

export const consumeHostedAuthCallback = (): HostedAuthSession => {
  if (typeof window === 'undefined') {
    throw new Error('Hosted Auth callback can only run in the browser')
  }

  const fragment = window.location.hash.startsWith('#')
    ? window.location.hash.slice(1)
    : window.location.hash
  const params = new URLSearchParams(fragment)
  const accessToken = params.get('access_token')
  const returnedState = params.get('state')

  window.history.replaceState(null, document.title, `${window.location.pathname}${window.location.search}`)

  if (!accessToken) {
    throw new Error('Hosted Auth did not return an access token')
  }

  const rawStoredState = window.localStorage.getItem(STATE_STORAGE_KEY)
  if (!rawStoredState) {
    throw new Error('Missing hosted Auth state. Please start sign in again.')
  }

  let storedState: StoredAuthState
  try {
    storedState = JSON.parse(rawStoredState) as StoredAuthState
  } catch {
    window.localStorage.removeItem(STATE_STORAGE_KEY)
    throw new Error('Invalid hosted Auth state. Please start sign in again.')
  }

  window.localStorage.removeItem(STATE_STORAGE_KEY)

  if (!returnedState || returnedState !== storedState.state) {
    throw new Error('Hosted Auth state validation failed. Please start sign in again.')
  }

  if (Date.now() - storedState.createdAt > STATE_TTL_MS) {
    throw new Error('Hosted Auth state expired. Please start sign in again.')
  }

  return {
    accessToken,
    refreshToken: params.get('refresh_token'),
    expiresAt: params.get('expires_at'),
    authMethod: params.get('auth_method'),
    returnPath: safeReturnPath(storedState.returnPath),
  }
}
