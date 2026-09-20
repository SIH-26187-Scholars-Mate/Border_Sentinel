import { useEffect, useState } from 'react'
import { listCameras } from '../api/cameras'
import VideoUploadAnalyzer from '../components/VideoUploadAnalyzer'
import { cameraCode } from '../utils/camera'

export default function Analyze() {
  const [cameras, setCameras] = useState([])
  const [selected, setSelected] = useState('')
  const [error, setError] = useState(null)

  useEffect(() => {
    listCameras().then((items) => { setCameras(items); if (items[0]) setSelected(String(items[0].id)) }).catch((err) => setError(err.message))
  }, [])

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-slate-100">Analyze recorded video</h1>
        <p className="mt-1 max-w-2xl text-sm text-slate-500">Upload a recorded clip against one of your cameras and get a plain report of what the AI found — objects seen, vehicle plates read, faces spotted, and any intrusions or suspicious activity. Everything found is saved as an alert on that camera automatically.</p>
      </div>

      {error && <div className="rounded-lg border border-red-900 bg-red-950/40 px-4 py-3 text-sm text-red-300">Could not load cameras: {error}</div>}
      {cameras.length > 0 ? (
        <>
          <div className="max-w-md rounded-xl border border-slate-800 bg-slate-900/80 p-4 shadow-lg">
            <label className="text-xs font-medium text-slate-400">Camera to save this analysis to</label>
            <select value={selected} onChange={(e) => setSelected(e.target.value)} className="mt-2 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2.5 text-sm text-slate-200 outline-none focus:border-sky-600">
              {cameras.map((camera) => <option key={camera.id} value={camera.id}>{cameraCode(camera)} · {camera.name} — {camera.location}</option>)}
            </select>
            <p className="mt-2 text-[11px] leading-5 text-slate-600">A camera is required — every alert found needs one to belong to. If that camera has a saved restricted zone, the report will also flag intrusions into it.</p>
          </div>
          {selected && <VideoUploadAnalyzer cameraId={selected} />}
        </>
      ) : !error ? (
        <div className="rounded-xl border border-dashed border-slate-800 p-10 text-center text-sm text-slate-500">Add a camera first, then upload a video for analysis.</div>
      ) : null}
    </div>
  )
}
