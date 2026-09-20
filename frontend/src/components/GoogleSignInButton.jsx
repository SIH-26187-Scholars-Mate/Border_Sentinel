// src/components/GoogleSignInButton.jsx
// Shared "Continue with Google" button used on both Login and Register.
// Kicks off Supabase's OAuth redirect flow — the browser leaves the app and
// comes back at /auth/callback once Google has authenticated the user.
import { useState } from 'react'
import { supabase } from '../api/supabaseClient'

export default function GoogleSignInButton({ label = 'Continue with Google', onError }) {
  const [loading, setLoading] = useState(false)

  async function handleClick() {
    onError?.(null)
    setLoading(true)
    try {
      const { error } = await supabase.auth.signInWithOAuth({
        provider: 'google',
        options: { redirectTo: `${window.location.origin}/auth/callback` },
      })
      if (error) throw error
      // On success the browser navigates away to Google immediately, so
      // there is nothing further to do here. loading intentionally stays
      // true until the redirect happens.
    } catch (err) {
      onError?.(err.message || 'Could not start Google sign-in')
      setLoading(false)
    }
  }

  return (
    <button
      type="button"
      onClick={handleClick}
      disabled={loading}
      className="flex w-full items-center justify-center gap-2.5 rounded-lg border border-slate-700 bg-slate-900 py-2.5 text-sm font-medium text-slate-200 transition hover:bg-slate-800 disabled:opacity-50"
    >
      <svg viewBox="0 0 24 24" className="h-4.5 w-4.5" aria-hidden="true">
        <path fill="#4285F4" d="M23.52 12.27c0-.85-.08-1.67-.22-2.45H12v4.64h6.47c-.28 1.5-1.13 2.77-2.4 3.62v3h3.87c2.27-2.09 3.58-5.17 3.58-8.81Z" />
        <path fill="#34A853" d="M12 24c3.24 0 5.96-1.07 7.94-2.92l-3.87-3c-1.08.72-2.45 1.15-4.07 1.15-3.13 0-5.78-2.11-6.73-4.96H1.28v3.11C3.25 21.3 7.31 24 12 24Z" />
        <path fill="#FBBC05" d="M5.27 14.27a7.2 7.2 0 0 1 0-4.54v-3.1H1.28a12 12 0 0 0 0 10.75l3.99-3.11Z" />
        <path fill="#EA4335" d="M12 4.77c1.76 0 3.35.6 4.6 1.79l3.43-3.43C17.95 1.19 15.24 0 12 0 7.31 0 3.25 2.7 1.28 6.63l3.99 3.1C6.22 6.88 8.87 4.77 12 4.77Z" />
      </svg>
      {loading ? 'Redirecting…' : label}
    </button>
  )
}
