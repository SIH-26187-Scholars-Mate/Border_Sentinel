import { useEffect, useMemo, useState } from 'react'
import { acknowledgeAlert, listAlerts } from '../api/alerts'
import { listCameras } from '../api/cameras'
import { cameraCode, formatAlertType, severityClass } from '../utils/camera'

const TYPE_OPTIONS = ['intrusion', 'unauthorized_vehicle', 'suspicious_activity', 'perimeter_breach', 'unattended_object', 'other']
const PAGE_SIZE = 8

export default function Alerts() {
  const [alerts, setAlerts] = useState([])
  const [cameras, setCameras] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [query, setQuery] = useState('')
  const [typeFilter, setTypeFilter] = useState('all')
  const [statusFilter, setStatusFilter] = useState('all')
  const [severityFilter, setSeverityFilter] = useState('all')
  const [cameraFilter, setCameraFilter] = useState('all')
  const [sourceFilter, setSourceFilter] = useState('all')
  const [dateFilter, setDateFilter] = useState('all')
  const [page, setPage] = useState(1)
  const [selected, setSelected] = useState(null)
  const [checked, setChecked] = useState(new Set())
  const [bulkBusy, setBulkBusy] = useState(false)

  function refresh() {
    setLoading(true)
    setError(null)
    Promise.all([listAlerts(), listCameras()])
      .then(([alertList, cameraList]) => { setAlerts(alertList); setCameras(cameraList) })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }

  useEffect(() => { refresh() }, [])
  useEffect(() => { setPage(1); setChecked(new Set()) }, [query, typeFilter, statusFilter, severityFilter, cameraFilter, sourceFilter, dateFilter])

  const cameraById = useMemo(() => new Map(cameras.map((camera) => [String(camera.id), camera])), [cameras])

  async function handleAcknowledge(id) {
    try {
      const updated = await acknowledgeAlert(id)
      setAlerts((prev) => prev.map((a) => (a.id === id ? updated : a)))
      setSelected((prev) => prev?.id === id ? updated : prev)
      setChecked((prev) => { const next = new Set(prev); next.delete(id); return next })
    } catch (err) { setError(err.message) }
  }

  async function acknowledgeSelected() {
    if (!checked.size) return
    setBulkBusy(true)
    try {
      const updates = await Promise.all([...checked].map((id) => acknowledgeAlert(id)))
      const byId = new Map(updates.map((a) => [a.id, a]))
      setAlerts((prev) => prev.map((a) => byId.get(a.id) || a))
      setChecked(new Set())
    } catch (err) { setError(err.message) }
    finally { setBulkBusy(false) }
  }

  // With nothing checked, the button doubles as a quick filter: click it to
  // show acknowledged-only, click again to go back to all statuses.
  function handleAcknowledgeButtonClick() {
    if (checked.size) { acknowledgeSelected(); return }
    setStatusFilter((prev) => (prev === 'acknowledged' ? 'all' : 'acknowledged'))
  }

  const filtered = alerts.filter((a) => {
    const camera = cameraById.get(String(a.camera_id))
    const haystack = `${formatAlertType(a.alert_type)} ${a.description || ''} ${camera?.name || ''} ${cameraCode(camera)}`.toLowerCase()
    if (query && !haystack.includes(query.toLowerCase())) return false
    if (typeFilter !== 'all' && a.alert_type !== typeFilter) return false
    if (statusFilter === 'open' && a.is_acknowledged) return false
    if (statusFilter === 'acknowledged' && !a.is_acknowledged) return false
    if (severityFilter !== 'all' && a.severity !== severityFilter) return false
    if (cameraFilter !== 'all' && String(a.camera_id) !== cameraFilter) return false
    if (sourceFilter !== 'all' && (a.source || 'live') !== sourceFilter) return false
    if (dateFilter !== 'all') {
      const age = Date.now() - new Date(a.created_at).getTime()
      const days = dateFilter === 'today' ? 1 : dateFilter === '7d' ? 7 : 30
      if (age > days * 86400000) return false
    }
    return true
  })
  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE))
  const pageItems = filtered.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE)
  const allPageChecked = pageItems.length > 0 && pageItems.every((a) => checked.has(a.id))

  function toggleAllPage() {
    setChecked((prev) => {
      const next = new Set(prev)
      if (allPageChecked) pageItems.forEach((a) => next.delete(a.id))
      else pageItems.forEach((a) => { if (!a.is_acknowledged) next.add(a.id) })
      return next
    })
  }

  function exportCsv() {
    const header = ['Alert ID', 'Severity', 'Event', 'Camera', 'Time', 'Confidence', 'Status']
    const rows = filtered.map((a) => {
      const c = cameraById.get(String(a.camera_id))
      return [a.id, a.severity, formatAlertType(a.alert_type), `${cameraCode(c)} ${c?.name || ''}`.trim(), new Date(a.created_at).toISOString(), `${Math.round(a.confidence * 100)}%`, a.is_acknowledged ? 'Acknowledged' : 'Open']
    })
    const csv = [header, ...rows].map((r) => r.map((v) => `"${String(v).replaceAll('"', '""')}"`).join(',')).join('\n')
    const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }))
    const a = document.createElement('a'); a.href = url; a.download = `border-sentinel-alerts-${new Date().toISOString().slice(0, 10)}.csv`; a.click(); URL.revokeObjectURL(url)
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-slate-100">Alerts</h1>
          <p className="mt-1 text-sm text-slate-500">Search, filter, acknowledge and investigate events generated by the monitoring network.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button onClick={exportCsv} className="rounded-lg border border-slate-700 px-3 py-2 text-xs text-slate-300 hover:bg-slate-800">Export CSV</button>
          <button onClick={refresh} className="rounded-lg border border-slate-700 px-3 py-2 text-xs text-slate-300 hover:bg-slate-800">Refresh</button>
          <button
            disabled={bulkBusy}
            onClick={handleAcknowledgeButtonClick}
            className={`rounded-lg px-3 py-2 text-xs font-medium text-white disabled:opacity-40 ${statusFilter === 'acknowledged' && !checked.size ? 'bg-amber-600' : 'bg-sky-600'}`}
          >
            {bulkBusy
              ? 'Acknowledging…'
              : checked.size
                ? `Acknowledge selected (${checked.size})`
                : statusFilter === 'acknowledged'
                  ? 'Showing acknowledged only'
                  : 'Acknowledge selected'}
          </button>
        </div>
      </div>

      {error && <div className="rounded-lg border border-red-900 bg-red-950/40 px-4 py-3 text-sm text-red-300">{error}</div>}

      <section className="rounded-xl border border-slate-800 bg-slate-900/80 p-4 shadow-lg">
        <div className="grid gap-2 md:grid-cols-2 lg:grid-cols-4">
          <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search event, camera or description…" className="rounded-lg border border-slate-700 bg-slate-950 px-3 py-2.5 text-xs text-slate-200 outline-none focus:border-sky-600 lg:col-span-2" />
          <Filter value={typeFilter} setValue={setTypeFilter} options={['all', ...TYPE_OPTIONS]} labels={['All event types', ...TYPE_OPTIONS.map(formatAlertType)]} />
          <Filter value={statusFilter} setValue={setStatusFilter} options={['all', 'open', 'acknowledged']} labels={['All status', 'Open only', 'Acknowledged only']} />
          <Filter value={severityFilter} setValue={setSeverityFilter} options={['all', 'critical', 'high', 'medium', 'low']} labels={['All severity', 'Critical', 'High', 'Medium', 'Low']} />
          <select value={cameraFilter} onChange={(e) => setCameraFilter(e.target.value)} className="rounded-lg border border-slate-700 bg-slate-950 px-3 py-2.5 text-xs text-slate-200"><option value="all">All cameras</option>{cameras.map((c) => <option key={c.id} value={c.id}>{cameraCode(c)} · {c.name}</option>)}</select>
          <Filter value={sourceFilter} setValue={setSourceFilter} options={['all', 'live', 'video_analysis']} labels={['Live + uploaded', 'Live cameras only', 'Uploaded videos only']} />
          <Filter value={dateFilter} setValue={setDateFilter} options={['all', 'today', '7d', '30d']} labels={['Any time', 'Today', 'Last 7 days', 'Last 30 days']} />
        </div>
      </section>

      <section className="overflow-hidden rounded-xl border border-slate-800 bg-slate-900/80 shadow-lg">
        <div className="flex items-center justify-between border-b border-slate-800 px-5 py-4">
          <div><h2 className="text-sm font-semibold text-slate-200">Event queue</h2><p className="mt-0.5 text-xs text-slate-500">{filtered.length} matching events · page {page} of {totalPages}</p></div>
          <label className="flex items-center gap-2 text-xs text-slate-500"><input type="checkbox" checked={allPageChecked} onChange={toggleAllPage} /> Select page</label>
        </div>
        {loading ? <div className="p-10 text-center text-sm text-slate-500">Loading incident queue…</div> : pageItems.length === 0 ? <div className="p-10 text-center text-sm text-slate-500">No events match the current filters.</div> : (
          <div className="divide-y divide-slate-800">
            {pageItems.map((alert) => {
              const camera = cameraById.get(String(alert.camera_id))
              return <article key={alert.id} className="flex flex-col gap-4 px-5 py-4 lg:flex-row lg:items-center lg:justify-between hover:bg-slate-950/30">
                <div className="flex min-w-0 items-start gap-3">
                  <input type="checkbox" checked={checked.has(alert.id)} disabled={alert.is_acknowledged} onChange={(e) => setChecked((prev) => { const next = new Set(prev); e.target.checked ? next.add(alert.id) : next.delete(alert.id); return next })} className="mt-1" />
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2"><span className="text-sm font-medium text-slate-100">{formatAlertType(alert.alert_type)}</span><span className={`rounded-full border px-2 py-0.5 text-[10px] font-medium uppercase ${severityClass(alert.severity)}`}>{alert.severity}</span><span className={`rounded-full border px-2 py-0.5 text-[10px] ${alert.is_acknowledged ? 'border-slate-700 text-slate-500' : 'border-amber-900 bg-amber-950/30 text-amber-300'}`}>{alert.is_acknowledged ? 'Acknowledged' : 'Open'}</span>{alert.source === 'video_analysis' && <span className="rounded-full border border-indigo-900 bg-indigo-950/30 px-2 py-0.5 text-[10px] text-indigo-300">Uploaded video</span>}</div>
                    <div className="mt-1 flex flex-wrap gap-x-3 gap-y-1 text-xs text-slate-500"><span>{camera ? `${cameraCode(camera)} · ${camera.name}` : 'Camera unavailable'}</span><span>{new Date(alert.created_at).toLocaleString()}</span><span>{Math.round(alert.confidence * 100)}% confidence</span></div>
                    {alert.description && <p className="mt-2 max-w-2xl text-xs leading-5 text-slate-500">{alert.description}</p>}
                  </div>
                </div>
                <div className="flex shrink-0 flex-wrap gap-2 lg:justify-end">
                  <button onClick={() => setSelected(alert)} className="rounded-lg border border-slate-700 px-3 py-1.5 text-xs text-slate-300 hover:border-sky-700 hover:text-sky-300">Details & evidence</button>
                  {!alert.is_acknowledged && <button onClick={() => handleAcknowledge(alert.id)} className="rounded-lg border border-emerald-900/70 bg-emerald-950/20 px-3 py-1.5 text-xs text-emerald-300 hover:bg-emerald-950/40">Acknowledge</button>}
                </div>
              </article>
            })}
          </div>
        )}
        <div className="flex items-center justify-between border-t border-slate-800 px-5 py-3 text-xs text-slate-500"><span>Showing {filtered.length ? (page - 1) * PAGE_SIZE + 1 : 0}–{Math.min(page * PAGE_SIZE, filtered.length)} of {filtered.length}</span><div className="flex gap-2"><button disabled={page <= 1} onClick={() => setPage(p => p - 1)} className="rounded border border-slate-700 px-3 py-1.5 disabled:opacity-30">Previous</button><button disabled={page >= totalPages} onClick={() => setPage(p => p + 1)} className="rounded border border-slate-700 px-3 py-1.5 disabled:opacity-30">Next</button></div></div>
      </section>

      {selected && <AlertModal alert={selected} camera={cameraById.get(String(selected.camera_id))} onClose={() => setSelected(null)} onAcknowledge={handleAcknowledge} />}
    </div>
  )
}

function Filter({ value, setValue, options, labels }) { return <select value={value} onChange={(e) => setValue(e.target.value)} className="rounded-lg border border-slate-700 bg-slate-950 px-3 py-2.5 text-xs text-slate-200">{options.map((o, i) => <option key={o} value={o}>{labels[i]}</option>)}</select> }

function AlertModal({ alert, camera, onClose, onAcknowledge }) {
  return <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4" onMouseDown={onClose}>
    <div className="max-h-[90vh] w-full max-w-3xl overflow-auto rounded-2xl border border-slate-700 bg-slate-900 shadow-2xl" onMouseDown={(e) => e.stopPropagation()}>
      <div className="flex items-start justify-between border-b border-slate-800 p-5"><div><div className="flex flex-wrap items-center gap-2"><span className="text-lg font-semibold text-slate-100">{formatAlertType(alert.alert_type)}</span><span className={`rounded-full border px-2 py-0.5 text-[10px] uppercase ${severityClass(alert.severity)}`}>{alert.severity}</span></div><p className="mt-1 text-xs text-slate-500">{camera ? `${cameraCode(camera)} · ${camera.name} · ${camera.location}` : 'Camera unavailable'}</p></div><button onClick={onClose} className="rounded-lg border border-slate-700 px-2.5 py-1 text-xs text-slate-400">Close</button></div>
      <div className="grid gap-5 p-5 md:grid-cols-2">
        <div className="overflow-hidden rounded-xl border border-slate-800 bg-black"><div className="flex aspect-video items-center justify-center">{alert.image_url ? <img src={alert.image_url} alt="Alert evidence" className="h-full w-full object-contain" /> : <div className="p-8 text-center text-xs text-slate-600">No evidence snapshot attached to this event.</div>}</div></div>
        <div className="space-y-3"><Detail label="Event" value={formatAlertType(alert.alert_type)} /><Detail label="Camera" value={camera ? `${cameraCode(camera)} · ${camera.name}` : 'Unavailable'} /><Detail label="Time" value={new Date(alert.created_at).toLocaleString()} /><Detail label="Confidence" value={`${Math.round(alert.confidence * 100)}%`} /><Detail label="Status" value={alert.is_acknowledged ? `Acknowledged${alert.acknowledged_at ? ` · ${new Date(alert.acknowledged_at).toLocaleString()}` : ''}` : 'Open'} />{alert.description && <Detail label="Description" value={alert.description} />}</div>
      </div>
      <div className="flex justify-end gap-2 border-t border-slate-800 p-5">{camera && <a href={`/cameras/${camera.id}`} className="rounded-lg border border-sky-800 bg-sky-950/30 px-3 py-2 text-xs text-sky-300">Open source camera</a>}{!alert.is_acknowledged && <button onClick={() => onAcknowledge(alert.id)} className="rounded-lg bg-emerald-600 px-3 py-2 text-xs font-medium text-white">Acknowledge alert</button>}</div>
    </div>
  </div>
}
function Detail({ label, value }) { return <div className="rounded-lg border border-slate-800 bg-slate-950/60 p-3"><div className="text-[10px] uppercase tracking-wider text-slate-600">{label}</div><div className="mt-1 text-sm text-slate-200">{value}</div></div> }