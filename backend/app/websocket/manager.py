"""
app/websocket/manager.py
Singleton WebSocket connection manager.

All live clients connect here via /ws/alerts.
alert_service (or ingest route) calls ws_manager.broadcast() to push
a JSON alert to every connected client simultaneously.
"""
from fastapi import WebSocket


class ConnectionManager:
    def __init__(self) -> None:
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        """Accept handshake and register the client."""
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        """Remove a client (on disconnect or send error)."""
        try:
            self.active_connections.remove(websocket)
        except ValueError:
            pass  # already removed — safe to ignore

    async def broadcast(self, message: str) -> None:
        """
        Send a text message to every connected client.
        Stale connections that raise on send are silently removed.
        """
        stale: list[WebSocket] = []
        for ws in list(self.active_connections):
            try:
                await ws.send_text(message)
            except Exception:
                stale.append(ws)
        for ws in stale:
            self.disconnect(ws)


# Module-level singleton — imported by both alerts_ws.py and ingest.py
ws_manager = ConnectionManager()
