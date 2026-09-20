import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { createCamera, listCameras, updateCamera, deleteCamera } from '../api/cameras'
import { cameraCode } from '../utils/camera'

export default function Cameras() {
  const [cameras, setCameras] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [showForm, setShowForm] = useState(false)
  const [editing, setEditing] = useState(null)

  function refresh() {
    setLoading(true)
    setError(null)
    listCameras()
      .then(setCameras)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }

  useEffect(() => { refresh() }, [])

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-slate-100">Cameras</h1>
          <p className="mt-1 text-sm text-slate-500">Select a camera to open its live AI view. Previews are loaded only when requested.</p>
        </div>
        <button
          onClick={() => setShowForm((v) => !v)}
          className="rounded-lg bg-sky-600 px-4 py-2 text-sm font-medium text-white shadow-lg shadow-sky-950/30 transition hover:bg-sky-500"
        >
          {showForm ? 'Cancel' : '+ Add camera'}
        </button>
      </div>

      {showForm && <CameraForm onCreated={() => { setShowForm(false); refresh() }} />}
      {editing && <CameraForm initial={editing} edit onCreated={() => { setEditing(null); refresh() }} onCancel={() => setEditing(null)} />}

      {error && <div className="rounded-lg border border-red-900 bg-red-950/40 px-4 py-3 text-sm text-red-300">{error}</div>}

      {loading ? (
        <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-8 text-center text-sm text-slate-500">Loading camera network…</div>
      ) : (
        <>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
            {cameras.map((cam) => (
              <article key={cam.id} className="group rounded-xl border border-slate-800 bg-slate-900/80 p-5 shadow-lg shadow-black/10 transition hover:-translate-y-0.5 hover:border-slate-700">
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="rounded-md border border-slate-700 bg-slate-950 px-2 py-1 font-mono text-[11px] text-slate-400">{cameraCode(cam)}</span>
                      <span className={`flex items-center gap-1.5 text-xs ${cam.is_active ? 'text-emerald-400' : 'text-slate-500'}`}>
                        <span className={`h-2 w-2 rounded-full ${cam.is_active ? 'bg-emerald-400' : 'bg-slate-600'}`} />
                        {cam.is_active ? 'Active' : 'Offline'}
                      </span>
                    </div>
                    <h2 className="mt-3 text-base font-semibold text-slate-100">{cam.name}</h2>
                    <p className="mt-1 text-sm text-slate-500">{cam.location}</p>
                  </div>
                  <span className={`rounded-full border px-2 py-1 text-[10px] uppercase tracking-wider ${cam.ai_running ? "border-emerald-900/70 bg-emerald-950/30 text-emerald-400" : "border-slate-800 bg-slate-950 text-slate-500"}`}>AI {cam.ai_running ? "running" : "stopped"}</span>
                </div>

                <div className="mt-5 grid grid-cols-2 gap-3 text-xs">
                  <div className="rounded-lg border border-slate-800 bg-slate-950/70 p-3">
                    <div className="text-slate-600">Source</div>
                    <div className="mt-1 truncate text-slate-300">{cam.stream_url ? "RTSP / IP camera" : "Laptop webcam"}</div>
                  </div>
                  <div className="rounded-lg border border-slate-800 bg-slate-950/70 p-3">
                    <div className="text-slate-600">Live preview</div>
                    <div className="mt-1 text-emerald-400">On demand</div>
                  </div>
                </div>

                <div className="mt-5 grid grid-cols-3 gap-2"><Link
                  to={`/cameras/${cam.id}`}
                  className="mt-5 flex items-center justify-center rounded-lg border border-sky-800/80 bg-sky-950/40 px-4 py-2.5 text-sm font-medium text-sky-300 transition hover:bg-sky-900/50 hover:text-sky-200"
                >
                  View camera
                </Link><button onClick={()=>setEditing(cam)} className="rounded-lg border border-slate-700 px-3 py-2.5 text-xs text-slate-300">Edit</button><button onClick={async()=>{if(confirm('Delete this camera?')){await deleteCamera(cam.id);refresh()}}} className="rounded-lg border border-red-900/60 px-3 py-2.5 text-xs text-red-400">Delete</button></div>
              </article>
            ))}
          </div>
          {cameras.length === 0 && <div className="rounded-xl border border-dashed border-slate-800 p-10 text-center text-sm text-slate-500">No cameras yet — add one to get started.</div>}
        </>
      )}
    </div>
  )
}

function CameraForm({ onCreated, onCancel, initial, edit=false }) {
  const [form, setForm] = useState(initial ? { name: initial.name, location: initial.location, latitude: initial.latitude ?? '', longitude: initial.longitude ?? '', stream_url: initial.stream_url ?? '', is_active: initial.is_active } : { name: '', location: '', latitude: '', longitude: '', stream_url: '', is_active: true })
  const [error, setError] = useState(null)
  const [saving, setSaving] = useState(false)

  async function handleSubmit(e) {
    e.preventDefault()
    setSaving(true)
    setError(null)
    try {
      const payload = {
        name: form.name.trim(),
        location: form.location.trim(),
        latitude: form.latitude ? parseFloat(form.latitude) : undefined,
        longitude: form.longitude ? parseFloat(form.longitude) : undefined,
        stream_url: form.stream_url.trim() || undefined,
        is_active: form.is_active,
      }
      if (edit) await updateCamera(initial.id, payload); else await createCamera(payload)
      onCreated()
    } catch (err) {
      setError(err.message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="grid grid-cols-1 gap-4 rounded-xl border border-slate-800 bg-slate-900 p-5 shadow-lg sm:grid-cols-2">
      <div className="sm:col-span-2">
        <h2 className="text-sm font-semibold text-slate-200">{edit ? 'Edit camera' : 'Register camera'}</h2>
        <p className="mt-1 text-xs text-slate-500">Enter an RTSP URL for an IP camera. Saving automatically starts its AI worker; leave it blank to use the laptop webcam.</p>
      </div>
      {error && <div className="sm:col-span-2 rounded-lg border border-red-900 bg-red-950/40 px-3 py-2 text-sm text-red-300">{error}</div>}
      <Field label="Camera name" value={form.name} onChange={(v) => setForm({ ...form, name: v })} required />
      <Field label="Location" value={form.location} onChange={(v) => setForm({ ...form, location: v })} required />
      <Field label="Latitude" value={form.latitude} onChange={(v) => setForm({ ...form, latitude: v })} />
      <Field label="Longitude" value={form.longitude} onChange={(v) => setForm({ ...form, longitude: v })} />
      <div className="sm:col-span-2"><Field label="RTSP / Stream URL" placeholder="rtsp://192.168.1.100:554/stream1" value={form.stream_url} onChange={(v) => setForm({ ...form, stream_url: v })} /><p className="mt-1.5 text-[11px] text-slate-600">Example: rtsp://username:password@192.168.1.100:554/stream1</p></div>
      <label className="flex items-center gap-2 text-xs text-slate-400"><input type="checkbox" checked={form.is_active} onChange={e=>setForm({...form,is_active:e.target.checked})}/> Camera active</label>
      <div className="sm:col-span-2 flex gap-2">
        <button type="submit" disabled={saving} className="rounded-lg bg-sky-600 px-4 py-2 text-sm font-medium text-white hover:bg-sky-500 disabled:opacity-50">{saving ? 'Saving…' : edit ? 'Save changes' : 'Create camera'}</button>{edit&&<button type="button" onClick={onCancel} className="rounded-lg border border-slate-700 px-4 py-2 text-sm">Cancel</button>}
      </div>
    </form>
  )
}

function Field({ label, value, onChange, required = false, placeholder = "" }) {
  return (
    <label className="space-y-1.5 text-xs text-slate-400">
      <span>{label}</span>
      <input value={value} placeholder={placeholder} required={required} onChange={(e) => onChange(e.target.value)} className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2.5 text-sm text-slate-100 outline-none transition focus:border-sky-500" />
    </label>
  )
}
