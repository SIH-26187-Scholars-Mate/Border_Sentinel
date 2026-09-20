"""
app/websocket/alerts_ws.py
WebSocket endpoint: ws://host/ws/alerts

Clients connect here to receive real-time alert broadcasts.
The server keeps the connection open; the client can also send
text (e.g. a ping) which is simply echoed back.

Authentication note: for the initial implementation auth is
intentionally omitted to keep latency low. In production, pass
a JWT as a query parameter and verify it on connect before
calling ws_manager.connect().
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.websocket.manager import ws_manager

router = APIRouter(tags=["websocket"])


@router.websocket("/ws/alerts")
async def alerts_websocket(websocket: WebSocket) -> None:
    await ws_manager.connect(websocket)
    try:
        while True:
            # Keep the connection alive; handle any client pings
            data = await websocket.receive_text()
            # Echo back (useful for client-side keepalive pings)
            await websocket.send_text(data)
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
