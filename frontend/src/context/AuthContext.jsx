// src/context/AuthContext.jsx
// Persist the access token in sessionStorage so a normal page refresh does not
// destroy the authenticated session. The token still disappears when the tab
// session ends.
import { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react'
import { fetchMe, login as loginApi, updateMe } from '../api/auth'
import { stopAllCameras } from '../api/cameras'
import { registerAuthHooks } from '../api/client'

const AuthContext = createContext(null)
const TOKEN_KEY = 'border-sentinel.access-token'

function readStoredToken() {
  try {
    return sessionStorage.getItem(TOKEN_KEY)
  } catch {
    return null
  }
}

export function AuthProvider({ children }) {
  const [token, setToken] = useState(() => readStoredToken())
  const [user, setUser] = useState(null)
  const [initializing, setInitializing] = useState(true)
  const tokenRef = useRef(token)
  const logoutInProgressRef = useRef(false)

  const logout = useCallback(async () => {
    if (logoutInProgressRef.current) return
    logoutInProgressRef.current = true
    // Stop every AI worker before clearing the token. This is especially
    // important for the default local webcam source (stream_url = null):
    // otherwise the Python worker can keep the laptop camera open after the
    // user has logged out of the web app.
    try {
      if (tokenRef.current) await stopAllCameras()
    } catch {
      // Still clear the local session if the backend is unreachable.
    } finally {
      setToken(null)
      tokenRef.current = null
      setUser(null)
      try { sessionStorage.removeItem(TOKEN_KEY) } catch {}
      logoutInProgressRef.current = false
    }
  }, [])

  useEffect(() => {
    tokenRef.current = token
    registerAuthHooks({
      getToken: () => tokenRef.current,
      onUnauthorized: () => {
        if (!logoutInProgressRef.current) logout()
      },
    })
  }, [token, logout])

  useEffect(() => {
    let cancelled = false
    const stored = readStoredToken()
    if (!stored) {
      setInitializing(false)
      return
    }

    tokenRef.current = stored
    fetchMe()
      .then((me) => { if (!cancelled) setUser(me) })
      .catch(() => { if (!cancelled) logout() })
      .finally(() => { if (!cancelled) setInitializing(false) })

    return () => { cancelled = true }
  }, [logout])

  // Shared by email/password login, email/password registration (when the
  // Supabase project auto-confirms and hands back a session immediately),
  // and the Google OAuth callback — all three end up with a Supabase access
  // token and just need it applied the same way.
  const setSession = useCallback(async (access_token) => {
    tokenRef.current = access_token
    setToken(access_token)
    try { sessionStorage.setItem(TOKEN_KEY, access_token) } catch {}
    const me = await fetchMe()
    setUser(me)
  }, [])

  const login = useCallback(async (email, password) => {
    const { access_token } = await loginApi(email, password)
    await setSession(access_token)
  }, [setSession])

  const updateProfile = useCallback(async (fullName) => {
    const updated = await updateMe(fullName)
    setUser(updated)
    return updated
  }, [])

  const value = { token, user, isAuthenticated: !!token && !!user, initializing, login, logout, setSession, updateProfile }
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider')
  return ctx
}
