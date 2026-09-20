// src/pages/Login.jsx
import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import GoogleSignInButton from '../components/GoogleSignInButton'
import { useAuth } from '../context/AuthContext'
import { ApiError } from '../api/client'

export default function Login() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e) {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      await login(email, password)
      navigate('/dashboard', { replace: true })
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : 'Could not reach the server')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex min-h-screen bg-slate-950">
      <div
        className="relative hidden flex-1 flex-col justify-between overflow-hidden p-10 lg:flex"
        style={{ background: 'linear-gradient(165deg, #10151f 0%, #1a2130 45%, #47230f 100%)' }}
      >
        <div className="absolute inset-0 opacity-[0.06]" style={{ backgroundImage: 'radial-gradient(circle at 1px 1px, #fff 1px, transparent 0)', backgroundSize: '28px 28px' }} />
        <div className="relative flex items-center gap-2.5">
          <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-slate-800/80">
            <svg viewBox="0 0 24 24" className="h-4.5 w-4.5" fill="none"><path d="M12 3 L20 6.5 V12 C20 17 16.5 20 12 21.5 C7.5 20 4 17 4 12 V6.5 Z" stroke="#e2a164" strokeWidth="1.4" strokeLinejoin="round" /></svg>
          </span>
          <span className="text-sm font-semibold text-slate-100">Border Sentinel</span>
        </div>
        <div className="relative max-w-md">
          <h1 className="text-3xl font-semibold leading-tight text-slate-100">
            Every camera watching. One console to see what matters.
          </h1>
          <p className="mt-4 text-sm leading-relaxed text-slate-400">
            Live feeds, AI-flagged intrusions, and vehicle detections land here in real time,
            so your team reacts to the one event that needs eyes — not a wall of footage.
          </p>
        </div>
        <p className="relative text-xs text-slate-500">Prototype build — for demonstration, not live deployment.</p>
      </div>

      <div className="flex flex-1 items-center justify-center px-6 py-12">
        <form onSubmit={handleSubmit} className="w-full max-w-sm space-y-5">
          <div className="mb-2 flex items-center gap-2.5 lg:hidden">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-slate-800">
              <svg viewBox="0 0 24 24" className="h-4.5 w-4.5" fill="none"><path d="M12 3 L20 6.5 V12 C20 17 16.5 20 12 21.5 C7.5 20 4 17 4 12 V6.5 Z" stroke="#e2a164" strokeWidth="1.4" strokeLinejoin="round" /></svg>
            </span>
            <span className="text-sm font-semibold text-slate-100">Border Sentinel</span>
          </div>

          <div>
            <h2 className="text-xl font-semibold text-slate-100">Sign in</h2>
            <p className="mt-1 text-sm text-slate-500">Use the operator account for this deployment.</p>
          </div>

          {error && (
            <div className="rounded-lg border border-red-900 bg-red-950/50 px-3.5 py-2.5 text-sm text-red-300">
              {error}
            </div>
          )}

          <GoogleSignInButton onError={setError} />

          <div className="flex items-center gap-3">
            <div className="h-px flex-1 bg-slate-800" />
            <span className="text-xs text-slate-500">or</span>
            <div className="h-px flex-1 bg-slate-800" />
          </div>

          <div className="space-y-1.5">
            <label className="text-xs font-medium text-slate-400" htmlFor="email">Email</label>
            <input
              id="email"
              type="email"
              required
              autoFocus
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full rounded-lg border border-slate-700 bg-slate-900 px-3.5 py-2.5 text-sm text-slate-100 outline-none transition focus:border-sky-500 focus:ring-2 focus:ring-sky-500/20"
            />
          </div>

          <div className="space-y-1.5">
            <label className="text-xs font-medium text-slate-400" htmlFor="password">Password</label>
            <input
              id="password"
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full rounded-lg border border-slate-700 bg-slate-900 px-3.5 py-2.5 text-sm text-slate-100 outline-none transition focus:border-sky-500 focus:ring-2 focus:ring-sky-500/20"
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full rounded-lg bg-sky-600 py-2.5 text-sm font-medium text-white shadow-lg shadow-sky-950/40 transition hover:bg-sky-500 disabled:opacity-50"
          >
            {loading ? 'Signing in…' : 'Sign in'}
          </button>

          <p className="text-center text-sm text-slate-500">
            Don't have an account?{' '}
            <Link to="/register" className="font-medium text-sky-400 hover:text-sky-300">Create one</Link>
          </p>
        </form>
      </div>
    </div>
  )
}
