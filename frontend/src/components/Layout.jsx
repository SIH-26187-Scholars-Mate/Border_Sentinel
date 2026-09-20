// src/components/Layout.jsx
import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

const NAV_ITEMS = [
  { to: '/dashboard', label: 'Dashboard', icon: IconGrid },
  { to: '/cameras', label: 'Cameras', icon: IconCamera },
  { to: '/alerts', label: 'Alerts', icon: IconBell },
  { to: '/analyze', label: 'Analyze', icon: IconUpload },
]

export default function Layout() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  async function handleLogout() {
    await logout()
    navigate('/login', { replace: true })
  }

  const name = user?.full_name?.trim() || user?.email?.split('@')[0] || 'operator'
  const greeting = timeGreeting(new Date())

  return (
    <div className="flex min-h-screen bg-slate-950 text-slate-200">
      <aside className="flex w-60 shrink-0 flex-col border-r border-slate-800 bg-slate-900/60">
        <div className="flex items-center gap-2.5 px-5 py-5">
          <WatchMark />
          <div>
            <div className="text-sm font-semibold text-slate-100">Border Sentinel</div>
            <div className="text-[11px] text-slate-500">Operations console</div>
          </div>
        </div>

        <nav className="mt-2 flex-1 space-y-0.5 px-3">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                `group flex items-center gap-3 rounded-lg border-l-2 px-3 py-2.5 text-sm transition ${
                  isActive
                    ? 'border-sky-500 bg-sky-500/10 text-sky-200'
                    : 'border-transparent text-slate-400 hover:border-slate-700 hover:bg-slate-800/60 hover:text-slate-200'
                }`
              }
            >
              {({ isActive }) => (
                <>
                  <item.icon className={`h-4 w-4 shrink-0 ${isActive ? 'text-sky-400' : 'text-slate-500 group-hover:text-slate-300'}`} />
                  {item.label}
                </>
              )}
            </NavLink>
          ))}
        </nav>

        <NavLink
          to="/settings"
          className={({ isActive }) =>
            `flex items-center gap-2.5 border-t border-slate-800 px-5 py-3.5 transition ${
              isActive ? 'bg-sky-500/10' : 'hover:bg-slate-800/60'
            }`
          }
        >
          {({ isActive }) => (
            <>
              <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-sky-600 to-sky-800 text-xs font-semibold text-slate-100">
                {initials(name)}
              </span>
              <div className="min-w-0 flex-1">
                <div className={`truncate text-sm font-medium capitalize ${isActive ? 'text-sky-200' : 'text-slate-200'}`}>{name}</div>
                <div className="text-[11px] text-slate-500">Settings</div>
              </div>
              <IconGear className={`h-4 w-4 shrink-0 ${isActive ? 'text-sky-400' : 'text-slate-500'}`} />
            </>
          )}
        </NavLink>
      </aside>

      <div className="flex flex-1 flex-col">
        <header className="flex items-center justify-between border-b border-slate-800 bg-slate-900/30 px-6 py-3.5">
          <div>
            <p className="text-sm text-slate-300">{greeting}, <span className="font-medium capitalize text-slate-100">{name}</span></p>
          </div>
          <div className="flex items-center gap-4">
            <button
              onClick={handleLogout}
              className="rounded-lg border border-slate-700 px-3.5 py-1.5 text-xs font-medium text-slate-300 transition hover:border-slate-600 hover:bg-slate-800 hover:text-slate-100"
            >
              Log out
            </button>
          </div>
        </header>

        <main className="flex-1 p-6">
          <Outlet />
        </main>
      </div>
    </div>
  )
}

function initials(name) {
  return (name || '?')
    .trim()
    .split(/\s+/)
    .slice(0, 2)
    .map((w) => w[0]?.toUpperCase())
    .join('') || '?'
}

function timeGreeting(date) {
  const h = date.getHours()
  if (h < 5) return 'Quiet watch'
  if (h < 12) return 'Good morning'
  if (h < 18) return 'Good afternoon'
  return 'Good evening'
}

function WatchMark() {
  return (
    <span className="relative flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-slate-800">
      <svg viewBox="0 0 24 24" className="h-4.5 w-4.5" fill="none">
        <path d="M12 3 L20 6.5 V12 C20 17 16.5 20 12 21.5 C7.5 20 4 17 4 12 V6.5 Z" stroke="#e2a164" strokeWidth="1.4" strokeLinejoin="round" />
        <circle cx="12" cy="11" r="2.6" stroke="#e2a164" strokeWidth="1.4" />
      </svg>
      <span className="absolute -right-0.5 -top-0.5 h-2 w-2 animate-pulse rounded-full bg-emerald-400" />
    </span>
  )
}

function IconGrid({ className }) {
  return <svg viewBox="0 0 24 24" fill="none" className={className}><rect x="3.5" y="3.5" width="7" height="7" rx="1.4" stroke="currentColor" strokeWidth="1.6"/><rect x="13.5" y="3.5" width="7" height="7" rx="1.4" stroke="currentColor" strokeWidth="1.6"/><rect x="3.5" y="13.5" width="7" height="7" rx="1.4" stroke="currentColor" strokeWidth="1.6"/><rect x="13.5" y="13.5" width="7" height="7" rx="1.4" stroke="currentColor" strokeWidth="1.6"/></svg>
}
function IconCamera({ className }) {
  return <svg viewBox="0 0 24 24" fill="none" className={className}><path d="M3.5 8.5A1.5 1.5 0 0 1 5 7h2.2l1-1.6A1.5 1.5 0 0 1 9.5 4.7h5a1.5 1.5 0 0 1 1.3.7l1 1.6H19a1.5 1.5 0 0 1 1.5 1.5v9A1.5 1.5 0 0 1 19 19H5a1.5 1.5 0 0 1-1.5-1.5Z" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round"/><circle cx="12" cy="13" r="3.4" stroke="currentColor" strokeWidth="1.6"/></svg>
}
function IconBell({ className }) {
  return <svg viewBox="0 0 24 24" fill="none" className={className}><path d="M6 10a6 6 0 1 1 12 0c0 4.2 1.2 5.5 1.6 6.1.3.4 0 .9-.5.9H4.9c-.5 0-.8-.5-.5-.9C4.8 15.5 6 14.2 6 10Z" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round"/><path d="M9.5 19.5a2.5 2.5 0 0 0 5 0" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round"/></svg>
}
function IconUpload({ className }) {
  return <svg viewBox="0 0 24 24" fill="none" className={className}><path d="M12 15V4.5M12 4.5 8.5 8M12 4.5 15.5 8" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"/><path d="M4.5 15.5V17a2.5 2.5 0 0 0 2.5 2.5h10a2.5 2.5 0 0 0 2.5-2.5v-1.5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round"/></svg>
}
function IconGear({ className }) {
  return <svg viewBox="0 0 24 24" fill="none" className={className}><path d="M12 15.2a3.2 3.2 0 1 0 0-6.4 3.2 3.2 0 0 0 0 6.4Z" stroke="currentColor" strokeWidth="1.6"/><path d="M19.4 13.5a1.7 1.7 0 0 0 .34 1.87l.06.06a2.05 2.05 0 1 1-2.9 2.9l-.06-.06a1.7 1.7 0 0 0-1.87-.34 1.7 1.7 0 0 0-1.03 1.56v.16a2.05 2.05 0 0 1-4.1 0v-.1a1.7 1.7 0 0 0-1.11-1.55 1.7 1.7 0 0 0-1.87.34l-.06.06a2.05 2.05 0 1 1-2.9-2.9l.06-.06a1.7 1.7 0 0 0 .34-1.87 1.7 1.7 0 0 0-1.56-1.03H4.6a2.05 2.05 0 0 1 0-4.1h.1a1.7 1.7 0 0 0 1.55-1.11 1.7 1.7 0 0 0-.34-1.87l-.06-.06a2.05 2.05 0 1 1 2.9-2.9l.06.06a1.7 1.7 0 0 0 1.87.34h.08a1.7 1.7 0 0 0 1.03-1.56V4.6a2.05 2.05 0 0 1 4.1 0v.1a1.7 1.7 0 0 0 1.03 1.56h.08a1.7 1.7 0 0 0 1.87-.34l.06-.06a2.05 2.05 0 1 1 2.9 2.9l-.06.06a1.7 1.7 0 0 0-.34 1.87v.08a1.7 1.7 0 0 0 1.56 1.03h.16a2.05 2.05 0 0 1 0 4.1h-.1a1.7 1.7 0 0 0-1.56 1.03Z" stroke="currentColor" strokeWidth="1.4" strokeLinejoin="round"/></svg>
}
