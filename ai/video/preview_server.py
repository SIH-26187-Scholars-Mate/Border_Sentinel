"""Small OpenCV preview server with live MJPEG and still-frame endpoints."""
from collections import OrderedDict
from http import server
import threading
import time
from urllib.parse import parse_qs, urlsplit

import cv2

# How many alert-evidence snapshots to keep in memory per worker before the
# oldest ones are evicted. Evidence lives only for as long as this process
# runs (in-memory, same as the live preview) — fine for a live demo/dashboard,
# but a restart clears it. A "live" channel is exempt (always overwritten).
MAX_EVIDENCE_FRAMES = 300


class _State:
    def __init__(self):
        self.condition = threading.Condition()
        self.jpeg_by_channel = OrderedDict()


class _Handler(server.BaseHTTPRequestHandler):
    state = None

    def _channel(self, parsed):
        query = parse_qs(parsed.query)
        channel = query.get('job', ['live'])[0] or 'live'

        if channel != 'live' and len(channel) > 80:
            self.send_error(400, 'Invalid preview channel')
            return None

        return channel

    def do_GET(self):
        parsed = urlsplit(self.path)

        if parsed.path in ('/', '/health'):
            body = b'Border Sentinel camera preview OK'
            self.send_response(200)
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Content-Type', 'text/plain; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if parsed.path == '/snapshot.jpg':
            channel = self._channel(parsed)
            if channel is None:
                return

            with self.state.condition:
                jpeg = self.state.jpeg_by_channel.get(channel)

            if jpeg is None:
                self.send_error(404, 'No camera frame available')
                return

            self.send_response(200)
            self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate')
            self.send_header('Pragma', 'no-cache')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Content-Type', 'image/jpeg')
            self.send_header('Content-Length', str(len(jpeg)))
            self.end_headers()
            self.wfile.write(jpeg)
            return

        if parsed.path != '/stream.mjpg':
            self.send_error(404)
            return

        channel = self._channel(parsed)
        if channel is None:
            return

        self.send_response(200)
        self.send_header('Age', '0')
        self.send_header('Cache-Control', 'no-cache, private')
        self.send_header('Pragma', 'no-cache')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=frame')
        self.end_headers()

        try:
            while True:
                with self.state.condition:
                    jpeg = self.state.jpeg_by_channel.get(channel)
                    if jpeg is None:
                        self.state.condition.wait(timeout=1.0)
                        jpeg = self.state.jpeg_by_channel.get(channel)

                if jpeg is None:
                    continue

                self.wfile.write(b'--frame\r\n')
                self.wfile.write(b'Content-Type: image/jpeg\r\n')
                self.wfile.write(
                    f'Content-Length: {len(jpeg)}\r\n\r\n'.encode()
                )
                self.wfile.write(jpeg)
                self.wfile.write(b'\r\n')
                self.wfile.flush()
                time.sleep(0.03)

        except (BrokenPipeError, ConnectionResetError):
            pass

    def log_message(self, *_args):
        return


class PreviewServer:
    def __init__(self, host='0.0.0.0', port=8001):
        self.state = _State()
        handler = type('PreviewHandler', (_Handler,), {'state': self.state})
        self.httpd = server.ThreadingHTTPServer((host, port), handler)
        self.thread = threading.Thread(
            target=self.httpd.serve_forever,
            daemon=True,
        )

    def start(self):
        self.thread.start()

    def publish(self, frame, channel='live'):
        ok, encoded = cv2.imencode(
            '.jpg',
            frame,
            [int(cv2.IMWRITE_JPEG_QUALITY), 80],
        )

        if not ok:
            return

        with self.state.condition:
            # Evict oldest non-"live" (i.e. evidence) entries once the cap is
            # hit, so a long-running worker's memory doesn't grow forever as
            # more alerts fire. "live" is exempt — it's a single key that's
            # just overwritten every frame, never accumulates.
            if channel != 'live' and channel not in self.state.jpeg_by_channel:
                evidence_keys = [k for k in self.state.jpeg_by_channel if k != 'live']
                while len(evidence_keys) >= MAX_EVIDENCE_FRAMES:
                    oldest = evidence_keys.pop(0)
                    self.state.jpeg_by_channel.pop(oldest, None)

            self.state.jpeg_by_channel[channel] = encoded.tobytes()
            self.state.jpeg_by_channel.move_to_end(channel)
            self.state.condition.notify_all()

    def close_channel(self, channel):
        with self.state.condition:
            self.state.jpeg_by_channel.pop(channel, None)
            self.state.condition.notify_all()

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()
