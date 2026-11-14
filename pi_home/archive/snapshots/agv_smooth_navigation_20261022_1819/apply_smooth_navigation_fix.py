"""Apply the smooth navigation & speed profile fix to an already stationary AGV controller.

Run on the Pi with the staging directory as argv[1]. Retains the original
process environment in memory only. Never sends ARM, drive or AUTO commands.
"""
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time
import urllib.request

ROOT = Path('/home/khangho/agv_codex_reader_20261003_0652')
STAGE = Path(sys.argv[1]).resolve()
EXPECTED_NEW = {
    'agv_unified_brain.py': '2b9da1132091b209730caf643a577cb9d325d5d52ac258f30f23e70a0a50cf7b',
    'agv_speed_profile.py': '205d9bcab8a9324dce2f250d6a681f256a3fc102b074f23c89751b0fbaba19c8',
}
EXPECTED_OLD = {
    'agv_unified_brain.py': '89e0c0d3b3b6b4aaf48a6ad0ae32042ac78110cb7407ce4beebc3c7e8988b200',
    'agv_speed_profile.py': 'ece845e19e9890499e9d3bf446896a99fff4a848f65a29f1bc5e94d29af83fc5',
}


def get_telemetry():
    with urllib.request.urlopen('http://127.0.0.1:8080/api/telemetry', timeout=2) as response:
        return json.load(response)


def get_diagnostics():
    with urllib.request.urlopen('http://127.0.0.1:8080/api/diagnostics', timeout=2) as response:
        return json.load(response)


def stationary(data, require_confirmed_stop=False):
    c = data.get('control') or {}
    p = c.get('latest_d0') or {}
    age = c.get('d0_age_s')
    return (data.get('auto') is False and c.get('armed') is False
            and isinstance(age, (float, int)) and 0 <= age <= .25
            and p.get('safety') == 'DISARMED'
            and all(p.get(k) == 0 for k in ('l_tgt', 'r_tgt', 'l_rpm', 'r_rpm',
                                          'l_pwm', 'r_pwm', 'v', 'w'))
            and (not require_confirmed_stop or c.get('stop_confirmed') is True))


def ensure_stopped():
    t = get_telemetry()
    if not stationary(t, require_confirmed_stop=True):
        print("Vehicle not yet stop_confirmed/DISARMED; requesting normal STOP via /api/cmd?val=STOP...", flush=True)
        with urllib.request.urlopen('http://127.0.0.1:8080/api/cmd?val=STOP', timeout=3) as r:
            res = json.load(r)
            print(f"STOP request result: {res}", flush=True)
        time.sleep(0.2)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def exited(pid):
    try:
        return Path(f'/proc/{pid}/stat').read_text().split(') ', 1)[1].startswith('Z')
    except FileNotFoundError:
        return True


def terminate(pid):
    os.kill(pid, signal.SIGTERM)
    deadline = time.monotonic() + 8
    while not exited(pid) and time.monotonic() < deadline:
        time.sleep(.1)
    if not exited(pid):
        raise RuntimeError('Graceful shutdown timed out; no forced kill issued')


assert STAGE.parent == ROOT.parent and STAGE.name.startswith('agv_smooth_navigation_')
pid = int((ROOT / 'runtime' / 'brain.pid').read_text().strip())
proc = Path(f'/proc/{pid}')
assert proc.joinpath('cwd').resolve() == ROOT, f"CWD mismatch: {proc.joinpath('cwd').resolve()}"
cmd = [part.decode() for part in proc.joinpath('cmdline').read_bytes().split(b'\0') if part]
assert cmd[-2:] == ['agv_unified_brain.py', '--operator-control'], cmd
env = dict(part.decode().split('=', 1) for part in proc.joinpath('environ').read_bytes().split(b'\0') if part and '=' in part.decode())
exe = str(proc.joinpath('exe').resolve())

# Verify current files match EXPECTED_OLD
for name, expected in EXPECTED_OLD.items():
    assert digest(ROOT / name) == expected, f'Live file changed unexpectedly: {name}'

# Verify staged files match EXPECTED_NEW
for name, expected in EXPECTED_NEW.items():
    assert (STAGE / name).is_file(), f'Staged file missing: {name}'
    assert digest(STAGE / name) == expected, f'Staged hash mismatch: {name}'
    compile((STAGE / name).read_text(encoding='utf-8'), name, 'exec')

# Subprocess dependency and import verification with proc environment
test_cmd = [exe, '-c', f'import sys; sys.path.insert(0, "{STAGE}"); import agv_speed_profile; assert agv_speed_profile.ARC_INNER_MIN_RPM == 20.0']
subprocess.run(test_cmd, env=env, check=True)

# Ensure stopped and confirmed stationary
ensure_stopped()
for _ in range(3):
    assert stationary(get_telemetry(), True), 'Vehicle is not freshly confirmed stationary; aborted'
    time.sleep(.15)

backup = STAGE / 'backup'
backup.mkdir(exist_ok=True)
backup_hashes = {}
for name in EXPECTED_OLD:
    shutil.copy2(ROOT / name, backup / name)
    backup_hashes[name] = digest(backup / name)
assert backup_hashes == EXPECTED_OLD, 'Backup hash mismatch'

before = get_telemetry()
diagnostics_before = get_diagnostics()
(STAGE / 'before.json').write_text(json.dumps(before, ensure_ascii=False, indent=2))
(STAGE / 'diagnostics_before.json').write_text(json.dumps(diagnostics_before, ensure_ascii=False, indent=2))

# Preserve SLAM and HOME mission state
starts = [entry for entry in diagnostics_before.get('command_journal', {}).get('recent', [])
          if entry.get('operation') == 'AUTO_START' and entry.get('http_status') == 200]
nav = diagnostics_before.get('navigation') or {}
home = nav.get('home') or (starts[-1]['response']['gate']['pose'] if starts else [0.0, 0.0, 0.0])
assert home is not None and len(home) == 3, f'No verified original HOME: {home}; abort migration'

slams = subprocess.check_output(['pgrep', '-f', '^/opt/ros/jazzy/lib/slam_toolbox/async_slam_toolbox_node']).decode().split()
assert len(slams) == 1, f'Expected exactly one live SLAM publisher, found {len(slams)}'
slam_pid = int(slams[0])
slam_token = Path(f'/proc/{slam_pid}/stat').read_text().split(') ', 1)[1].split()[19]

resume = dict(
    slam_pid=slam_pid,
    slam_token=slam_token,
    home=home,
    map_info=before['map_info'],
    trajectory=before['trajectory'],
    odom_pose=before['robot'],
    cautious=nav.get('cautious', False)
)

with urllib.request.urlopen('http://127.0.0.1:8080/api/map_full', timeout=5) as response:
    m = json.load(response)
assert all(m[k] == before['map_info'][k] for k in ('res', 'ox', 'oy', 'yaw', 'frame')), 'Map shifted during capture; abort before restart'

visited = set()
r = math.ceil(.20 / m['res'])
mc, ms = math.cos(m['yaw']), math.sin(m['yaw'])
for x, y in before['trajectory']['path']:
    dx, dy = x - m['ox'], y - m['oy']
    gx, gy = math.floor((mc * dx + ms * dy) / m['res']), math.floor((-ms * dx + mc * dy) / m['res'])
    for dy_offset in range(-r, r + 1):
        for dx_offset in range(-r, r + 1):
            cx, cy = gx + dx_offset, gy + dy_offset
            if dx_offset * dx_offset + dy_offset * dy_offset <= r * r and 0 <= cx < m['w'] and 0 <= cy < m['h'] and m['data'][cy * m['w'] + cx] == 0:
                visited.add((cx, cy))
resume['visited_cells'] = sorted(visited)
print(f'Coverage reconstructed from retained trace: {len(visited)} cells', flush=True)

resume_path = STAGE / 'navigation_resume.json'
resume_path.write_text(json.dumps(resume))
env['AGV_NAV_RESTART_CHECKPOINT'] = str(resume_path)
print(f'Preserving original HOME: {json.dumps(home)}', flush=True)

terminate(pid)
print('Original brain stopped gracefully; LiDAR/SLAM/TF unchanged', flush=True)


def launch():
    with (ROOT / 'runtime' / 'brain.log').open('ab', buffering=0) as log:
        return subprocess.Popen(cmd, executable=exe, cwd=ROOT, env=env,
                                stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                                start_new_session=True)


child = None
try:
    for name in EXPECTED_NEW:
        target = ROOT / name
        staged = ROOT / (name + '.smooth-fix-new')
        shutil.copy2(STAGE / name, staged)
        staged.chmod(target.stat().st_mode if target.exists() else 0o644)
        os.replace(staged, target)
    
    child = launch()
    (ROOT / 'runtime' / 'brain.pid').write_text(str(child.pid) + '\n')
    print(f'Launched new brain PID {child.pid}', flush=True)

    deadline = time.monotonic() + 30
    last_error = None
    after = None
    while time.monotonic() < deadline:
        assert child.poll() is None, f'Brain exited prematurely: {child.returncode}'
        try:
            after = get_telemetry()
            if stationary(after) and after['control'].get('fault') is None and after.get('map_info', {}).get('has_map') is True:
                break
        except Exception as exc:
            last_error = type(exc).__name__
        time.sleep(.25)
    else:
        raise RuntimeError(f'No fresh disarmed telemetry with map after restart: {last_error}')

    with urllib.request.urlopen('http://127.0.0.1:8080/api/diagnostics', timeout=3) as response:
        diagnostics_after = json.load(response)

    # UI HTTP 200 check
    with urllib.request.urlopen('http://127.0.0.1:8080/', timeout=3) as response:
        assert response.status == 200, f'UI status: {response.status}'
        ui_bytes = response.read()
        assert len(ui_bytes) > 1000, 'UI response too small'

    # State verification
    assert diagnostics_after['navigation']['home'] == home, f"HOME migration failed: {diagnostics_after['navigation']['home']} != {home}"
    assert after['speed_config'] == before['speed_config'], 'Speed configuration changed'
    assert after['control']['rpm_profile_enabled'] is True
    assert abs(after['robot']['x'] - before['robot']['x']) < .05 and abs(after['robot']['y'] - before['robot']['y']) < .05, 'Odom continuity failed'
    assert after['trajectory']['points_count'] >= len(before['trajectory']['path']), 'Trace migration failed'
    assert after['map_info']['has_map'] is True, 'Map inactive after restart'
    assert after['map_info']['w'] > 0 and after['map_info']['h'] > 0, 'Invalid map dimensions'

    installed_hashes = {name: digest(ROOT / name) for name in EXPECTED_NEW}
    assert installed_hashes == EXPECTED_NEW, f'Installed hashes mismatch: {installed_hashes} != {EXPECTED_NEW}'

    (STAGE / 'after.json').write_text(json.dumps(after, ensure_ascii=False, indent=2))
    (STAGE / 'diagnostics_after.json').write_text(json.dumps(diagnostics_after, ensure_ascii=False, indent=2))

    result = {
        'timestamp_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        'status': 'APPLIED_DISARMED',
        'pi_host': 'khang.local',
        'pi_root': str(ROOT),
        'brain_pid_before': pid,
        'brain_pid_after': child.pid,
        'brain_cmd': cmd,
        'brain_exe': exe,
        'brain_cwd': str(ROOT),
        'backup_dir': str(backup),
        'staging_dir': str(STAGE),
        'deployed_files': {
            name: {
                'sha256': installed_hashes[name],
                'before_sha256': EXPECTED_OLD[name]
            } for name in EXPECTED_NEW
        },
        'verification': {
            'http_ui_status': 200,
            'auto_mode': after['auto'],
            'armed': after['control']['armed'],
            'mcu_safety': after['control']['latest_d0']['safety'],
            'motor_rpms': {
                'left': after['control']['latest_d0']['l_rpm'],
                'right': after['control']['latest_d0']['r_rpm']
            },
            'motor_pwms': {
                'left': after['control']['latest_d0']['l_pwm'],
                'right': after['control']['latest_d0']['r_pwm']
            },
            'velocities': {
                'v': after['control']['latest_d0']['v'],
                'w': after['control']['latest_d0']['w']
            },
            'd0_age_s': after['control']['d0_age_s'],
            'has_map': after['map_info']['has_map'],
            'map_size': [after['map_info']['w'], after['map_info']['h']],
            'home': diagnostics_after['navigation']['home'],
            'trajectory_points': after['trajectory']['points_count'],
            'distance_m': after['trajectory']['distance_m'],
            'preflight_ready': after['control'].get('preflight_ready', True),
            'rpm_profile_enabled': after['control']['rpm_profile_enabled']
        }
    }
    (STAGE / 'result.json').write_text(json.dumps(result, indent=2))
    print('DEPLOYMENT_SUCCESS_JSON_START')
    print(json.dumps(result, indent=2))
    print('DEPLOYMENT_SUCCESS_JSON_END')
except Exception as e:
    print(f'Deployment failed with exception: {e}; initiating rollback...', flush=True)
    if child is not None and child.poll() is None:
        terminate(child.pid)
    for name in EXPECTED_OLD:
        shutil.copy2(backup / name, ROOT / name)
    resume_path.write_text(json.dumps(resume))
    old = launch()
    (ROOT / 'runtime' / 'brain.pid').write_text(str(old.pid) + '\n')
    print(f'Rolled back original files; restored brain PID {old.pid}', flush=True)
    raise
