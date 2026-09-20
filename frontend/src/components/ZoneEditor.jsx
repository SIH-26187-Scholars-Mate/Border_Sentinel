import { useEffect, useMemo, useRef, useState } from 'react'
import { createZone, deleteZone, listZones, updateZone } from '../api/zones'

// Fence points are stored as normalized coordinates (0..1), so they remain
// independent of the camera's native resolution.
const DESIGN_WIDTH = 1280
const DESIGN_HEIGHT = 720
const CLOSE_RADIUS = 0.022

function clamp(value, min = 0, max = 1) {
  return Math.max(min, Math.min(max, value))
}

function normalizePoint(point) {
  // Convert older 1280x720 zones so they remain editable.
  if (Number(point.x) > 1 || Number(point.y) > 1) {
    return {
      x: clamp(Number(point.x) / DESIGN_WIDTH),
      y: clamp(Number(point.y) / DESIGN_HEIGHT),
    }
  }
  return {
    x: clamp(Number(point.x)),
    y: clamp(Number(point.y)),
  }
}

function displayPoint(point) {
  return {
    x: point.x * DESIGN_WIDTH,
    y: point.y * DESIGN_HEIGHT,
  }
}

function getPreviewPort(camera) {
  return camera?.preview_port || 8101
}

function getSnapshotUrl(camera, attempt = 0) {
  const port = getPreviewPort(camera)
  const channel = encodeURIComponent(camera?.id || 'live')
  const cacheBust = attempt ? `&t=${attempt}` : ''
  return `${window.location.protocol}//${window.location.hostname}:${port}/snapshot.jpg?job=${channel}${cacheBust}`
}

export default function ZoneEditor({ cameraId, camera }) {
  const ref = useRef(null)
  const dragIndex = useRef(null)
  const dragged = useRef(false)

  const [points, setPoints] = useState([])
  const [closed, setClosed] = useState(false)
  const [editingId, setEditingId] = useState(null)
  const [zones, setZones] = useState([])
  const [name, setName] = useState('Restricted Zone')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)

  const [frameUrl, setFrameUrl] = useState(null)
  const [capturing, setCapturing] = useState(false)
  const [frameError, setFrameError] = useState(null)
  const [frameReady, setFrameReady] = useState(false)

  useEffect(() => {
    listZones(cameraId)
      .then((items) => setZones(items))
      .catch((e) => setError(e.message))
  }, [cameraId])

  useEffect(() => {
    return () => {
      if (frameUrl) URL.revokeObjectURL(frameUrl)
    }
  }, [frameUrl])

  async function captureFrame() {
    setCapturing(true)
    setFrameError(null)
    setFrameReady(false)

    try {
      const response = await fetch(getSnapshotUrl(camera, Date.now()), {
        cache: 'no-store',
      })

      if (!response.ok) {
        throw new Error(`Camera snapshot failed (${response.status})`)
      }

      const blob = await response.blob()
      const nextUrl = URL.createObjectURL(blob)

      setFrameUrl((oldUrl) => {
        if (oldUrl) URL.revokeObjectURL(oldUrl)
        return nextUrl
      })
    } catch (e) {
      setFrameError(
        `${e.message}. Start the AI camera first, then try Capture frame again.`
      )
    } finally {
      setCapturing(false)
    }
  }

  function toNormalized(clientX, clientY) {
    const r = ref.current.getBoundingClientRect()

    return {
      x: clamp((clientX - r.left) / r.width),
      y: clamp((clientY - r.top) / r.height),
    }
  }

  function addPoint(e) {
    if (!frameReady || closed || dragIndex.current !== null) return

    const p = toNormalized(e.clientX, e.clientY)

    if (points.length >= 3) {
      const first = points[0]
      const dist = Math.hypot(p.x - first.x, p.y - first.y)

      if (dist <= CLOSE_RADIUS) {
        setClosed(true)
        return
      }
    }

    setPoints((prev) => [...prev, p])
  }

  function startDrag(e, index) {
    if (!frameReady) return

    e.stopPropagation()
    e.preventDefault()

    dragIndex.current = index
    dragged.current = false
    e.currentTarget.setPointerCapture?.(e.pointerId)
  }

  function dragPoint(e) {
    const index = dragIndex.current
    if (index === null || !frameReady) return

    e.preventDefault()
    dragged.current = true

    const p = toNormalized(e.clientX, e.clientY)

    setPoints((prev) =>
      prev.map((point, i) => (i === index ? p : point))
    )
  }

  function finishDrag(e) {
    if (dragIndex.current === null) return

    e.stopPropagation()
    dragIndex.current = null
  }

  function clickPoint(e, index) {
    e.stopPropagation()

    if (
      !dragged.current &&
      !closed &&
      index === 0 &&
      points.length >= 3
    ) {
      setClosed(true)
    }

    dragged.current = false
  }

  function closeShapeManually() {
    if (points.length >= 3) setClosed(true)
  }

  function reset() {
    setPoints([])
    setClosed(false)
    setEditingId(null)
  }

  function editExisting(z) {
    setPoints((z.points || []).map(normalizePoint))
    setClosed(true)
    setName(z.name)
    setEditingId(z.id)
  }

  async function save() {
    if (points.length < 3 || !closed) return

    setSaving(true)
    setError(null)

    try {
      const payload = {
        name,
        points: points.map((p) => ({
          x: Number(p.x.toFixed(6)),
          y: Number(p.y.toFixed(6)),
        })),
        enabled: true,
        trigger_object: 'person',
      }

      if (editingId) {
        const z = await updateZone(cameraId, editingId, payload)
        setZones((zs) => zs.map((x) => (x.id === editingId ? z : x)))
      } else {
        const z = await createZone(cameraId, payload)
        setZones((zs) => [...zs, z])
      }

      reset()
    } catch (e) {
      setError(e.message)
    } finally {
      setSaving(false)
    }
  }

  const canClose = !closed && points.length >= 3
  const canSave = closed && points.length >= 3
  const svgPoints = points.map(displayPoint)

  return (
    <section className="rounded-xl border border-slate-800 bg-slate-900 shadow-lg">
      <div className="border-b border-slate-800 p-4">
        <h2 className="text-sm font-semibold text-slate-200">
          Virtual fence / restricted zone
        </h2>

        <p className="mt-1 text-xs text-slate-500">
          Capture a camera frame, then draw the restricted zone directly on
          the captured image. This gives the operator a real visual reference
          instead of having to guess the fence location.
        </p>
      </div>

      <div className="p-4">
        <div
          ref={ref}
          onClick={addPoint}
          className="relative aspect-video cursor-crosshair touch-none overflow-hidden rounded-lg border border-slate-800 bg-black"
        >
          {frameUrl ? (
            <img
              src={frameUrl}
              alt="Captured camera frame for virtual fence"
              className="absolute inset-0 h-full w-full object-contain"
              onLoad={() => setFrameReady(true)}
              onError={() => setFrameReady(false)}
            />
          ) : (
            <div className="absolute inset-0 flex items-center justify-center bg-[linear-gradient(135deg,#0f172a,#020617)]">
              <div className="max-w-md px-6 text-center">
                <p className="text-sm font-medium text-slate-200">
                  No reference frame captured
                </p>
                <p className="mt-2 text-xs leading-5 text-slate-500">
                  Start the AI camera, then capture a frame to see the actual
                  camera view while drawing the fence.
                </p>
              </div>
            </div>
          )}

          <svg
            className="pointer-events-none absolute inset-0 h-full w-full"
            viewBox={`0 0 ${DESIGN_WIDTH} ${DESIGN_HEIGHT}`}
            preserveAspectRatio="none"
          >
            {closed ? (
              <polygon
                points={svgPoints.map((p) => `${p.x},${p.y}`).join(' ')}
                fill="rgba(239,68,68,.12)"
                stroke="rgba(248,113,113,.9)"
                strokeWidth="4"
              />
            ) : (
              <polyline
                points={svgPoints.map((p) => `${p.x},${p.y}`).join(' ')}
                fill="none"
                stroke="rgba(248,113,113,.9)"
                strokeWidth="4"
              />
            )}

            {svgPoints.map((p, i) => (
              <circle
                key={i}
                cx={p.x}
                cy={p.y}
                r={i === 0 && !closed && points.length >= 3 ? 14 : 10}
                fill={
                  i === 0 && !closed && points.length >= 3
                    ? 'rgba(74,222,128,.95)'
                    : 'white'
                }
                stroke="rgba(15,23,42,.9)"
                strokeWidth="3"
                className={
                  !closed
                    ? 'pointer-events-auto cursor-grab active:cursor-grabbing'
                    : 'pointer-events-auto cursor-grab active:cursor-grabbing'
                }
                onPointerDown={(e) => startDrag(e, i)}
                onPointerMove={dragPoint}
                onPointerUp={finishDrag}
                onPointerCancel={finishDrag}
                onClick={(e) => clickPoint(e, i)}
              >
                <title>
                  {closed
                    ? 'Fence point'
                    : 'Drag to adjust this point'}
                </title>
              </circle>
            ))}
          </svg>

          <div className="pointer-events-none absolute left-3 top-3 rounded bg-black/70 px-2 py-1 text-[10px] text-slate-300">
            {!frameUrl
              ? 'Capture a frame to begin'
              : !frameReady
                ? 'Loading frame…'
                : closed
                  ? `${points.length}-point zone · drag points to adjust`
                  : `Click to place points · ${points.length} so far${
                      points.length >= 3
                        ? ' · click the green point to close'
                        : ''
                    }`}
          </div>
        </div>

        <div className="mt-3 flex flex-wrap gap-2">
          <button
            onClick={captureFrame}
            disabled={capturing}
            className="rounded-lg border border-sky-700 bg-sky-950/30 px-4 py-2 text-sm text-sky-300 disabled:opacity-40"
          >
            {capturing
              ? 'Capturing…'
              : frameUrl
                ? 'Refresh frame'
                : 'Capture frame'}
          </button>

          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm"
          />

          <button
            onClick={closeShapeManually}
            disabled={!canClose}
            className="rounded-lg border border-emerald-700 px-4 py-2 text-sm text-emerald-300 disabled:opacity-40"
          >
            Close shape
          </button>

          <button
            onClick={save}
            disabled={!canSave || saving}
            className="rounded-lg bg-red-600 px-4 py-2 text-sm disabled:opacity-40"
          >
            {saving ? 'Saving…' : editingId ? 'Update zone' : 'Save zone'}
          </button>

          <button
            onClick={reset}
            className="rounded-lg border border-slate-700 px-4 py-2 text-sm"
          >
            {editingId ? 'Cancel edit' : 'Clear'}
          </button>
        </div>

        {frameError && (
          <p className="mt-2 text-xs text-amber-300">
            {frameError}
          </p>
        )}

        {error && (
          <p className="mt-2 text-xs text-red-300">
            {error}
          </p>
        )}

        <div className="mt-4 space-y-2">
          {zones.map((z) => (
            <div
              key={z.id}
              className="flex items-center justify-between rounded-lg border border-slate-800 bg-slate-950 p-3 text-xs"
            >
              <span>
                <b className="text-slate-200">{z.name}</b>
                <span className="ml-2 text-slate-500">
                  {z.points.length} points · {z.trigger_object} entry
                </span>
              </span>

              <span className="flex gap-3">
                <button
                  onClick={() => editExisting(z)}
                  className="text-slate-300"
                >
                  Edit
                </button>

                <button
                  onClick={async () => {
                    await deleteZone(cameraId, z.id)
                    setZones((zs) => zs.filter((x) => x.id !== z.id))

                    if (editingId === z.id) reset()
                  }}
                  className="text-red-400"
                >
                  Delete
                </button>
              </span>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}
