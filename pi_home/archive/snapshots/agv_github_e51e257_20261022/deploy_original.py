"""Install verified original Git blobs on the Pi, keeping a recoverable backup."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
import urllib.request

ROOT = Path('/home/khangho/agv_codex_reader_20261003_0652')
STAGE = Path('/home/khangho/agv_github_e51e257_20261022')
EXPECTED = json.loads((STAGE/'expected_github_hashes.json').read_text())


def get(path):
    with urllib.request.urlopen('http://127.0.0.1:8080'+path, timeout=3) as response:
        return json.load(response)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def zero(data, require_disarmed=False):
    c = data['control']
    p = c.get('latest_d0') or {}
    age = c.get('d0_age_s')
    return (data['auto'] is False and c.get('fault') is None and
            isinstance(age, (int, float)) and 0 <= age <= .25 and
            p.get('safety') in (('DISARMED',) if require_disarmed else ('DISARMED', 'ARMED')) and
            all(p.get(k) == 0 for k in ('l_tgt', 'r_tgt', 'l_rpm', 'r_rpm',
                                       'l_pwm', 'r_pwm', 'v', 'w')))


assert set(EXPECTED) == {'agv_unified_brain.py', 'agv_command_session.py',
                         'agv_navigation.py', 'agv_preflight_static_collector.py',
                         'agv_command_journal.py', 'index_cyberpunk.html', 'start_agv_system.sh'}
for name, expected in EXPECTED.items():
    assert digest(STAGE/name) == expected, f'Staged Git blob mismatch: {name}'
    if name.endswith('.py'):
        compile((STAGE/name).read_bytes(), name, 'exec')
assert b'\r' not in (STAGE/'start_agv_system.sh').read_bytes()
assert digest(ROOT/'agv_unified_brain.py') == '3ed5b521062684d0d5a8485485c90e321d1ce505bea84d359d803e39a8729970'
assert digest(ROOT/'agv_navigation.py') == '6579c48a1d6265bf31f3b43892e91efb7507d0f7ec3b61c9af93a2e6296812e4'
for _ in range(3):
    assert zero(get('/api/telemetry'), True), 'No fresh stationary DISARMED proof'
    time.sleep(.15)

# Verify the launcher PID files before the existing stop script uses them.
for name, marker in [('brain', 'agv_unified_brain.py'), ('lidar', 'sllidar'),
                     ('slam', 'slam_toolbox'), ('static_tf', 'static_transform_publisher')]:
    pidfile = ROOT/'runtime'/f'{name}.pid'
    if not pidfile.exists():
        continue
    pid = int(pidfile.read_text())
    try:
        cmd = Path(f'/proc/{pid}/cmdline').read_bytes().replace(b'\0', b' ').decode()
    except FileNotFoundError:
        pidfile.unlink()
        print(f'Removed stale launcher reference: {name} PID {pid}', flush=True)
        continue
    assert marker in cmd, (name, pid, cmd)

backup = STAGE/'backup'
backup.mkdir()
for name in EXPECTED:
    shutil.copy2(ROOT/name, backup/name)
(STAGE/'telemetry_before.json').write_text(json.dumps(get('/api/telemetry'), ensure_ascii=False))
(STAGE/'map_before.json').write_text(json.dumps(get('/api/map_full')))
with (STAGE/'install.log').open('ab', buffering=0) as log:
    subprocess.run(['bash', './stop_agv_system.sh'], cwd=ROOT, stdin=subprocess.DEVNULL,
                   stdout=log, stderr=log, check=True, timeout=20)


def launch():
    with (ROOT/'runtime'/'start_github_e51e257.log').open('ab', buffering=0) as log:
        return subprocess.Popen(['bash', './start_agv_system.sh'], cwd=ROOT,
                                stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                                start_new_session=True)


try:
    for name in EXPECTED:
        temp = ROOT/(name+'.github-restore-new')
        shutil.copy2(STAGE/name, temp)
        temp.chmod((ROOT/name).stat().st_mode)
        os.replace(temp, ROOT/name)
    child = launch()
    deadline = time.monotonic()+45
    last_error = None
    while time.monotonic() < deadline:
        try:
            after = get('/api/telemetry')
            if zero(after) and after['map_info']['has_map']:
                break
        except Exception as exc:
            last_error = type(exc).__name__
        time.sleep(.25)
    else:
        raise RuntimeError(f'Original system not ready: {last_error}')
    hashes = {name: digest(ROOT/name) for name in EXPECTED}
    assert hashes == EXPECTED, 'Installed bytes do not match original Git blobs'
    result = dict(commit='e51e257be707c5ba71f3244ec331967aa91f74be',
                  status='ORIGINAL_GITHUB_RUNNING_AUTO_OFF', backup=str(backup), hashes=hashes)
    (STAGE/'telemetry_after.json').write_text(json.dumps(after, ensure_ascii=False))
    (STAGE/'result.json').write_text(json.dumps(result, indent=2))
    print(json.dumps(result), flush=True)
except Exception:
    with (STAGE/'install.log').open('ab', buffering=0) as log:
        subprocess.run(['bash', './stop_agv_system.sh'], cwd=ROOT, stdin=subprocess.DEVNULL,
                       stdout=log, stderr=log, timeout=20)
    for name in EXPECTED:
        shutil.copy2(backup/name, ROOT/name)
    launch()
    print('Original installation failed; restored prior files and restarted AUTO off.', flush=True)
    raise
