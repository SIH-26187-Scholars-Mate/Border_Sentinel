import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { listAlerts } from '../api/alerts'
import { listCameras } from '../api/cameras'
import { useAlertsSocket } from '../hooks/useAlertsSocket'
import { cameraCode, formatAlertType, severityClass } from '../utils/camera'

export default function Dashboard() {
  const { alerts: liveAlerts, connected } = useAlertsSocket()
  const [history, setHistory] = useState([])
  const [cameras, setCameras] = useState([])
  const [error, setError] = useState(null)

  useEffect(() => {
    Promise.all([listAlerts(), listCameras()]).then(([alerts, cameraList]) => { setHistory(alerts); setCameras(cameraList) }).catch((err) => setError(err.message))
  }, [])

  const cameraById = useMemo(() => new Map(cameras.map((camera) => [String(camera.id), camera])), [cameras])
  const seen = new Set()
  const merged = [...liveAlerts, ...history].filter((a) => { if (seen.has(a.id)) return false; seen.add(a.id); return true }).sort((a, b) => new Date(b.created_at) - new Date(a.created_at))
  const unacknowledged = merged.filter((a) => !a.is_acknowledged).length
  const bySeverity = merged.reduce((acc, a) => { acc[a.severity] = (acc[a.severity] || 0) + 1; return acc }, {})
  const activeCameras = cameras.filter((camera) => camera.is_active).length
  const aiWorkers = cameras.filter((camera) => camera.ai_running).length
  const critical = merged.filter((a) => a.severity === 'critical' && !a.is_acknowledged).slice(0, 3)
  const criticalCount = bySeverity.critical || 0

  return (
    <div className="space-y-6">
      {/* Hero: the one thing an operator needs to know at a glance */}
      <section className="relative overflow-hidden rounded-2xl border border-slate-800 p-6" style={{ background: 'linear-gradient(120deg, #1a2130 0%, #1a2130 55%, #2b160a 130%)' }}>
        <div className="flex flex-col gap-6 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <h1 className="text-2xl font-semibold text-slate-100">Operations overview</h1>
            <p className="mt-1.5 max-w-md text-sm text-slate-400">
              {criticalCount > 0
                ? `${criticalCount} critical event${criticalCount === 1 ? '' : 's'} need${criticalCount === 1 ? 's' : ''} attention right now.`
                : 'No critical events open. The network is quiet.'}
            </p>
            <span className={`mt-4 inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-xs ${connected ? 'border-emerald-900/70 bg-emerald-950/40 text-emerald-300' : 'border-red-900/70 bg-red-950/40 text-red-300'}`}>
              <span className={`h-2 w-2 rounded-full ${connected ? 'bg-emerald-400 animate-pulse' : 'bg-red-400'}`} />
              {connected ? 'Live alert stream connected' : 'Reconnecting to alert stream'}
            </span>
          </div>
          <div className="flex shrink-0 items-center gap-6">
            <RingStat value={criticalCount} label="Critical" color="#d1553f" />
            <RingStat value={activeCameras} total={cameras.length || activeCameras} label="Cameras online" color="#5fbdae" />
            <RingStat value={aiWorkers} total={cameras.length || aiWorkers} label="AI workers" color="#e2a164" />
          </div>
        </div>
      </section>

      {error && <div className="rounded-lg border border-red-900 bg-red-950/40 px-4 py-3 text-sm text-red-300">Could not load monitoring data: {error}</div>}

      <div className="grid gap-6 xl:grid-cols-[1.6fr_1fr]">
        <section className="rounded-xl border border-slate-800 bg-slate-900/60">
          <div className="flex items-center justify-between border-b border-slate-800 px-5 py-4">
            <div>
              <h2 className="text-sm font-semibold text-slate-200">Priority queue</h2>
              <p className="mt-0.5 text-xs text-slate-500">Unacknowledged events that need a decision.</p>
            </div>
            <Link to="/alerts" className="text-xs font-medium text-sky-400 hover:text-sky-300">Open incident center</Link>
          </div>
          <div className="divide-y divide-slate-800">
            {critical.length === 0
              ? <div className="p-10 text-center text-sm text-slate-500">Nothing waiting on you.</div>
              : critical.map((alert) => <AlertRow key={alert.id} alert={alert} camera={cameraById.get(String(alert.camera_id))} />)}
          </div>
        </section>

        <section className="rounded-xl border border-slate-800 bg-slate-900/60">
          <div className="border-b border-slate-800 px-5 py-4">
            <h2 className="text-sm font-semibold text-slate-200">Camera health</h2>
            <p className="mt-0.5 text-xs text-slate-500">AI workers run only while a camera is active.</p>
          </div>
          <div className="divide-y divide-slate-800">
            {cameras.slice(0, 6).map((camera) => (
              <Link to={`/cameras/${camera.id}`} key={camera.id} className="flex items-center justify-between px-5 py-3 transition hover:bg-slate-950/40">
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="rounded border border-slate-700 px-1.5 py-0.5 font-mono text-[10px] text-slate-500">{cameraCode(camera)}</span>
                    <span className="truncate text-xs font-medium text-slate-200">{camera.name}</span>
                  </div>
                  <p className="mt-1 truncate text-[11px] text-slate-600">{camera.location}</p>
                </div>
                <div className="flex items-center gap-2 text-[10px]">
                  <span className={`h-2 w-2 rounded-full ${camera.ai_running ? 'bg-emerald-400' : camera.is_active ? 'bg-amber-400' : 'bg-slate-600'}`} />
                  <span className={camera.ai_running ? 'text-emerald-300' : camera.is_active ? 'text-amber-300' : 'text-slate-600'}>{camera.ai_running ? 'AI live' : camera.is_active ? 'Starting' : 'Offline'}</span>
                </div>
              </Link>
            ))}
            {!cameras.length && <div className="p-8 text-center text-xs text-slate-500">No cameras registered.</div>}
          </div>
          <div className="border-t border-slate-800 p-4">
            <Link to="/cameras" className="block rounded-lg border border-slate-700 px-3 py-2 text-center text-xs text-slate-300 transition hover:border-sky-700 hover:text-sky-300">Manage cameras</Link>
          </div>
        </section>
      </div>

      <section className="rounded-xl border border-slate-800 bg-slate-900/60">
        <div className="flex items-center justify-between border-b border-slate-800 px-5 py-4">
          <div>
            <h2 className="text-sm font-semibold text-slate-200">Recent activity</h2>
            <p className="mt-0.5 text-xs text-slate-500">Newest events across the network.</p>
          </div>
          <Link to="/alerts" className="text-xs text-sky-400 hover:text-sky-300">Search all events</Link>
        </div>
        <div className="divide-y divide-slate-800">
          {merged.slice(0, 8).map((alert) => <AlertRow key={alert.id} alert={alert} camera={cameraById.get(String(alert.camera_id))} />)}
          {!merged.length && <div className="p-10 text-center text-sm text-slate-500">No events yet.</div>}
        </div>
      </section>
    </div>
  )
}

function RingStat({ value, total, label, color }) {
  const pct = total ? Math.min(1, value / total) : value > 0 ? 1 : 0
  const r = 20, c = 2 * Math.PI * r
  return (
    <div className="flex flex-col items-center">
      <svg width="52" height="52" viewBox="0 0 52 52">
        <circle cx="26" cy="26" r={r} fill="none" stroke="#293245" strokeWidth="4" />
        <circle cx="26" cy="26" r={r} fill="none" stroke={color} strokeWidth="4" strokeLinecap="round"
          strokeDasharray={c} strokeDashoffset={c * (1 - pct)} transform="rotate(-90 26 26)" />
        <text x="26" y="30" textAnchor="middle" fontSize="15" fontWeight="600" fill="#f2eee1">{value}</text>
      </svg>
      <span className="mt-1.5 text-[11px] text-slate-500">{label}</span>
    </div>
  )
}

function AlertRow({ alert, camera }) {
  return (
    <div className="flex flex-col gap-3 px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-sm font-medium capitalize text-slate-100">{formatAlertType(alert.alert_type)}</span>
          <span className={`rounded-full border px-2 py-0.5 text-[10px] ${severityClass(alert.severity)}`}>{alert.severity}</span>
          {!alert.is_acknowledged && <span className="text-[10px] font-medium text-amber-300">Open</span>}
        </div>
        <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-slate-500">
          {camera ? <span className="flex items-center gap-1.5"><span className="rounded border border-slate-800 px-1 font-mono text-[10px] text-slate-600">{cameraCode(camera)}</span>{camera.name}</span> : <span>Camera unavailable</span>}
          <span>{new Date(alert.created_at).toLocaleString()}</span>
          <span>{Math.round(alert.confidence * 100)}% confidence</span>
        </div>
      </div>
      {camera && <Link to={`/cameras/${camera.id}`} className="shrink-0 rounded-lg border border-slate-700 px-3 py-1.5 text-xs text-slate-300 transition hover:border-sky-700 hover:text-sky-300">View camera</Link>}
    </div>
  )
}
