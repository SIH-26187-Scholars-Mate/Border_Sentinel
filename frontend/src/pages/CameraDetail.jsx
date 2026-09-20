import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { listAlerts } from '../api/alerts'
import { getCamera } from '../api/cameras'
import CameraPreview from '../components/CameraPreview'
import VideoUploadAnalyzer from '../components/VideoUploadAnalyzer'
import ZoneEditor from '../components/ZoneEditor'
import { cameraCode, formatAlertType, severityClass } from '../utils/camera'

export default function CameraDetail() {
  const { id } = useParams()
  const [camera, setCamera] = useState(null)
  const [alerts, setAlerts] = useState([])
  const [error, setError] = useState(null)
  const [alertError, setAlertError] = useState(null)

  function refreshAlerts() {
    return listAlerts(id)
      .then(setAlerts)
      .catch((err) =>
        setAlertError(`Could not load alert history: ${err.message}`)
      )
  }

  useEffect(() => {
    let cancelled = false
    setError(null)
    setAlertError(null)

    getCamera(id)
      .then((cam) => {
        if (!cancelled) setCamera(cam)
      })
      .catch((err) => {
        if (!cancelled) setError(err.message)
      })

    refreshAlerts()

    return () => {
      cancelled = true
    }
  }, [id])

  const code = cameraCode(camera)

  if (error) {
    return (
      <div className="rounded-lg border border-red-900 bg-red-950/40 p-4 text-sm text-red-300">
        {error}
      </div>
    )
  }

  if (!camera) {
    return (
      <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-8 text-center text-sm text-slate-500">
        Loading camera…
      </div>
    )
  }

  const openAlerts = alerts.filter((a) => !a.is_acknowledged).length
  const criticalAlerts = alerts.filter((a) => a.severity === 'critical').length

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <Link
            to="/cameras"
            className="text-xs font-medium text-sky-400 hover:text-sky-300"
          >
            Back to cameras
          </Link>

          <div className="mt-2 flex flex-wrap items-center gap-2">
            <span className="rounded-md border border-slate-700 bg-slate-900 px-2 py-1 font-mono text-[11px] text-slate-400">
              {code}
            </span>

            <span
              className={`rounded-full border px-2 py-1 text-[10px] uppercase ${
                camera.is_active
                  ? 'border-emerald-900/70 bg-emerald-950/40 text-emerald-400'
                  : 'border-slate-700 bg-slate-900 text-slate-500'
              }`}
            >
              {camera.is_active ? 'Active' : 'Offline'}
            </span>

            <span
              className={`rounded-full border px-2 py-1 text-[10px] uppercase ${
                camera.ai_running
                  ? 'border-sky-900 bg-sky-950/40 text-sky-300'
                  : 'border-slate-700 text-slate-500'
              }`}
            >
              AI {camera.ai_running ? 'running' : 'stopped'}
            </span>
          </div>

          <h1 className="mt-2 text-2xl font-semibold tracking-tight text-slate-100">
            {camera.name}
          </h1>

          <p className="mt-1 text-sm text-slate-500">{camera.location}</p>
        </div>

        <div className="rounded-lg border border-slate-800 bg-slate-900 px-4 py-3 text-right">
          <div className="text-[10px] uppercase tracking-wider text-slate-600">
            Source
          </div>

          <div className="mt-1 max-w-sm truncate text-xs text-slate-300">
            {camera.stream_url || 'Laptop webcam · source 0'}
          </div>
        </div>
      </div>

      <CameraPreview
        camera={camera}
        onCameraChanged={setCamera}
      />

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
        <Info label="AI status" value={camera.ai_running ? 'Active' : 'Stopped'} />
        <Info label="Open alerts" value={openAlerts} />
        <Info label="Critical events" value={criticalAlerts} />
        <Info label="Latitude" value={camera.latitude ?? '—'} />
        <Info label="Longitude" value={camera.longitude ?? '—'} />
      </div>

      <ZoneEditor
        cameraId={id}
        camera={camera}
      />

      <VideoUploadAnalyzer
        cameraId={id}
        onAlertsChanged={refreshAlerts}
      />

      {alertError && (
        <div className="rounded-lg border border-amber-900 bg-amber-950/40 px-4 py-3 text-sm text-amber-300">
          {alertError}
        </div>
      )}

      <section className="overflow-hidden rounded-xl border border-slate-800 bg-slate-900/80 shadow-lg">
        <div className="flex items-center justify-between border-b border-slate-800 px-5 py-4">
          <div>
            <h2 className="text-sm font-semibold text-slate-200">
              Camera incident timeline
            </h2>
            <p className="mt-0.5 text-xs text-slate-500">
              Detection events and evidence associated with {code}.
            </p>
          </div>

          <Link
            to="/alerts"
            className="text-xs text-sky-400 hover:text-sky-300"
          >
            Open incident center
          </Link>
        </div>

        <div className="divide-y divide-slate-800">
          {alerts.length === 0 && (
            <div className="px-5 py-8 text-center text-sm text-slate-500">
              No alerts recorded for this camera.
            </div>
          )}

          {alerts.slice(0, 12).map((a) => (
            <div
              key={a.id}
              className="flex flex-col gap-3 px-5 py-4 sm:flex-row sm:items-center sm:justify-between"
            >
              <div>
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-sm capitalize text-slate-200">
                    {formatAlertType(a.alert_type)}
                  </span>

                  <span
                    className={`rounded-full border px-2 py-0.5 text-[10px] uppercase ${severityClass(
                      a.severity
                    )}`}
                  >
                    {a.severity}
                  </span>

                  <span className="text-[10px] text-slate-600">
                    {a.is_acknowledged ? 'Acknowledged' : 'Open'}
                  </span>
                </div>

                <div className="mt-1 text-xs text-slate-500">
                  {new Date(a.created_at).toLocaleString()} · confidence{' '}
                  {Math.round(a.confidence * 100)}%
                </div>

                {a.description && (
                  <p className="mt-1 text-xs text-slate-600">
                    {a.description}
                  </p>
                )}
              </div>

              {a.image_url && (
                <a
                  href={a.image_url}
                  target="_blank"
                  rel="noreferrer"
                  className="text-xs text-sky-400"
                >
                  View evidence
                </a>
              )}
            </div>
          ))}
        </div>
      </section>
    </div>
  )
}

function Info({ label, value }) {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/80 p-4">
      <div className="text-[10px] uppercase tracking-wider text-slate-600">
        {label}
      </div>
      <div className="mt-1 text-sm text-slate-200">{value}</div>
    </div>
  )
}
