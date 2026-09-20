import { useEffect, useMemo, useState } from 'react'

function getAiBaseUrl() {
  const configured = String(import.meta.env.VITE_AI_API_URL || '').trim()
  if (configured) return configured.replace(/\/$/, '')
  const port = import.meta.env.VITE_AI_UPLOAD_API_PORT || '8002'
  return `${window.location.protocol}//${window.location.hostname}:${port}`
}

function formatTime(seconds) {
  const s = Math.max(0, Math.round(seconds || 0))
  const m = Math.floor(s / 60)
  const rem = s % 60
  return `${m}:${String(rem).padStart(2, '0')}`
}

export default function VideoUploadAnalyzer({ cameraId, onAlertsChanged }) {
  const [file, setFile] = useState(null)
  const [job, setJob] = useState(null)
  const [error, setError] = useState(null)
  const [uploading, setUploading] = useState(false)
  const aiUrl = useMemo(getAiBaseUrl, [])

  useEffect(() => {
    if (!job?.job_id || job.status === 'completed' || job.status === 'failed') return undefined

    const timer = window.setInterval(async () => {
      try {
        const response = await fetch(`${aiUrl}/api/video/jobs/${job.job_id}`)
        if (!response.ok) throw new Error(`Status request failed (${response.status})`)
        const next = await response.json()
        setJob(next)
        if (next.status === 'completed') onAlertsChanged?.()
      } catch (err) {
        setError(err.message)
      }
    }, 1500)

    return () => window.clearInterval(timer)
  }, [aiUrl, job?.job_id, job?.status, onAlertsChanged])

  async function startAnalysis() {
    if (!file || !cameraId) return
    setError(null)
    setUploading(true)
    setJob(null)

    try {
      const form = new FormData()
      form.append('video', file)
      form.append('camera_id', cameraId)

      const response = await fetch(`${aiUrl}/api/video/analyze`, { method: 'POST', body: form })
      const body = await response.json().catch(() => ({}))
      if (!response.ok) throw new Error(body.detail || `Upload failed (${response.status})`)
      setJob(body)
    } catch (err) {
      setError(err.message || 'Could not reach the AI analysis service. Is it running?')
    } finally {
      setUploading(false)
    }
  }

  const report = job?.status === 'completed' ? job.report : null

  return (
    <section className="overflow-hidden rounded-xl border border-slate-800 bg-slate-900 shadow-lg">
      <div className="border-b border-slate-800 px-4 py-3">
        <h2 className="text-sm font-semibold text-slate-200">Upload video for AI analysis</h2>
        <p className="mt-1 text-xs text-slate-500">
          Upload a recorded clip and get back a report of what was detected. Every event found is saved to this camera's alert history automatically.
        </p>
      </div>

      <div className="space-y-4 p-4">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
          <input
            type="file"
            accept="video/mp4,video/quicktime,video/x-msvideo,video/x-matroska,video/webm,video/x-m4v"
            onChange={(event) => setFile(event.target.files?.[0] || null)}
            className="block w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-300 file:mr-3 file:rounded file:border-0 file:bg-slate-800 file:px-3 file:py-2 file:text-xs file:font-medium file:text-slate-200"
          />
          <button
            type="button"
            disabled={!file || !cameraId || uploading || job?.status === 'processing'}
            onClick={startAnalysis}
            className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-40"
          >
            {uploading ? 'Uploading…' : job?.status === 'processing' ? 'Analyzing…' : 'Analyze Video'}
          </button>
        </div>

        {file && <p className="text-xs text-slate-500">Selected: {file.name}</p>}
        {error && <p className="rounded-lg border border-red-900 bg-red-950/40 px-3 py-2 text-sm text-red-300">{error}</p>}

        {job?.status === 'processing' && (
          <p className="rounded-lg border border-slate-800 bg-slate-950 px-3 py-2 text-xs text-slate-400">
            Processing {job.filename} — this can take a little while for longer clips.
          </p>
        )}

        {job?.status === 'failed' && (
          <p className="rounded-lg border border-red-900 bg-red-950/40 px-3 py-2 text-sm text-red-300">
            {job.error || 'Analysis failed.'}
          </p>
        )}

        {report && (
          <div className="space-y-4 rounded-lg border border-slate-800 bg-slate-950 p-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="text-sm text-slate-200">{report.summary}</p>
              {job.alerts_saved > 0 && (
                <span className="shrink-0 rounded-full border border-emerald-900 bg-emerald-950/30 px-3 py-1 text-[11px] text-emerald-300">
                  {job.alerts_saved} alert{job.alerts_saved !== 1 ? 's' : ''} saved to this camera
                </span>
              )}
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Objects detected</h3>
                {Object.keys(report.object_counts || {}).length > 0 ? (
                  <div className="mt-2 flex flex-wrap gap-2">
                    {Object.entries(report.object_counts).map(([name, count]) => (
                      <span key={name} className="rounded-full border border-slate-700 bg-slate-800 px-3 py-1 text-xs text-slate-200">
                        {count} {name}{count !== 1 ? 's' : ''}
                      </span>
                    ))}
                  </div>
                ) : (
                  <p className="mt-2 text-xs text-slate-600">None</p>
                )}
              </div>

              <div>
                <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Faces</h3>
                <p className="mt-2 text-xs text-slate-300">
                  {report.faces_detected_frames > 0
                    ? `Visible in ${report.faces_detected_frames} frame(s)`
                    : 'None spotted'}
                </p>
              </div>
            </div>

            {report.vehicles?.length > 0 && (
              <div>
                <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Vehicle plates read</h3>
                <ul className="mt-2 space-y-1">
                  {report.vehicles.map((v, i) => (
                    <li key={i} className="flex items-center justify-between rounded-md bg-slate-900 px-3 py-1.5 text-xs text-slate-300">
                      <span className="font-mono">{v.plate}</span>
                      <span className="text-slate-500">at {formatTime(v.time_seconds)}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            <div>
              <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Intrusion events</h3>
              {report.intrusions?.length > 0 ? (
                <ul className="mt-2 space-y-1">
                  {report.intrusions.map((e, i) => (
                    <li key={i} className="flex items-center justify-between rounded-md border border-red-900 bg-red-950/40 px-3 py-1.5 text-xs text-red-300">
                      <span>Track {e.track_id} entered the restricted zone</span>
                      <span>at {formatTime(e.time_seconds)}</span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="mt-2 text-xs text-slate-600">
                  No intrusions detected — or this camera has no restricted zone drawn yet.
                </p>
              )}
            </div>

            {report.activities?.length > 0 && (
              <div>
                <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Suspicious activity</h3>
                <ul className="mt-2 space-y-1">
                  {report.activities.map((e, i) => (
                    <li key={i} className="flex items-center justify-between rounded-md border border-amber-900 bg-amber-950/30 px-3 py-1.5 text-xs text-amber-300">
                      <span>Track {e.track_id} — {String(e.activity).replace(/_/g, ' ')}</span>
                      <span>at {formatTime(e.time_seconds)}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            <a href="/alerts" className="inline-block text-xs text-sky-400 hover:text-sky-300">View saved alerts →</a>
          </div>
        )}
      </div>
    </section>
  )
}
