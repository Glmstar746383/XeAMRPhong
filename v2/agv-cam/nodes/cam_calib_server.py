#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Camera viewer + floor distance calibration for AGV.

Chay tren Pi:
    python3 cam_calib_server.py --device /dev/video0 --port 8090

Mo tren laptop:
    http://<ip-pi>:8090/

Tinh nang:
  - Xem camera truc tiep (MJPEG), do phan giai that cua khung hinh
  - Click de lay toa do pixel
  - Hieu chuan homography: click 4 diem tren san, nhap toa do met that
  - Sau khi hieu chuan: click bat ky dau -> ra toa do (X,Y) va khoang cach
  - Ve luoi met len anh de doi chieu bang thuoc day
  - Luu / tai cau hinh tai ~/camera_calib.json
"""
import argparse
import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# uu tien backend V4L2, tat GStreamer/MSMF gay warning
os.environ.setdefault("OPENCV_VIDEOIO_PRIORITY_GSTREAMER", "0")
os.environ.setdefault("OPENCV_VIDEOIO_PRIORITY_MSMF", "0")

import cv2
import numpy as np

CALIB_PATH = os.path.expanduser("~/camera_calib.json")
BG_PATH = os.path.expanduser("~/floor_ref.jpg")
LOCK = threading.Lock()
STATE = {"jpeg": None, "w": 0, "h": 0, "seq": 0, "fps": 0.0, "err": "", "device": ""}


def load_calib():
    try:
        with open(CALIB_PATH, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return {}


def write_calib(data):
    with open(CALIB_PATH, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)


def save_calib(data):
    try:
        prev = int(load_calib().get("count", 0))
    except Exception:
        prev = 0
    data["count"] = prev + 1
    write_calib(data)
    return data["count"]


def open_capture(dev, width, height, fps):
    """Thu lan luot nhieu backend, tra ve (cap, ten_backend)."""
    idx = None
    if dev.startswith("/dev/video"):
        try:
            idx = int(dev[len("/dev/video"):])
        except ValueError:
            idx = None

    gst_raw = ("v4l2src device=%s ! video/x-raw,width=%d,height=%d,framerate=%d/1 "
               "! videoconvert ! appsink" % (dev, width, height, max(1, fps)))
    gst_mjpg = ("v4l2src device=%s ! image/jpeg,width=%d,height=%d,framerate=%d/1 "
                "! jpegdec ! videoconvert ! appsink" % (dev, width, height, max(1, fps)))

    attempts = []
    if idx is not None:
        attempts.append(("v4l2-index", idx, cv2.CAP_V4L2))
    attempts.append(("v4l2-path", dev, cv2.CAP_V4L2))
    attempts.append(("gst-mjpg", gst_mjpg, cv2.CAP_GSTREAMER))
    attempts.append(("gst-raw", gst_raw, cv2.CAP_GSTREAMER))
    attempts.append(("default", dev, cv2.CAP_ANY))

    for name, src, api in attempts:
        try:
            cap = cv2.VideoCapture(src, api)
        except Exception:
            continue
        if not cap.isOpened():
            cap.release()
            continue
        if "gst" not in name:
            cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        ok, frame = cap.read()
        if ok and frame is not None:
            return cap, name
        cap.release()
    return None, None


def source_loop(url, quality, fps_target):
    """Doc khung hinh tu MJPEG/snapshot co san, khong mo /dev/video thêm lan nua."""
    import urllib.request
    period = 1.0 / max(1.0, float(fps_target))
    last_t = time.time()
    while True:
        t0 = time.time()
        try:
            with urllib.request.urlopen(url, timeout=5) as resp:
                raw = resp.read()
            frame = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
            if frame is None:
                raise ValueError("jpeg khong hop le")
            ok, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), int(quality)])
            if not ok:
                raise ValueError("encode loi")
            now = time.time()
            dt = max(1e-3, now - last_t)
            last_t = now
            with LOCK:
                STATE["jpeg"] = buf.tobytes()
                STATE["h"], STATE["w"] = frame.shape[:2]
                STATE["seq"] += 1
                STATE["fps"] = (1.0 / dt) if STATE["fps"] == 0 else (0.9 * STATE["fps"] + 0.1 / dt)
                STATE["err"] = ""
        except Exception as exc:
            with LOCK:
                STATE["err"] = "source: %s" % exc
        rest = period - (time.time() - t0)
        if rest > 0:
            time.sleep(rest)


def cam_loop(cap, quality, label):
    real_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    real_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    with LOCK:
        STATE["w"], STATE["h"], STATE["device"] = real_w, real_h, label

    last_t = time.time()
    while True:
        ok, frame = cap.read()
        if not ok or frame is None:
            with LOCK:
                STATE["err"] = "khong doc duoc khung hinh"
            time.sleep(0.05)
            continue
        params = [int(cv2.IMWRITE_JPEG_QUALITY), int(quality)]
        ok, buf = cv2.imencode(".jpg", frame, params)
        if not ok:
            continue
        now = time.time()
        dt = max(1e-3, now - last_t)
        last_t = now
        with LOCK:
            STATE["jpeg"] = buf.tobytes()
            STATE["h"], STATE["w"] = frame.shape[:2]
            STATE["seq"] += 1
            STATE["fps"] = (1.0 / dt) if STATE["fps"] == 0 else (0.9 * STATE["fps"] + 0.1 / dt)
            STATE["err"] = ""


PAGE = r"""<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Camera - Hieu chuan khoang cach</title>
<style>
  :root { color-scheme: dark; }
  * { box-sizing: border-box; }
  body { margin:0; font-family: system-ui, "Segoe UI", sans-serif; background:#0b1120; color:#e2e8f0; }
  header { padding:10px 16px; background:#111a2e; border-bottom:1px solid #22304a;
           display:flex; gap:16px; align-items:center; flex-wrap:wrap; font-size:13px; }
  header b { color:#38bdf8; }
  main { display:grid; grid-template-columns: minmax(0,1fr) 390px; gap:12px; padding:12px; align-items:start; }
  @media (max-width: 1050px) { main { grid-template-columns: 1fr; } }
  .stage { background:#000; border:1px solid #22304a; border-radius:10px; overflow:hidden; position:relative; }
  .stage .tag { position:absolute; top:8px; left:10px; font-size:11px; letter-spacing:1px;
                color:#38bdf8; background:rgba(11,17,32,.72); padding:2px 8px; border-radius:6px;
                border:1px solid #22304a; z-index:2; }
  #wrap { position:relative; background:#000; width:100%; }
  #vid { display:block; width:100%; height:auto; }
  #ov  { position:absolute; inset:0; width:100%; height:100%; cursor:crosshair; }
  .side { display:flex; flex-direction:column; gap:12px; }
  .card { background:#111a2e; border:1px solid #22304a; border-radius:10px; padding:12px 14px; }
  .card h3 { margin:0 0 8px; font-size:12px; color:#7dd3fc; letter-spacing:.6px; text-transform:uppercase; }
  button { background:#1d4ed8; border:0; color:#fff; padding:7px 12px; border-radius:7px;
           font-size:13px; cursor:pointer; }
  button.alt { background:#334155; }
  button:disabled { opacity:.45; cursor:not-allowed; }
  input[type=number] { width:70px; background:#0b1120; border:1px solid #334155; color:#e2e8f0;
                       padding:4px 6px; border-radius:6px; font-size:13px; }
  table { border-collapse:collapse; font-size:13px; width:100%; }
  td { padding:3px 6px 3px 0; }
  code { color:#fbbf24; }
  .row { display:flex; gap:8px; align-items:center; margin:6px 0; flex-wrap:wrap; }
  .muted { color:#94a3b8; font-size:12px; }
  .big { font-size:19px; color:#4ade80; font-weight:600; }
  .stat { display:flex; justify-content:space-between; gap:10px; font-size:13px; padding:4px 0;
          border-bottom:1px dashed #1e293b; }
  .stat b { color:#e2e8f0; font-weight:600; }
  .ok  { color:#4ade80; } .warn { color:#fbbf24; } .bad { color:#f87171; }
  .hmat { font-family: ui-monospace, Consolas, monospace; font-size:11px; color:#94a3b8;
          line-height:1.6; white-space:pre; margin-top:6px; }
</style>
</head>
<body>
<header>
  <span>Camera: <b id="info">dang ket noi...</b></span>
  <span>FPS: <b id="fps">-</b></span>
  <span>Pixel: <b id="px">-</b></span>
  <span id="err" style="color:#f87171"></span>
  <button id="fs" class="alt" style="margin-left:auto">Toan man hinh</button>
</header>

<main>
  <section class="stage">
    <span class="tag">TEST CAMERA</span>
    <div id="wrap">
      <img id="vid" src="/stream.mjpg" alt="camera">
      <canvas id="ov"></canvas>
    </div>
  </section>

  <aside class="side">
    <div class="card">
      <h3>1 &middot; Hieu chuan</h3>
      <div class="stat"><span>Trang thai</span><b id="stStatus" class="bad">chua hieu chuan</b></div>
      <div class="stat"><span>So lan hieu chuan</span><b id="stCount">0</b></div>
      <div class="stat"><span>Lan cuoi</span><b id="stTime">-</b></div>
      <div class="stat"><span>Sai so 4 moc</span><b id="stErr">-</b></div>

      <div class="row" style="margin-top:10px">
        <button id="mCalib" class="alt">Che do hieu chuan</button>
        <button id="mMeasure">Che do do</button>
      </div>
      <div class="row">
        <button id="presetFront" class="alt">Mau gan 0.5-1m</button>
        <button id="presetTop" class="alt">Mau nhin xuong</button>
      </div>
      <table id="pts"></table>
      <div class="row">
        <button id="apply" disabled>Tinh H &amp; luu</button>
        <button id="reset" class="alt">Xoa diem</button>
      </div>
      <div class="muted" id="calibState">Click 4 moc tren anh theo thu tu 1 &rarr; 2 &rarr; 3 &rarr; 4</div>
      <details style="margin-top:8px">
        <summary class="muted" style="cursor:pointer">Gia tri H (3x3)</summary>
        <div class="hmat" id="hmat">-</div>
      </details>
    </div>

    <div class="card">
      <h3>2 &middot; Ket qua do</h3>
      <div class="stat"><span>X (ngang)</span><b id="wx">-</b></div>
      <div class="stat"><span>Y (toi truoc)</span><b id="wy">-</b></div>
      <div class="stat"><span>Khoang cach (mo hinh)</span><b id="wd" class="big">-</b></div>
      <div class="stat"><span>Khoang cach cheo (H)</span><b id="wdh">-</b></div>
      <div class="row" style="margin-top:10px">
        <button id="p1" class="alt">Diem A</button>
        <button id="p2" class="alt">Diem B</button>
        <span id="ab" class="big">-</span>
      </div>
      <div class="muted">Click chan vat can de do. Dung A/B de do be ngang.</div>
    </div>

    <div class="card">
      <h3>3 &middot; Hieu chuan nhieu khoang cach</h3>
      <div class="muted">Giữ nguyên một điểm trên mốc. Click điểm đó, nhập khoảng cách thật, bấm Ghi mẫu. Lặp lại ở nhiều khoảng cách.</div>
      <div class="stat"><span>Diem dang chon</span><b id="curPt">-</b></div>
      <div class="row">
        <input type="number" id="realD" value="0.5" step="0.05" min="0.1"> m
        <button id="addSample">Ghi mau</button>
        <button id="clearSamples" class="alt">Xoa het</button>
      </div>
      <table id="samples"></table>
      <div class="row">
        <button id="fitModel">Tinh mo hinh</button>
        <a id="download" href="/calib.json" download="camera_calib.json"><button class="alt">Xuat file</button></a>
      </div>
      <div class="stat"><span>Mo hinh</span><b id="mdlState">chua co</b></div>
      <div class="stat"><span>A = f&middot;h</span><b id="mA">-</b></div>
      <div class="stat"><span>v0 (duong chan troi)</span><b id="mv0">-</b></div>
      <div class="stat"><span>Sai so RMS</span><b id="mRms">-</b></div>
    </div>

    <div class="card">
      <h3>4 &middot; Lop phu</h3>
      <div class="row"><label><input type="checkbox" id="grid" checked> Luoi met</label></div>
      <div class="row"><label><input type="checkbox" id="cross" checked> Tam ngam</label></div>
      <div class="row">
        <span class="muted">Do dam luoi</span>
        <input type="number" id="step" value="0.5" step="0.1" min="0.1" max="5"> m
      </div>
    </div>
  </aside>
</main>

<script>
const vid = document.getElementById('vid');
const cv  = document.getElementById('ov');
const ctx = cv.getContext('2d');
const $ = id => document.getElementById(id);

let W = 0, H = 0;          // kich thuoc that cua khung hinh
let Hmat = null;           // homography pixel -> met
let mode = 'measure';      // 'measure' | 'calib'
let calibPts = [];         // 4 diem pixel
let worldPts = [[0,0],[1,0],[1,1],[0,1]];   // toa do met mac dinh: hinh vuong 1m
let lastPt = null;
let ptA = null, ptB = null;
let samples = [];        // [{d, u, v}]
let rangeModel = null;   // {A, v0, rms, n}

vid.addEventListener('load', () => {
  if (vid.naturalWidth) { W = vid.naturalWidth; H = vid.naturalHeight; syncCanvas(); }
});
setInterval(() => {
  if (vid.naturalWidth && (vid.naturalWidth !== W || vid.naturalHeight !== H)) {
    W = vid.naturalWidth; H = vid.naturalHeight; syncCanvas();
  }
}, 500);

function syncCanvas() {
  cv.width = W; cv.height = H;
  $('info').textContent = W + ' x ' + H;
  draw();
}

// ---------- toa do ----------
function toNative(ev) {
  const r = cv.getBoundingClientRect();
  return [
    (ev.clientX - r.left) * (cv.width  / r.width),
    (ev.clientY - r.top ) * (cv.height / r.height)
  ];
}

// ---------- homography ----------
function gauss(A, b) {
  const n = b.length;
  for (let i = 0; i < n; i++) {
    let p = i;
    for (let r = i + 1; r < n; r++) if (Math.abs(A[r][i]) > Math.abs(A[p][i])) p = r;
    [A[i], A[p]] = [A[p], A[i]];
    [b[i], b[p]] = [b[p], b[i]];
    const d = A[i][i];
    if (Math.abs(d) < 1e-12) throw new Error('suy bien');
    for (let c = i; c < n; c++) A[i][c] /= d;
    b[i] /= d;
    for (let r = 0; r < n; r++) {
      if (r === i) continue;
      const f = A[r][i];
      if (!f) continue;
      for (let c = i; c < n; c++) A[r][c] -= f * A[i][c];
      b[r] -= f * b[i];
    }
  }
  return b;
}

function solveH(src, dst) {
  const A = [], b = [];
  for (let i = 0; i < 4; i++) {
    const [u, v] = src[i], [X, Y] = dst[i];
    A.push([u, v, 1, 0, 0, 0, -X * u, -X * v]); b.push(X);
    A.push([0, 0, 0, u, v, 1, -Y * u, -Y * v]); b.push(Y);
  }
  const h = gauss(A, b);
  return [h[0], h[1], h[2], h[3], h[4], h[5], h[6], h[7], 1];
}

function applyH(h, u, v) {
  const d = h[6] * u + h[7] * v + h[8];
  return [(h[0] * u + h[1] * v + h[2]) / d, (h[3] * u + h[4] * v + h[5]) / d];
}

function inv3(m) {
  const [a, b, c, d, e, f, g, h, i] = m;
  const A = e * i - f * h, B = c * h - b * i, C = b * f - c * e;
  const D = f * g - d * i, E = a * i - c * g, F = c * d - a * f;
  const G = d * h - e * g, Hh = b * g - a * h, I = a * e - b * d;
  const det = a * A + b * D + c * G;
  return [A / det, B / det, C / det, D / det, E / det, F / det, G / det, Hh / det, I / det];
}

// ---------- thong ke hieu chuan ----------
let calibInfo = {};

function calibError(h, src, dst) {
  if (!h || !src || !dst || src.length !== 4 || dst.length !== 4) return null;
  let s = 0;
  for (let i = 0; i < 4; i++) {
    const [X, Y] = applyH(h, src[i][0], src[i][1]);
    s += (X - dst[i][0]) * (X - dst[i][0]) + (Y - dst[i][1]) * (Y - dst[i][1]);
  }
  return Math.sqrt(s / 4);
}

function updateStats() {
  const has = !!Hmat;
  const st = $('stStatus');
  st.textContent = has ? 'da hieu chuan' : 'chua hieu chuan';
  st.className = has ? 'ok' : 'bad';

  $('stCount').textContent = calibInfo.count || (has ? 1 : 0);
  $('stTime').textContent = calibInfo.saved_at || '-';

  const e = has ? calibError(Hmat, calibInfo.src, calibInfo.dst) : null;
  const el = $('stErr');
  if (e === null) {
    el.textContent = '-';
    el.className = '';
  } else {
    el.textContent = (e * 100).toFixed(1) + ' cm';
    el.className = e < 0.03 ? 'ok' : (e < 0.10 ? 'warn' : 'bad');
  }

  $('hmat').textContent = has
    ? Hmat.map((v, i) => v.toFixed(4) + ((i % 3 === 2) ? '\n' : '  ')).join('')
    : '-';
}

// ---------- hieu chuan nhieu khoang cach ----------
function modelDistance(v) {
  if (!rangeModel) return null;
  const den = v - rangeModel.v0;
  if (!(den > 0.5)) return null;
  return rangeModel.A / den;
}

function renderSamples() {
  const t = $('samples');
  if (!samples.length) {
    t.innerHTML = '<tr><td class="muted">chua co mau nao</td></tr>';
    return;
  }
  let html = '<tr><td class="muted">#</td><td class="muted">d that</td><td class="muted">v px</td><td class="muted">d tinh</td><td class="muted">loi</td></tr>';
  samples.forEach((s, i) => {
    const calc = modelDistance(s.v);
    const err = calc === null ? '-' : ((calc - s.d) * 100).toFixed(1) + ' cm';
    html += '<tr><td>' + (i + 1) + '</td><td>' + s.d.toFixed(2) + '</td><td>' +
            s.v.toFixed(0) + '</td><td>' + (calc === null ? '-' : calc.toFixed(3)) +
            '</td><td>' + err + '</td></tr>';
  });
  t.innerHTML = html;
}

function updateModel() {
  const st = $('mdlState');
  if (!rangeModel) {
    st.textContent = 'chua co';
    st.className = 'bad';
    $('mA').textContent = '-';
    $('mv0').textContent = '-';
    $('mRms').textContent = '-';
    return;
  }
  st.textContent = 'da tinh (' + rangeModel.n + ' mau)';
  st.className = 'ok';
  $('mA').textContent = rangeModel.A.toFixed(1);
  $('mv0').textContent = rangeModel.v0.toFixed(1);
  const rr = $('mRms');
  rr.textContent = (rangeModel.rms * 100).toFixed(1) + ' cm';
  rr.className = rangeModel.rms < 0.03 ? 'ok' : (rangeModel.rms < 0.10 ? 'warn' : 'bad');
}

async function saveRange() {
  try {
    await fetch('/api/range', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ samples: samples, model: rangeModel })
    });
  } catch (e) {}
}

$('addSample').onclick = () => {
  if (!lastPt) {
    $('calibState').textContent = 'hay click 1 diem tren anh truoc';
    return;
  }
  const d = parseFloat($('realD').value);
  if (!(d > 0)) return;
  samples.push({ d: d, u: lastPt[0], v: lastPt[1] });
  renderSamples();
  lastPt = null;
  $('curPt').textContent = '-';
  $('calibState').textContent =
    'da ghi mau ' + samples.length + ' (d=' + d + ' m). Hay click diem moc o khoang cach moi.';
  draw();
};

$('clearSamples').onclick = async () => {
  samples = [];
  rangeModel = null;
  renderSamples();
  updateModel();
  await saveRange();
  draw();
};

$('fitModel').onclick = async () => {
  if (samples.length < 3) {
    $('mdlState').textContent = 'can it nhat 3 mau';
    $('mdlState').className = 'bad';
    return;
  }
  let n = samples.length, sx = 0, sy = 0, sxx = 0, sxy = 0;
  for (const s of samples) {
    const x = s.v, y = 1 / s.d;
    sx += x; sy += y; sxx += x * x; sxy += x * y;
  }
  const den = n * sxx - sx * sx;
  if (Math.abs(den) < 1e-9) {
    $('mdlState').textContent = 'cac mau cung v, khong tinh duoc';
    $('mdlState').className = 'bad';
    return;
  }
  const m = (n * sxy - sx * sy) / den;
  const c = (sy - m * sx) / n;
  if (m <= 0) {
    $('mdlState').textContent = 'du lieu nguoc (v phai giam khi d tang)';
    $('mdlState').className = 'bad';
    return;
  }
  const A = 1 / m;
  const v0 = -c / m;
  let ss = 0;
  for (const s of samples) {
    const d = A / (s.v - v0);
    ss += (d - s.d) * (d - s.d);
  }
  const rms = Math.sqrt(ss / n);
  const ds = samples.map(s => s.d);
  rangeModel = {
    type: 'pinhole_ground',
    A: A, v0: v0, rms: rms, n: n,
    valid_range_m: [Math.min.apply(null, ds), Math.max.apply(null, ds)]
  };
  updateModel();
  renderSamples();
  await saveRange();
  draw();
};

// ---------- ve ----------
function draw() {
  ctx.clearRect(0, 0, cv.width, cv.height);

  if (Hmat && $('grid').checked) {
    const inv = inv3(Hmat);
    const step = parseFloat($('step').value) || 0.5;
    const span = 8;
    ctx.lineWidth = Math.max(1, cv.width / 900);
    for (let x = 0; x <= span + 1e-9; x += step) {
      const a = applyH(inv, x, 0), b = applyH(inv, x, span);
      stroke(a, b, x === 0 ? '#38bdf8' : 'rgba(56,189,248,.35)');
    }
    for (let y = 0; y <= span + 1e-9; y += step) {
      const a = applyH(inv, 0, y), b = applyH(inv, span, y);
      stroke(a, b, y === 0 ? '#38bdf8' : 'rgba(56,189,248,.35)');
    }
  }

  if (rangeModel) {
    const marks = [0.3, 0.4, 0.5, 0.7, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0];
    ctx.lineWidth = 1.5;
    for (const d of marks) {
      const v = rangeModel.v0 + rangeModel.A / d;
      if (v < 0 || v > cv.height) continue;
      ctx.strokeStyle = 'rgba(250,204,21,.55)';
      ctx.beginPath(); ctx.moveTo(0, v); ctx.lineTo(cv.width, v); ctx.stroke();
      ctx.fillStyle = 'rgba(250,204,21,.95)';
      ctx.font = Math.max(12, cv.width / 70) + 'px sans-serif';
      ctx.fillText(d.toFixed(1) + ' m', 6, v - 4);
    }
  }

  if ($('cross').checked) {
    const cx = cv.width / 2, cy = cv.height / 2, r = 14;
    ctx.strokeStyle = '#fbbf24'; ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.moveTo(cx - r, cy); ctx.lineTo(cx + r, cy);
    ctx.moveTo(cx, cy - r); ctx.lineTo(cx, cy + r);
    ctx.stroke();
  }

  calibPts.forEach((p, i) => {
    dot(p, '#f472b6');
    label(p, String(i + 1), '#f472b6');
  });

  if (ptA) dot(ptA, '#4ade80');
  if (ptB) dot(ptB, '#4ade80');
  if (ptA && ptB) {
    ctx.strokeStyle = '#4ade80'; ctx.lineWidth = 2;
    ctx.beginPath(); ctx.moveTo(ptA[0], ptA[1]); ctx.lineTo(ptB[0], ptB[1]); ctx.stroke();
  }
  if (lastPt) dot(lastPt, '#e2e8f0');
}

function stroke(a, b, color) {
  ctx.strokeStyle = color;
  ctx.beginPath(); ctx.moveTo(a[0], a[1]); ctx.lineTo(b[0], b[1]); ctx.stroke();
}
function dot(p, color) {
  ctx.fillStyle = color;
  ctx.beginPath(); ctx.arc(p[0], p[1], Math.max(3, cv.width / 250), 0, 7); ctx.fill();
}
function label(p, txt, color) {
  ctx.fillStyle = color;
  ctx.font = Math.max(14, cv.width / 55) + 'px sans-serif';
  ctx.fillText(txt, p[0] + 8, p[1] - 8);
}

// ---------- su kien ----------
cv.addEventListener('mousemove', ev => {
  const [u, v] = toNative(ev);
  if (!Hmat) { $('px').textContent = u.toFixed(0) + ', ' + v.toFixed(0); return; }
  const [X, Y] = applyH(Hmat, u, v);
  $('px').textContent = u.toFixed(0) + ', ' + v.toFixed(0) +
    '  ->  ' + X.toFixed(2) + 'm, ' + Y.toFixed(2) + 'm';
});

cv.addEventListener('click', ev => {
  const p = toNative(ev);
  if (mode === 'calib') {
    if (calibPts.length >= 4) calibPts = [];
    calibPts.push(p);
    renderPts();
    $('apply').disabled = calibPts.length !== 4;
    draw();
    return;
  }
  lastPt = p;
  $('curPt').textContent = p[0].toFixed(0) + ', ' + p[1].toFixed(0);
  const dm = modelDistance(p[1]);
  if (Hmat) {
    const [X, Y] = applyH(Hmat, p[0], p[1]);
    $('wx').textContent = X.toFixed(3) + ' m';
    $('wy').textContent = Y.toFixed(3) + ' m';
    $('wdh').textContent = Math.hypot(X, Y).toFixed(3) + ' m';
    $('wd').textContent = dm !== null ? dm.toFixed(3) + ' m' : '-';
  } else {
    $('wx').textContent = '-';
    $('wy').textContent = '-';
    $('wdh').textContent = '-';
    $('wd').textContent = dm !== null ? dm.toFixed(3) + ' m' : '-';
  }
  draw();
});

function renderPts() {
  const t = $('pts');
  t.innerHTML = '<tr><td class="muted">#</td><td class="muted">X (m)</td><td class="muted">Y (m)</td></tr>';
  for (let i = 0; i < 4; i++) {
    const tr = document.createElement('tr');
    const p = calibPts[i];
    tr.innerHTML =
      '<td>' + (i + 1) + (p ? ' <span class="muted">(' + p[0].toFixed(0) + ',' + p[1].toFixed(0) + ')</span>' : ' <span class="muted">chua click</span>') + '</td>' +
      '<td><input type="number" step="0.05" id="cx' + i + '" value="' + worldPts[i][0] + '"></td>' +
      '<td><input type="number" step="0.05" id="cy' + i + '" value="' + worldPts[i][1] + '"></td>';
    t.appendChild(tr);
  }
  for (let i = 0; i < 4; i++) {
    $('cx' + i).addEventListener('change', e => { worldPts[i][0] = parseFloat(e.target.value) || 0; });
    $('cy' + i).addEventListener('change', e => { worldPts[i][1] = parseFloat(e.target.value) || 0; });
  }
}

$('fs').onclick = () => {
  const el = $('wrap');
  if (document.fullscreenElement) { document.exitFullscreen(); }
  else if (el.requestFullscreen) { el.requestFullscreen(); }
};
$('mMeasure').onclick = () => { mode = 'measure'; $('mMeasure').className = ''; $('mCalib').className = 'alt'; };
$('mCalib').onclick   = () => { mode = 'calib';   $('mCalib').className = ''; $('mMeasure').className = 'alt'; };

$('presetFront').onclick = () => {
  worldPts = [[-0.2, 0.5], [0.2, 0.5], [0.2, 1.0], [-0.2, 1.0]];
  renderPts(); draw();
};
$('presetTop').onclick = () => {
  worldPts = [[0, 0], [1, 0], [1, 1], [0, 1]];
  renderPts(); draw();
};
$('reset').onclick = () => { calibPts = []; renderPts(); $('apply').disabled = true; draw(); };
$('grid').onchange = draw;
$('cross').onchange = draw;
$('step').onchange = draw;

$('p1').onclick = () => { ptA = lastPt; draw(); updateAB(); };
$('p2').onclick = () => { ptB = lastPt; draw(); updateAB(); };
function updateAB() {
  if (ptA && ptB && Hmat) {
    const a = applyH(Hmat, ptA[0], ptA[1]), b = applyH(Hmat, ptB[0], ptB[1]);
    $('ab').textContent = Math.hypot(a[0] - b[0], a[1] - b[1]).toFixed(3) + ' m';
  }
}

$('apply').onclick = async () => {
  try {
    const h = solveH(calibPts, worldPts);
    Hmat = h;
    const r = await fetch('/api/calib', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ src: calibPts, dst: worldPts, H: h })
    });
    const j = await r.json();
    if (j.ok) {
      calibInfo = {
        src: calibPts.map(p => [p[0], p[1]]),
        dst: worldPts.map(p => [p[0], p[1]]),
        H: h, count: j.count, saved_at: j.saved_at
      };
      $('calibState').textContent = 'da luu lan ' + j.count + ' - ' + j.saved_at;
    } else {
      $('calibState').textContent = 'loi luu file: ' + (j.error || '');
    }
    updateStats();
    draw();
  } catch (e) {
    $('calibState').textContent = 'loi: ' + e.message + ' (4 diem co thang hang?)';
  }
};

async function boot() {
  renderPts();
  try {
    const j = await (await fetch('/api/state')).json();
    $('fps').textContent = j.fps.toFixed(1);
    if (j.w) { W = j.w; H = j.h; syncCanvas(); }
    if (j.calib && j.calib.H) {
      Hmat = j.calib.H;
      calibInfo = j.calib;
      calibPts = (j.calib.src || []).map(p => [p[0], p[1]]);
      worldPts = (j.calib.dst || worldPts).map(p => [p[0], p[1]]);
      renderPts();
      $('calibState').textContent = 'da nap lan ' + (j.calib.count || 1);
      draw();
    }
    if (j.calib && j.calib.range_model) {
      rangeModel = j.calib.range_model;
      samples = (j.calib.samples || []).map(s => ({ d: s.d, u: s.u, v: s.v }));
    }
    renderSamples();
    updateModel();
    updateStats();
  } catch (e) {}
  setInterval(async () => {
    try {
      const j = await (await fetch('/api/state')).json();
      $('fps').textContent = j.fps.toFixed(1);
      $('err').textContent = j.err || '';
      if (j.w && (j.w !== W || j.h !== H)) { W = j.w; H = j.h; syncCanvas(); }
    } catch (e) {}
  }, 1000);
}
boot();
</script>
</body>
</html>
"""


LIVE_PAGE = r"""<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>AGV - Khoang cach tu camera</title>
<style>
  :root { color-scheme: dark; }
  * { box-sizing: border-box; }
  body { margin:0; background:#0b1120; color:#e2e8f0; font-family: system-ui,"Segoe UI",sans-serif; }
  header { padding:8px 14px; background:#111a2e; border-bottom:1px solid #22304a; display:flex;
           gap:16px; align-items:center; flex-wrap:wrap; font-size:13px; }
  main { display:grid; grid-template-columns: minmax(0,1fr) 340px; gap:12px; padding:12px; align-items:start; }
  @media (max-width:1000px){ main { grid-template-columns:1fr; } }
  .stage { position:relative; background:#000; border:1px solid #22304a; border-radius:10px; overflow:hidden; }
  #live { display:block; width:100%; height:auto; }
  #ov { position:absolute; inset:0; width:100%; height:100%; pointer-events:none; }
  #badge { position:absolute; top:10px; left:10px; padding:6px 14px; border-radius:10px;
           font-size:34px; font-weight:700; background:rgba(11,17,32,.75); border:1px solid #22304a; }
  .card { background:#111a2e; border:1px solid #22304a; border-radius:10px; padding:12px 14px; margin-bottom:12px; }
  .card h3 { margin:0 0 8px; font-size:12px; color:#7dd3fc; letter-spacing:.6px; text-transform:uppercase; }
  .stat { display:flex; justify-content:space-between; gap:10px; font-size:14px; padding:5px 0;
          border-bottom:1px dashed #1e293b; }
  .stat b { font-weight:600; }
  button { background:#1d4ed8; border:0; color:#fff; padding:7px 12px; border-radius:7px; font-size:13px; cursor:pointer; }
  button.alt { background:#334155; }
  input[type=range]{ width:130px; }
  .row { display:flex; gap:8px; align-items:center; margin:8px 0; flex-wrap:wrap; font-size:13px; }
  .muted { color:#94a3b8; font-size:12px; }
  .g { color:#4ade80; } .y { color:#fbbf24; } .o { color:#fb923c; } .r { color:#f87171; }
</style>
</head>
<body>
<header>
  <span style="color:#38bdf8;font-weight:600">CAM RANGE</span>
  <span id="mdl">dang nap mo hinh...</span>
  <span id="src"></span>
</header>

<main>
  <section class="stage">
    <img id="live" src="/stream.mjpg" alt="camera">
    <canvas id="ov"></canvas>
    <div id="badge" class="r">--</div>
  </section>

  <aside>
    <div class="card">
      <h3>Ket qua</h3>
      <div class="stat"><span>Khoang cach</span><b id="d" class="g">-</b></div>
      <div class="stat"><span>Lech ngang X</span><b id="x">-</b></div>
      <div class="stat"><span>Pixel (u,v)</span><b id="uv">-</b></div>
      <div class="stat"><span>Trang thai</span><b id="st">-</b></div>
      <div class="row">
        <button id="recap" class="alt">Chup lai anh nen</button>
      </div>
      <div class="muted" id="msg">Dat xe, don sach san, roi bam "Chup lai anh nen".</div>
    </div>

    <div class="card">
      <h3>Tinh chinh</h3>
      <div class="row"><span class="muted">Nguong</span><input type="range" id="thr" min="8" max="90" value="28"><b id="thrv">28</b></div>
      <div class="row"><span class="muted">Min cot</span><input type="range" id="mc" min="2" max="40" value="6"><b id="mcv">6</b></div>
      <div class="row"><span class="muted">ROI trai</span><input type="range" id="r0" min="0" max="90" value="35"><b id="r0v">0.35</b></div>
      <div class="row"><span class="muted">ROI phai</span><input type="range" id="r1" min="10" max="100" value="65"><b id="r1v">0.65</b></div>
      <div class="row"><label><input type="checkbox" id="showOv" checked> Ve diem tiep xuc</label></div>
    </div>
  </aside>
</main>

<canvas id="proc" style="display:none"></canvas>
<canvas id="refc" style="display:none"></canvas>

<script>
const $ = id => document.getElementById(id);
const live = $('live'), ov = $('ov'), octx = ov.getContext('2d');
const proc = $('proc'), pctx = proc.getContext('2d', { willReadFrequently: true });
const refc = $('refc'), rctx = refc.getContext('2d', { willReadFrequently: true });

let model = null, refReady = false, hit = null, paused = false;

// nap mo hinh
fetch('/calib.json').then(r => r.json()).then(j => {
  const m = j.range_model;
  if (!m) { $('mdl').textContent = 'chua co range_model - hay hieu chuan truoc'; return; }
  const samples = j.samples || [];
  const cx = samples.length ? samples.reduce((s, q) => s + q.u, 0) / samples.length : 320;
  model = { A: m.A, v0: m.v0, rms: m.rms, cx: cx,
            valid: m.valid_range_m || [0.3, 3.0] };
  $('mdl').textContent = 'A=' + m.A.toFixed(1) + '  v0=' + m.v0.toFixed(1) +
                         '  rms=' + (m.rms * 100).toFixed(1) + 'cm';
  loadRef();
});

function loadRef() {
  const im = new Image();
  im.onload = () => {
    refc.width = im.naturalWidth; refc.height = im.naturalHeight;
    rctx.drawImage(im, 0, 0);
    refReady = true;
    $('msg').textContent = 'da nap anh nen ' + im.naturalWidth + 'x' + im.naturalHeight;
    loop();
  };
  im.onerror = () => {
    $('msg').textContent = 'chua co anh nen - bam "Chup lai anh nen"';
    refReady = false;
    setTimeout(loop, 1000);
  };
  im.src = '/floor_ref.jpg?t=' + Date.now();
}

$('recap').onclick = async () => {
  paused = true;
  const r = await fetch('/api/bg', { method: 'POST' });
  const j = await r.json();
  $('msg').textContent = j.ok ? 'da chup lai anh nen luc ' + new Date().toLocaleTimeString() : 'loi chup nen';
  refReady = false; paused = false;
  loadRef();
};

['thr', 'mc', 'r0', 'r1'].forEach(id => {
  $(id).oninput = () => {
    $('thrv').textContent = $('thr').value;
    $('mcv').textContent = $('mc').value;
    $('r0v').textContent = ($('r0').value / 100).toFixed(2);
    $('r1v').textContent = ($('r1').value / 100).toFixed(2);
  };
});

function detect() {
  const W = proc.width, H = proc.height;
  if (!W || !refReady || refc.width !== W) return null;
  const thr = +$('thr').value, minCol = +$('mc').value;
  const x0 = Math.floor(W * (+$('r0').value / 100));
  const x1 = Math.ceil(W * (+$('r1').value / 100));
  const vLo = Math.max(0, Math.floor(model.v0) + 3), vHi = H - 2;
  const cur = pctx.getImageData(0, 0, W, H).data;
  const ref = rctx.getImageData(0, 0, W, H).data;

  const ys = [], xs = [];
  for (let x = x0; x < x1; x++) {
    let cnt = 0, low = -1;
    for (let y = vLo; y < vHi; y++) {
      const i = (y * W + x) * 4;
      const g1 = cur[i] * .299 + cur[i + 1] * .587 + cur[i + 2] * .114;
      const g2 = ref[i] * .299 + ref[i + 1] * .587 + ref[i + 2] * .114;
      if (Math.abs(g1 - g2) > thr) { cnt++; low = y; }
    }
    if (low > 0 && cnt >= minCol) { ys.push(low); xs.push(x); }
  }
  if (ys.length < 3) return null;

  const order = ys.map((y, i) => i).sort((a, b) => ys[a] - ys[b]);
  const v = ys[order[Math.floor(order.length * 0.2)]];   // 20% gan nhat
  let su = 0, n = 0;
  for (let i = 0; i < ys.length; i++) {
    if (Math.abs(ys[i] - v) <= 6) { su += xs[i]; n++; }
  }
  return { u: n ? su / n : xs[0], v: v, run: ys.length };
}

function sizeOverlay() {
  const r = live.getBoundingClientRect();
  if (ov.width !== Math.round(r.width) || ov.height !== Math.round(r.height)) {
    ov.width = Math.round(r.width); ov.height = Math.round(r.height);
  }
}
window.addEventListener('resize', sizeOverlay);

function paint() {
  sizeOverlay();
  octx.clearRect(0, 0, ov.width, ov.height);
  const W = proc.width, H = proc.height;
  if (!W) return;
  const sx = ov.width / W, sy = ov.height / H;

  if ($('showOv').checked) {
    octx.strokeStyle = 'rgba(56,189,248,.5)';
    octx.lineWidth = 1;
    const x0 = W * (+$('r0').value / 100), x1 = W * (+$('r1').value / 100);
    octx.strokeRect(x0 * sx, (model.v0 + 3) * sy, (x1 - x0) * sx, (H - model.v0 - 5) * sy);

    if (hit) {
      octx.beginPath();
      octx.arc(hit.u * sx, hit.v * sy, Math.max(8, 0.02 * W * sx), 0, 7);
      octx.strokeStyle = '#4ade80'; octx.lineWidth = 3; octx.stroke();
    }
  }
}

function band(d) {
  if (d === null) return ['r', 'duong trong'];
  if (d < 0.22) return ['r', 'DUNG'];
  if (d < 0.30) return ['o', 'CHAM'];
  if (d < 0.45) return ['y', 'GIAM TOC'];
  return ['g', 'THOANG'];
}

let nFrame = 0;

function loop() {
  if (paused) { setTimeout(loop, 300); return; }
  const im = new Image();
  im.onload = () => {
    try {
      if (proc.width !== im.naturalWidth || proc.height !== im.naturalHeight) {
        proc.width = im.naturalWidth; proc.height = im.naturalHeight;
        if (refc.width !== proc.width) {
          const tmp = document.createElement('canvas');
          tmp.width = proc.width; tmp.height = proc.height;
          tmp.getContext('2d').drawImage(refc, 0, 0, proc.width, proc.height);
          refc.width = proc.width; refc.height = proc.height;
          rctx.drawImage(tmp, 0, 0);
        }
      }
      pctx.drawImage(im, 0, 0);
      nFrame++;
      $('src').textContent = im.naturalWidth + 'x' + im.naturalHeight + '  frame=' + nFrame;

      if (!model) { setTimeout(loop, 300); return; }

      hit = detect();
      let d = null;
      if (hit) {
        const den = hit.v - model.v0;
        if (den > 0.5) d = model.A / den;
      }
      const cls = band(d)[0], label = band(d)[1];
      const b = $('badge');
      b.className = cls;
      b.textContent = d === null ? 'TRONG' : d.toFixed(2) + ' m';
      $('d').textContent = d === null ? '> ' + model.valid[1].toFixed(1) + ' m'
                                      : d.toFixed(3) + ' m';
      $('d').className = cls;
      if (hit && d !== null) {
        const xm = (hit.u - model.cx) * d / (model.A / 0.125);
        $('x').textContent = (xm >= 0 ? '+' : '') + xm.toFixed(3) + ' m';
      } else { $('x').textContent = '-'; }
      $('uv').textContent = hit ? hit.u.toFixed(0) + ', ' + hit.v.toFixed(0) +
                                  '  (' + hit.run + ' cot)' : '-';
      $('st').textContent = label;
      $('st').className = cls;
      paint();
    } catch (e) {
      $('msg').textContent = 'LOI JS: ' + e.message;
      $('badge').textContent = 'ERR';
      $('badge').className = 'r';
    }
    setTimeout(loop, 90);
  };
  im.onerror = () => {
    $('msg').textContent = 'LOI: khong tai duoc /snapshot.jpg (frame=' + nFrame + ')';
    $('badge').textContent = 'NO IMG';
    $('badge').className = 'r';
    setTimeout(loop, 600);
  };
  im.src = '/snapshot.jpg?t=' + Date.now();
}
</script>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        pass

    def _send(self, code, ctype, body):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = self.path.split("?", 1)[0]

        if path in ("/", "/index.html"):
            self._send(200, "text/html; charset=utf-8", PAGE.encode("utf-8"))
            return

        if path == "/stream.mjpg":
            self.send_response(200)
            self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            last_seq = -1
            try:
                while True:
                    with LOCK:
                        buf, seq = STATE["jpeg"], STATE["seq"]
                    if buf is None or seq == last_seq:
                        time.sleep(0.02)
                        continue
                    last_seq = seq
                    self.wfile.write(b"--frame\r\n")
                    self.wfile.write(b"Content-Type: image/jpeg\r\n")
                    self.wfile.write(("Content-Length: %d\r\n\r\n" % len(buf)).encode())
                    self.wfile.write(buf)
                    self.wfile.write(b"\r\n")
            except (BrokenPipeError, ConnectionResetError):
                pass
            return

        if path == "/snapshot.jpg":
            with LOCK:
                buf = STATE["jpeg"]
            if buf is None:
                self._send(503, "text/plain", b"no frame")
            else:
                self._send(200, "image/jpeg", buf)
            return

        if path in ("/live", "/live.html"):
            self._send(200, "text/html; charset=utf-8", LIVE_PAGE.encode("utf-8"))
            return

        if path.startswith("/floor_ref.jpg"):
            try:
                with open(BG_PATH, "rb") as fh:
                    body = fh.read()
                self._send(200, "image/jpeg", body)
            except Exception:
                self._send(404, "text/plain", b"chua co anh nen")
            return

        if path == "/calib.json":
            body = json.dumps(load_calib(), indent=2, ensure_ascii=False,
                              default=str).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Content-Disposition",
                             'attachment; filename="camera_calib.json"')
            self.end_headers()
            self.wfile.write(body)
            return

        if path == "/api/state":
            with LOCK:
                body = {
                    "w": STATE["w"], "h": STATE["h"],
                    "fps": round(STATE["fps"], 1),
                    "err": STATE["err"], "device": STATE["device"],
                }
            body["calib"] = load_calib()
            self._send(200, "application/json", json.dumps(body).encode())
            return

        self._send(404, "text/plain", b"not found")

    def do_POST(self):
        path = self.path.split("?", 1)[0]

        if path == "/api/bg":
            with LOCK:
                buf = STATE["jpeg"]
            if buf is None:
                self._send(503, "application/json", b'{"ok":false,"error":"no frame"}')
                return
            try:
                with open(BG_PATH, "wb") as fh:
                    fh.write(buf)
                self._send(200, "application/json",
                           json.dumps({"ok": True, "path": BG_PATH}).encode())
            except Exception as exc:
                self._send(500, "application/json",
                           json.dumps({"ok": False, "error": str(exc)}).encode())
            return

        if path == "/api/range":
            n = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(n) if n else b"{}"
            try:
                data = json.loads(raw.decode("utf-8"))
                calib = load_calib()
                calib["version"] = 2
                calib["camera_mount"] = "front"
                calib["image_size"] = [STATE["w"], STATE["h"]]
                calib["samples"] = data.get("samples", [])
                calib["range_model"] = data.get("model")
                calib["usage"] = ("d_m = A / (v_px - v0), v_px = hang pixel cua "
                                  "diem tiep xuc san trong anh")
                calib["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
                write_calib(calib)
                self._send(200, "application/json",
                           json.dumps({"ok": True, "path": CALIB_PATH}).encode())
            except Exception as exc:
                self._send(400, "application/json",
                           json.dumps({"ok": False, "error": str(exc)}).encode())
            return

        if path != "/api/calib":
            self._send(404, "text/plain", b"not found")
            return
        n = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(n) if n else b"{}"
        try:
            data = json.loads(raw.decode("utf-8"))
            src = np.array(data["src"], dtype=np.float64)
            dst = np.array(data["dst"], dtype=np.float64)
            Hm, _ = cv2.findHomography(src, dst, 0)
            if Hm is None:
                raise ValueError("khong tinh duoc homography")
            data["H"] = Hm.reshape(-1).tolist()
            data["saved_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
            data["image_size"] = [STATE["w"], STATE["h"]]
            cnt = save_calib(data)
            self._send(200, "application/json",
                       json.dumps({"ok": True, "path": CALIB_PATH, "H": data["H"],
                                   "count": cnt, "saved_at": data["saved_at"]}).encode())
        except Exception as exc:
            self._send(400, "application/json",
                       json.dumps({"ok": False, "error": str(exc)}).encode())


def candidates(explicit):
    """Danh sach node camera can thu."""
    if explicit and explicit not in ("auto", ""):
        return [explicit]
    out = []
    for idx in range(10):
        path = "/dev/video%d" % idx
        if os.path.exists(path):
            out.append(path)
    return out


def free_port(start=8090, end=8300):
    import socket as _s
    for p in range(start, end):
        try:
            with _s.socket() as sock:
                sock.bind(("0.0.0.0", p))
            return p
        except OSError:
            continue
    return 8090


def local_ip():
    import socket as _s
    try:
        sock = _s.socket(_s.AF_INET, _s.SOCK_DGRAM)
        sock.connect(("1.1.1.1", 80))
        ip = sock.getsockname()[0]
        sock.close()
        return ip
    except Exception:
        return "127.0.0.1"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--device", default="auto", help="/dev/videoN hoac 'auto'")
    ap.add_argument("--port", type=int, default=0, help="0 = tu chon cong trong")
    ap.add_argument("--width", type=int, default=1280)
    ap.add_argument("--height", type=int, default=720)
    ap.add_argument("--quality", type=int, default=80)
    ap.add_argument("--fps", type=int, default=15)
    ap.add_argument("--source", default="",
                    help="URL snapshot de doc thay vi mo camera (vd http://127.0.0.1:8081/snapshot.jpg)")
    args = ap.parse_args()

    port = args.port if args.port else free_port()
    dev = None
    how = None
    cap = None

    if args.source:
        how = "source"
        dev = args.source
        t = threading.Thread(target=source_loop, args=(args.source, args.quality, args.fps),
                             daemon=True)
    else:
        for cand in candidates(args.device):
            cap, how = open_capture(cand, args.width, args.height, args.fps)
            if cap is not None:
                dev = cand
                break
        if cap is None:
            fallback = "http://127.0.0.1:8081/snapshot.jpg"
            print("Khong mo duoc /dev/video* (co the agv-cam.service dang giu).")
            print("Thu doc lai tu %s" % fallback)
            args.source = fallback
            how = "source"
            dev = fallback
            t = threading.Thread(target=source_loop, args=(fallback, args.quality, args.fps),
                                 daemon=True)
        else:
            t = threading.Thread(target=cam_loop,
                                 args=(cap, args.quality, "%s [%s]" % (dev, how)), daemon=True)

    t.start()
    time.sleep(1.5)

    with LOCK:
        w, h, err = STATE["w"], STATE["h"], STATE["err"]

    srv = None
    tries = 0
    while srv is None and tries < 20:
        try:
            srv = ThreadingHTTPServer(("0.0.0.0", port), Handler)
        except OSError:
            port += 1
            tries += 1
    if srv is None:
        print("KHONG BIND DUOC CONG NAO. Dung: sudo ss -ltnp | grep python")
        raise SystemExit(1)
    print("=" * 46)
    print(" Camera : %s   (%dx%d)" % (dev, w, h))
    print(" Backend: %s" % how)
    if err:
        print(" CANH BAO: %s" % err)
    print(" MO TRINH DUYET:")
    print("   http://%s:%d/" % (local_ip(), port))
    print("=" * 46)
    print(" Calib  : %s" % CALIB_PATH)
    print(" Ctrl+C de dung")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
