// src/hooks/useAlertsSocket.js
// Connects to backend's real ws://.../ws/alerts endpoint (see
// backend/app/websocket/alerts_ws.py). No auth on this endpoint yet per
// backend's own code comment — don't assume it's protected.
import { useEffect, useRef, useState } from 'react'
import { BACKEND_URL } from '../api/client'

function wsUrl() {
  return BACKEND_URL.replace(/^http/, 'ws') + '/ws/alerts'
}

export function useAlertsSocket() {
  const [alerts, setAlerts] = useState([])
  const [connected, setConnected] = useState(false)
  const wsRef = useRef(null)
  const reconnectTimer = useRef(null)

  useEffect(() => {
    let cancelled = false

    function connect() {
      const ws = new WebSocket(wsUrl())
      wsRef.current = ws

      ws.onopen = () => {
        if (cancelled) return
        setConnected(true)
      }

      ws.onmessage = (event) => {
        if (cancelled) return
        try {
          const alert = JSON.parse(event.data)
          // Ignore anything that isn't a real alert payload (e.g. an echoed
          // keepalive ping — see alerts_ws.py, it echoes plain text back).
          if (alert && alert.id && alert.alert_type) {
            setAlerts((prev) => [alert, ...prev].slice(0, 200))
          }
        } catch {
          // not JSON — likely an echoed ping, ignore
        }
      }

      ws.onclose = () => {
        if (cancelled) return
        setConnected(false)
        reconnectTimer.current = setTimeout(connect, 2000)
      }

      ws.onerror = () => {
        ws.close()
      }
    }

    connect()

    return () => {
      cancelled = true
      clearTimeout(reconnectTimer.current)
      wsRef.current?.close()
    }
  }, [])

  return { alerts, connected }
}
