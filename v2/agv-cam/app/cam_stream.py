#!/usr/bin/env python3
"""Minimal MJPEG camera server for the AGV Pi (port 8081).

One reader thread owns /dev/video0 and keeps only the newest JPEG. HTTP
clients stream that buffer, so extra viewers can never open the camera twice
or stack up latency. Endpoints:
  /               multipart MJPEG stream
  /view           HTML wrapper (Android WebView ignores a raw MJPEG document,
                  but renders it fine inside an <img>, so the app uses this)
  /snapshot.jpg   single frame, good for low-bandwidth polling
  /health         JSON status
"""
import json
import os
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import cv2

DEVICE = os.environ.get("AGV_CAM_DEVICE", "/dev/video0")
PORT = int(os.environ.get("AGV_CAM_PORT", "8081"))
WIDTH = int(os.environ.get("AGV_CAM_WIDTH", "640"))
HEIGHT = int(os.environ.get("AGV_CAM_HEIGHT", "480"))
QUALITY = int(os.environ.get("AGV_CAM_QUALITY", "70"))
TARGET_FPS = float(os.environ.get("AGV_CAM_FPS", "15"))
FOURCC = os.environ.get("AGV_CAM_FOURCC", "")
OUT_WIDTH = int(os.environ.get("AGV_CAM_OUT_WIDTH", "0") or 0)
OUT_HEIGHT = int(os.environ.get("AGV_CAM_OUT_HEIGHT", "0") or 0)


class FrameStore:
    def __init__(self):
        self.lock = threading.Lock()
        self.jpeg = None
        self.seq = 0
        self.opened_at = None
        self.error = None
        self._stop = threading.Event()

    def start(self):
        threading.Thread(target=self._loop, daemon=True).start()

    def _loop(self):
        period = 1.0 / TARGET_FPS if TARGET_FPS > 0 else 1.0 / 15.0
        while not self._stop.is_set():
            cap = cv2.VideoCapture(DEVICE, cv2.CAP_V4L2)
            if FOURCC:
                cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*FOURCC[:4].ljust(4)))
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, WIDTH)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, HEIGHT)
            cap.set(cv2.CAP_PROP_FPS, TARGET_FPS)
            if not cap.isOpened():
                self.error = "OPEN_FAIL"
                time.sleep(1.0)
                continue
            self.opened_at = time.time()
            self.error = None
            idle = 0
            while not self._stop.is_set():
                started = time.monotonic()
                ok, frame = cap.read()
                if not ok or frame is None:
                    idle += 1
                    if idle >= 10:
                        self.error = "READ_FAIL"
                        break
                    time.sleep(0.05)
                    continue
                idle = 0
                if OUT_WIDTH and OUT_HEIGHT and (frame.shape[1] != OUT_WIDTH or frame.shape[0] != OUT_HEIGHT):
                    frame = cv2.resize(frame, (OUT_WIDTH, OUT_HEIGHT), interpolation=cv2.INTER_AREA)
                ok, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), QUALITY])
                if ok:
                    with self.lock:
                        self.jpeg = buf.tobytes()
                        self.seq += 1
                left = period - (time.monotonic() - started)
                if left > 0:
                    time.sleep(left)
            cap.release()
            time.sleep(0.5)

    def latest(self):
        with self.lock:
            return self.jpeg, self.seq


STORE = FrameStore()

BRAIN_TELEMETRY = os.environ.get("AGV_BRAIN_TELEMETRY", "http://127.0.0.1:8080/api/telemetry")
_CSV_CACHE = {"at": 0.0, "text": "—,—,—,UNKNOWN"}


def telemetry_csv():
    """Compact feed for block-based clients that cannot parse JSON.

    Returns "rpm_left,rpm_right,lidar_min_m,state". Cached briefly so several
    phones polling at 2 Hz cannot hammer the brain node.
    """
    now = time.monotonic()
    if now - _CSV_CACHE["at"] < 0.5:
        return _CSV_CACHE["text"]
    try:
        with urllib.request.urlopen(BRAIN_TELEMETRY, timeout=0.8) as resp:
            data = json.loads(resp.read().decode("utf-8", "replace"))
        d0 = (data.get("control") or {}).get("latest_d0") or {}
        robot = data.get("robot") or {}
        left = d0.get("l_rpm", robot.get("l_rpm"))
        right = d0.get("r_rpm", robot.get("r_rpm"))
        lidar = data.get("min_m")
        safety = d0.get("safety") or ("ARMED" if (data.get("control") or {}).get("armed") else "DISARMED")
        if (data.get("control") or {}).get("fault"):
            safety = "FAULT"
        text = "%s,%s,%s,%s" % (
            "—" if left is None else ("%.1f" % float(left)),
            "—" if right is None else ("%.1f" % float(right)),
            "—" if lidar is None else ("%.2f" % float(lidar)),
            safety,
        )
    except Exception:
        text = _CSV_CACHE["text"]
    _CSV_CACHE["at"], _CSV_CACHE["text"] = now, text
    return text


VIEW_HTML = b"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,user-scalable=no">
<title>AGV CAMERA</title>
<style>
html,body{margin:0;height:100%;background:#07120f;color:#22d3ee;
font-family:system-ui,Arial,sans-serif;overflow:hidden}
#wrap{position:fixed;inset:0;display:flex;align-items:center;justify-content:center}
img{max-width:100%;max-height:100%;display:block}
#badge{position:fixed;top:8px;left:8px;font-size:12px;padding:4px 8px;
background:rgba(0,0,0,.55);border:1px solid #22d3ee55;border-radius:6px}
</style></head>
<body>
<div id="badge">CAMERA LIVE</div>
<div id="wrap"><img id="cam" alt="camera"></div>
<script>
var img=document.getElementById('cam');
var src='/stream';
img.onerror=function(){setTimeout(function(){img.src=src+'?t='+Date.now();},800);};
img.src=src;
document.getElementById('badge').onclick=function(){
  img.src=src+'?t='+Date.now();};
</script>
</body></html>
"""


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        pass

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-store")

    def do_GET(self):
        if self.path.startswith("/health"):
            with STORE.lock:
                body = json.dumps({
                    "ok": STORE.jpeg is not None,
                    "seq": STORE.seq,
                    "error": STORE.error,
                    "device": DEVICE,
                    "fps_target": TARGET_FPS,
                }).encode()
            self.send_response(200 if STORE.jpeg is not None else 503)
            self.send_header("Content-Type", "application/json")
            self._cors()
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if self.path.startswith("/snapshot"):
            frame, _ = STORE.latest()
            if frame is None:
                self.send_error(503, "camera not ready")
                return
            self.send_response(200)
            self.send_header("Content-Type", "image/jpeg")
            self._cors()
            self.send_header("Content-Length", str(len(frame)))
            self.end_headers()
            self.wfile.write(frame)
            return

        if self.path.startswith("/telemetry.csv"):
            body = telemetry_csv().encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self._cors()
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if self.path == "/" or self.path.startswith("/view"):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self._cors()
            self.send_header("Content-Length", str(len(VIEW_HTML)))
            self.end_headers()
            self.wfile.write(VIEW_HTML)
            return

        if not self.path.startswith("/stream"):
            self.send_error(404, "not found")
            return

        self.send_response(200)
        self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
        self._cors()
        self.end_headers()
        last = -1
        try:
            while True:
                frame, seq = STORE.latest()
                if frame is not None and seq != last:
                    last = seq
                    self.wfile.write(b"--frame\r\n")
                    self.wfile.write(b"Content-Type: image/jpeg\r\n")
                    self.wfile.write(("Content-Length: %d\r\n\r\n" % len(frame)).encode())
                    self.wfile.write(frame)
                    self.wfile.write(b"\r\n")
                time.sleep(1.0 / 120.0)
        except (BrokenPipeError, ConnectionResetError):
            return


def main():
    STORE.start()
    deadline = time.time() + 10
    while STORE.jpeg is None and time.time() < deadline:
        time.sleep(0.1)
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    server.daemon_threads = True
    print("CAM SERVER on %d device=%s ready=%s" % (PORT, DEVICE, STORE.jpeg is not None), flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
