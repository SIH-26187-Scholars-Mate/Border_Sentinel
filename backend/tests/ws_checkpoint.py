"""
Phase 6 checkpoint:
  1. Start two WebSocket clients connected to /ws/alerts
  2. POST a detection to /ingest/detection
  3. Assert both clients receive the broadcast within 5 s
"""
import asyncio
import json
import sys

import httpx
import websockets

BASE = "http://127.0.0.1:8000"
WS   = "ws://127.0.0.1:8000/ws/alerts"
SVC  = "placeholder-service-key"
CAM  = "00000000-0000-0000-0000-000000000099"   # fake UUID — in-memory store needs no FK

received: dict[str, dict] = {}


async def ws_client(name: str, ready: asyncio.Event, stop: asyncio.Event) -> None:
    """Connect, signal ready, then wait for one broadcast message."""
    async with websockets.connect(WS) as ws:
        ready.set()
        print(f"  [{name}] connected")
        try:
            msg = await asyncio.wait_for(ws.recv(), timeout=8)
            received[name] = json.loads(msg)
            print(f"  [{name}] received: {msg[:80]}...")
        except asyncio.TimeoutError:
            print(f"  [{name}] TIMEOUT — no message received")
        finally:
            stop.set()


async def main() -> int:
    ready1, ready2 = asyncio.Event(), asyncio.Event()
    stop  = asyncio.Event()

    # Launch both clients
    t1 = asyncio.create_task(ws_client("client-1", ready1, stop))
    t2 = asyncio.create_task(ws_client("client-2", ready2, stop))

    # Wait until both are connected
    await asyncio.gather(ready1.wait(), ready2.wait())
    print("\n  Both clients connected — posting detection...\n")

    # POST detection
    async with httpx.AsyncClient() as http:
        r = await http.post(
            f"{BASE}/ingest/detection",
            headers={"X-Service-Key": SVC},
            json={
                "camera_id": CAM,
                "alert_type": "perimeter_breach",
                "severity": "critical",
                "confidence": 0.99,
                "description": "Phase 6 WebSocket broadcast test",
            },
        )
        print(f"  POST /ingest/detection → HTTP {r.status_code}")
        assert r.status_code == 201, f"Expected 201, got {r.status_code}: {r.text}"
        posted_id = r.json()["id"]
        print(f"  Alert ID: {posted_id}")

    # Wait for both listeners to finish
    await asyncio.gather(t1, t2)

    # Verify
    print()
    ok = True
    for name in ("client-1", "client-2"):
        if name not in received:
            print(f"  FAIL: {name} did not receive anything")
            ok = False
        elif received[name].get("id") != posted_id:
            print(f"  FAIL: {name} received wrong alert id: {received[name].get('id')}")
            ok = False
        else:
            print(f"  PASS: {name} → alert_type={received[name]['alert_type']}  severity={received[name]['severity']}")

    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
