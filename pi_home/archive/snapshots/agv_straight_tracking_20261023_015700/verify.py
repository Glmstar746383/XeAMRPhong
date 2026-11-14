import hashlib
import json
import os
import subprocess
import time
import urllib.request

ROOT = '/home/khangho/agv_codex_reader_20261003_0652'
STAGE = '/home/khangho/agv_straight_tracking_20261023_015700'
BACKUP = '/home/khangho/agv_straight_tracking_20261023_015700/backup'
EXPECTED = {'agv_unified_brain.py': '47f9cd7e91684d64522efdbe7852b6a336e579ca361dcabb7304bad27244a2d9', 'agv_speed_profile.py': '6b575e184d56590b508a3dca18df8305844aa2e82b9d2ee84127e24579b18517'}

def check_telemetry():
    with urllib.request.urlopen('http://127.0.0.1:8080/api/telemetry', timeout=3) as r:
        return json.load(r)

def check_diagnostics():
    with urllib.request.urlopen('http://127.0.0.1:8080/api/diagnostics', timeout=3) as r:
        return json.load(r)

def check_ui():
    with urllib.request.urlopen('http://127.0.0.1:8080/', timeout=3) as r:
        assert r.status == 200
        content = r.read()
        assert len(content) > 1000
        return r.status, len(content)

deadline = time.monotonic() + 45
last_err = None
t_data = None
d_data = None
ui_res = None

while time.monotonic() < deadline:
    try:
        ui_res = check_ui()
        t_data = check_telemetry()
        d_data = check_diagnostics()
        
        c = t_data.get('control', {})
        d0 = c.get('latest_d0', {})
        d0_age = c.get('d0_age_s')
        
        # Verify stationary disarmed safety conditions
        if (t_data.get('auto') is False and
            c.get('armed') is False and
            d0.get('safety') == 'DISARMED' and
            isinstance(d0_age, (int, float)) and 0.0 <= d0_age <= 0.25 and
            all(d0.get(k) == 0 for k in ('l_tgt', 'r_tgt', 'l_rpm', 'r_rpm', 'l_pwm', 'r_pwm', 'v', 'w')) and
            c.get('fault') is None):
            break
    except Exception as exc:
        last_err = str(exc)
    time.sleep(0.5)
else:
    raise RuntimeError(f'Verification timed out: {last_err}')

# Check processes
brain_pid = None
try:
    with open(f'{ROOT}/runtime/brain.pid') as f:
        brain_pid = int(f.read().strip())
except Exception as e:
    raise RuntimeError(f'Failed to read brain.pid: {e}')

p_proc = f'/proc/{brain_pid}'
assert os.path.exists(p_proc), f'Brain PID {brain_pid} not alive'
cwd = os.readlink(f'{p_proc}/cwd')
assert cwd == ROOT, f'Brain CWD mismatch: {cwd} != {ROOT}'

# Check active ROS services
pids = {}
for svc, pat in [('sllidar', '^/opt/ros/jazzy/lib/sllidar_ros2/sllidar_node'),
                 ('slam_toolbox', '^/opt/ros/jazzy/lib/slam_toolbox/async_slam_toolbox_node'),
                 ('tf_publisher', '^/opt/ros/jazzy/lib/tf2_ros/static_transform_publisher')]:
    try:
        out = subprocess.check_output(['pgrep', '-f', pat]).decode().split()
        pids[svc] = [int(p) for p in out]
    except Exception:
        pids[svc] = []

final_data = {
    'brain_pid': brain_pid,
    'brain_cwd': cwd,
    'pids': pids,
    'ui_status': ui_res[0],
    'telemetry': t_data,
    'diagnostics': d_data
}
print('FINAL_VERIFICATION_JSON_START')
print(json.dumps(final_data))
print('FINAL_VERIFICATION_JSON_END')
