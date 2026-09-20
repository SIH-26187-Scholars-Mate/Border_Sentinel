// src/pages/AuthCallback.jsx
// Landing page for Supabase's OAuth redirect (Google). supabase-js parses the
// code/hash in the URL during client initialization (detectSessionInUrl,
// on by default), and getSession() below awaits that before resolving — so
// by the time this runs we either have a real session or the flow failed.
//
// No "run once" ref here on purpose: in dev, React 18 StrictMode mounts this
// component, tears it down, then mounts it again — if a guard blocked the
// second mount from starting its own check, the first mount's result would
// get silently discarded by its own cleanup before it ever resolved, and the
// page would hang on "Finishing sign-in…" forever. getSession()/setSession()
// are safe to call twice, so we just let each mount run its own check.
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { supabase } from '../api/supabaseClient'

export default function AuthCallback() {
  const { setSession } = useAuth()
  const navigate = useNavigate()
  const [error, setError] = useState(null)

  useEffect(() => {
    let cancelled = false

    async function finish() {
      const { data, error: sessionError } = await supabase.auth.getSession()
      if (cancelled) return

      if (sessionError || !data.session) {
        setError('Google sign-in did not complete. Please try again.')
        return
      }

      try {
        await setSession(data.session.access_token)
        if (!cancelled) navigate('/dashboard', { replace: true })
      } catch {
        if (!cancelled) setError('Signed in with Google, but could not load your account.')
      }
    }

    finish()
    return () => { cancelled = true }
  }, [setSession, navigate])

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-950">
      {error ? (
        <div className="max-w-sm space-y-3 text-center">
          <p className="text-sm text-red-300">{error}</p>
          <a href="/login" className="text-sm font-medium text-sky-400 hover:text-sky-300">Back to sign in</a>
        </div>
      ) : (
        <p className="text-sm text-slate-400">Finishing sign-in…</p>
      )}
    </div>
  )
}
