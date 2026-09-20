import { useEffect, useMemo, useState } from 'react'
import { getCameraWorker, startCamera, stopCamera } from '../api/cameras'

function getPreviewUrl(camera, attempt = 0) {
  const port = camera?.preview_port || 8101
  const channel = encodeURIComponent(camera?.id || 'live')
  const cacheBust = attempt ? `&t=${attempt}` : ''
  return `${window.location.protocol}//${window.location.hostname}:${port}/stream.mjpg?job=${channel}${cacheBust}`
}

export default function CameraPreview({ camera, onCameraChanged }) {
  const [failed, setFailed] = useState(false)
  const [running, setRunning] = useState(Boolean(camera?.ai_running))
  const [busy, setBusy] = useState(false)
  const [statusText, setStatusText] = useState(camera?.ai_status || 'stopped')
  const [errorText, setErrorText] = useState(camera?.ai_error || '')
  const [previewAttempt, setPreviewAttempt] = useState(0)
  const streamUrl = useMemo(() => getPreviewUrl(camera, previewAttempt), [camera?.id, camera?.preview_port, previewAttempt])

  useEffect(() => {
    setFailed(false)
    setRunning(Boolean(camera?.ai_running))
    setStatusText(camera?.ai_status || 'stopped')
    setErrorText(camera?.ai_error || '')
    setPreviewAttempt(0)

    if (!camera?.id) return
    let cancelled = false
    const poll = async () => {
      try {
        const state = await getCameraWorker(camera.id)
        if (cancelled) return
        setRunning(Boolean(state.running))
        setStatusText(state.status || (state.running ? 'running' : 'stopped'))
        setErrorText(state.ai_error || '')
        if (state.preview_port && state.preview_port !== camera.preview_port) {
          onCameraChanged?.({ ...camera, ...state, ai_running: Boolean(state.running), ai_status: state.status })
        }
      } catch {
        // A brief status-poll failure should not stop the live preview.
      }
    }
    poll()
    const timer = window.setInterval(poll, 2000)
    return () => { cancelled = true; window.clearInterval(timer) }
  }, [camera?.id])

  // Browsers do not reliably retry a failed MJPEG <img>. Retry the connection
  // while the worker is alive, because the worker may still be loading YOLO or
  // opening an RTSP/webcam source.
  useEffect(() => {
    if (!running || !failed) return
    const timer = window.setTimeout(() => setPreviewAttempt((n) => n + 1), 1500)
    return () => window.clearTimeout(timer)
  }, [running, failed, previewAttempt])

  async function toggle() {
    setBusy(true)
    setFailed(false)
    setErrorText('')
    try {
      const updated = running ? await stopCamera(camera.id) : await startCamera(camera.id)
      setRunning(Boolean(updated.ai_running))
      setStatusText(updated.ai_status || (updated.ai_running ? 'starting' : 'stopped'))
      setErrorText(updated.ai_error || '')
      setPreviewAttempt((n) => n + 1)
      onCameraChanged?.(updated)
    } catch (err) {
      setStatusText('error')
      setErrorText(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="overflow-hidden rounded-xl border border-slate-800 bg-slate-950 shadow-xl shadow-black/20">
      <div className="flex flex-col gap-3 border-b border-slate-800 px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="flex items-center gap-2"><h2 className="text-sm font-semibold text-slate-100">Live camera view</h2><span className="rounded-full border border-sky-900/70 bg-sky-950/40 px-2 py-0.5 text-[10px] uppercase tracking-wider text-sky-300">AI overlay</span></div>
          <p className="mt-1 text-xs text-slate-500">The AI worker stays connected to the configured RTSP stream or laptop webcam until you stop it or log out.</p>
        </div>
        <div className="flex items-center gap-2">
          <span className={`flex items-center gap-1.5 text-xs ${running && !failed ? 'text-emerald-400' : 'text-slate-500'}`}><span className={`h-2 w-2 rounded-full ${running && !failed ? 'bg-emerald-400' : 'bg-slate-600'}`} />{running && !failed ? 'LIVE' : statusText.toUpperCase()}</span>
          <button disabled={busy} onClick={toggle} className="rounded-lg border border-slate-700 px-3 py-1.5 text-xs text-slate-300 hover:bg-slate-800 disabled:opacity-50">{busy ? 'Working…' : running ? 'Stop camera' : 'Start camera'}</button>
        </div>
      </div>

      <div className="relative aspect-video overflow-hidden bg-black">
        {running && <img key={streamUrl} src={streamUrl} alt={`${camera.name} live AI feed`} className="h-full w-full object-contain" onLoad={() => setFailed(false)} onError={() => setFailed(true)} />}
        {!running && <PreviewOverlay><p className="font-medium text-slate-200">AI worker is stopped</p><p className="mt-2 max-w-md text-xs leading-5 text-slate-500">Click Start camera. The backend will launch the configured RTSP stream automatically. If the source is blank/null, it uses webcam 0.</p></PreviewOverlay>}
        {running && failed && <PreviewOverlay><p className="font-medium text-slate-200">Connecting to camera feed…</p><p className="mt-2 max-w-md text-xs leading-5 text-slate-400">The preview will retry automatically while the AI worker opens or reconnects to the camera.</p></PreviewOverlay>}
        {!running && errorText && <PreviewOverlay><p className="font-medium text-red-300">AI worker could not start</p><p className="mt-2 max-w-xl text-xs leading-5 text-slate-400">{errorText}</p><p className="mt-2 text-[11px] text-slate-500">Check runtime/ai-logs for the full worker log.</p></PreviewOverlay>}
        {running && !failed && <div className="pointer-events-none absolute left-3 top-3 rounded-md border border-emerald-700/60 bg-black/70 px-2.5 py-1.5 text-[11px] text-emerald-300">● AI PROCESSING · YOLO · TRACKING · ANPR · RULES</div>}
      </div>

      <div className="grid grid-cols-2 gap-px border-t border-slate-800 bg-slate-800 sm:grid-cols-4">
        {['YOLO detection', 'Tracking IDs', 'ANPR + OCR', 'Zone rules'].map((item) => <div key={item} className="bg-slate-950 px-4 py-3 text-xs text-slate-400"><span className="mr-2 text-emerald-400">✓</span>{item}</div>)}
      </div>
    </section>
  )
}

function PreviewOverlay({ children }) { return <div className="absolute inset-0 flex flex-col items-center justify-center bg-black/75 p-6 text-center">{children}</div> }
