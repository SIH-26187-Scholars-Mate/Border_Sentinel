// src/pages/Settings.jsx
import { useState } from 'react'
import { useAuth } from '../context/AuthContext'
import { useTheme } from '../context/ThemeContext'
import { ApiError } from '../api/client'

export default function Settings() {
  const { user, logout, updateProfile } = useAuth()

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-100">Settings</h1>
        <p className="mt-1 text-sm text-slate-400">Your account and how the console looks.</p>
      </div>

      <ProfileCard user={user} onSave={updateProfile} />
      <AppearanceCard />
      <SessionCard onLogout={logout} />
    </div>
  )
}

// ── Profile ──────────────────────────────────────────────────────────────────

function ProfileCard({ user, onSave }) {
  const [editing, setEditing] = useState(false)
  const [name, setName] = useState(user?.full_name || '')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)

  const displayName = user?.full_name?.trim() || user?.email?.split('@')[0] || 'Operator'

  function startEditing() {
    setName(user?.full_name || '')
    setError(null)
    setEditing(true)
  }

  async function handleSave() {
    const trimmed = name.trim()
    if (!trimmed) {
      setError('Name cannot be empty')
      return
    }
    setSaving(true)
    setError(null)
    try {
      await onSave(trimmed)
      setEditing(false)
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : 'Could not save your name. Try again.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <section className="overflow-hidden rounded-xl border border-slate-800 bg-slate-900/60">
      <div className="border-b border-slate-800 px-5 py-4">
        <h2 className="text-sm font-semibold text-slate-200">Profile</h2>
        <p className="mt-0.5 text-xs text-slate-500">Displayed in the sidebar and on shared alerts.</p>
      </div>

      <div className="flex items-start gap-4 px-5 py-5">
        <Avatar name={displayName} />

        <div className="min-w-0 flex-1 space-y-3">
          {editing ? (
            <div className="space-y-2">
              <label className="block text-xs font-medium text-slate-400">Display name</label>
              <input
                autoFocus
                value={name}
                onChange={(e) => setName(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleSave()}
                maxLength={60}
                className="w-full rounded-lg border border-slate-700 bg-slate-950/60 px-3 py-2 text-sm text-slate-100 outline-none focus:border-sky-600"
                placeholder="Your name"
              />
              {error && <p className="text-xs text-red-400">{error}</p>}
              <div className="flex gap-2 pt-1">
                <button
                  onClick={handleSave}
                  disabled={saving}
                  className="rounded-lg bg-sky-600 px-3.5 py-1.5 text-xs font-medium text-slate-100 transition hover:bg-sky-500 disabled:opacity-60"
                >
                  {saving ? 'Saving…' : 'Save'}
                </button>
                <button
                  onClick={() => setEditing(false)}
                  disabled={saving}
                  className="rounded-lg border border-slate-700 px-3.5 py-1.5 text-xs font-medium text-slate-300 transition hover:bg-slate-800"
                >
                  Cancel
                </button>
              </div>
            </div>
          ) : (
            <>
              <div className="flex items-center gap-2">
                <span className="text-base font-medium text-slate-100">{displayName}</span>
                <button
                  onClick={startEditing}
                  className="text-slate-500 transition hover:text-sky-400"
                  aria-label="Edit name"
                  title="Edit name"
                >
                  <IconPencil className="h-3.5 w-3.5" />
                </button>
              </div>
              <p className="text-sm text-slate-500">{user?.email || '—'}</p>
              <span className="inline-flex items-center rounded-full border border-slate-700 px-2.5 py-0.5 text-[11px] capitalize text-slate-400">
                {user?.role || 'authenticated'}
              </span>
            </>
          )}
        </div>
      </div>
    </section>
  )
}

function Avatar({ name }) {
  const initials = (name || '?')
    .trim()
    .split(/\s+/)
    .slice(0, 2)
    .map((w) => w[0]?.toUpperCase())
    .join('') || '?'

  return (
    <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-sky-600 to-sky-800 text-lg font-semibold text-slate-100">
      {initials}
    </div>
  )
}

// ── Appearance ───────────────────────────────────────────────────────────────

function AppearanceCard() {
  const { theme, setTheme } = useTheme()

  return (
    <section className="overflow-hidden rounded-xl border border-slate-800 bg-slate-900/60">
      <div className="border-b border-slate-800 px-5 py-4">
        <h2 className="text-sm font-semibold text-slate-200">Appearance</h2>
        <p className="mt-0.5 text-xs text-slate-500">Applies to every screen in the console.</p>
      </div>
      <div className="flex items-center justify-between px-5 py-4">
        <div className="flex items-center gap-3 text-sm text-slate-300">
          {theme === 'dark' ? <IconMoon className="h-4 w-4 text-sky-400" /> : <IconSun className="h-4 w-4 text-sky-400" />}
          Theme
        </div>
        <div className="flex rounded-lg border border-slate-700 p-0.5">
          <ThemeSegment active={theme === 'dark'} onClick={() => setTheme('dark')} icon={<IconMoon className="h-3.5 w-3.5" />} label="Dark" />
          <ThemeSegment active={theme === 'light'} onClick={() => setTheme('light')} icon={<IconSun className="h-3.5 w-3.5" />} label="Light" />
        </div>
      </div>
    </section>
  )
}

function ThemeSegment({ active, onClick, icon, label }) {
  return (
    <button
      onClick={onClick}
      className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition ${
        active ? 'bg-sky-600 text-slate-100' : 'text-slate-400 hover:text-slate-200'
      }`}
    >
      {icon}
      {label}
    </button>
  )
}

// ── Session ──────────────────────────────────────────────────────────────────

function SessionCard({ onLogout }) {
  return (
    <section className="overflow-hidden rounded-xl border border-slate-800 bg-slate-900/60">
      <div className="flex items-center justify-between px-5 py-4">
        <div>
          <h2 className="text-sm font-semibold text-slate-200">Session</h2>
          <p className="mt-0.5 text-xs text-slate-500">Sign out of this device.</p>
        </div>
        <button
          onClick={onLogout}
          className="rounded-lg border border-red-900/70 px-3.5 py-1.5 text-xs font-medium text-red-300 transition hover:bg-red-950/40"
        >
          Log out
        </button>
      </div>
    </section>
  )
}

// ── Icons ────────────────────────────────────────────────────────────────────

function IconPencil({ className }) {
  return <svg viewBox="0 0 24 24" fill="none" className={className}><path d="M15.7 4.3a1.5 1.5 0 0 1 2.1 0l1.9 1.9a1.5 1.5 0 0 1 0 2.1L8.5 19.5 4 20.5l1-4.5Z" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" /></svg>
}
function IconMoon({ className }) {
  return <svg viewBox="0 0 24 24" fill="none" className={className}><path d="M20 14.5A8.5 8.5 0 1 1 9.5 4a7 7 0 0 0 10.5 10.5Z" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" /></svg>
}
function IconSun({ className }) {
  return <svg viewBox="0 0 24 24" fill="none" className={className}><circle cx="12" cy="12" r="4" stroke="currentColor" strokeWidth="1.6" /><path d="M12 2.5v2.2M12 19.3v2.2M4.2 4.2l1.6 1.6M18.2 18.2l1.6 1.6M2.5 12h2.2M19.3 12h2.2M4.2 19.8l1.6-1.6M18.2 5.8l1.6-1.6" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" /></svg>
}
