#!/bin/bash
# Tu chua: LiDAR ket -> restart agv; camera khong publish -> restart agv-cam-range.
# Gioi han 1 lan / 5 phut cho moi loai.
STATE=/tmp/agv_health_last_restart
CAMSTATE=/tmp/agv_health_last_cam
NOW=$(date +%s)

python3 - "$NOW" "$STATE" "$CAMSTATE" <<'PY'
import json, subprocess, sys, urllib.request

now = int(sys.argv[1])
state, camstate = sys.argv[2], sys.argv[3]


def read_int(path):
    try:
        with open(path) as fh:
            return int(fh.read().strip() or 0)
    except Exception:
        return 0


def write_now(path):
    try:
        with open(path, 'w') as fh:
            fh.write(str(now))
    except Exception:
        pass


try:
    with urllib.request.urlopen('http://127.0.0.1:8080/api/telemetry', timeout=6) as r:
        t = json.loads(r.read().decode())
except Exception:
    sys.exit(0)

lidar = t.get('lidar') or {}
age = lidar.get('age_s')
if lidar.get('connected') is False and (age is None or age > 30):
    if now - read_int(state) >= 300:
        write_now(state)
        print('RESTART agv: lidar stale age=%s' % age, flush=True)
        subprocess.run(['sudo', '-n', 'systemctl', 'restart', 'agv'], timeout=60)
    sys.exit(0)

cam = t.get('camera') or {}
cage = cam.get('age_s')
if cam.get('enabled') and (cage is None or cage > 30):
    if now - read_int(camstate) >= 300:
        write_now(camstate)
        print('RESTART agv-cam-range: camera stale age=%s' % cage, flush=True)
        subprocess.run(['sudo', '-n', 'systemctl', 'restart', 'agv-cam-range'], timeout=40)
PY
