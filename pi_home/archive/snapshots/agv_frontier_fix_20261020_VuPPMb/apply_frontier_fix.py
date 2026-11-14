"""Apply the two-file frontier navigation fix to an already stationary AGV controller.

Run on the Pi with the staging directory as argv[1]. Retains the original
process environment in memory only. Never sends ARM, drive or AUTO commands.
"""
import hashlib
import json
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
EXPECTED = {'agv_unified_brain.py': '9b0e01b0f8fca589fee80425677a28043d69f2125deec519a641d30bd57dea22', 'agv_navigation.py': '2436a5bf0445d48918ac4408b7ebc57b987f462abe5d5ad714464b15cd92c1c1'}


def get_telemetry():
    with urllib.request.urlopen('http://127.0.0.1:8080/api/telemetry', timeout=2) as response:
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


assert STAGE.parent == ROOT.parent and STAGE.name.startswith('agv_frontier_fix_')
pid = 33763
proc = Path(f'/proc/{pid}')
assert proc.joinpath('cwd').resolve() == ROOT
cmd = [part.decode() for part in proc.joinpath('cmdline').read_bytes().split(b'\0') if part]
assert cmd[-2:] == ['agv_unified_brain.py', '--operator-control'], cmd
env = dict(part.decode().split('=', 1) for part in proc.joinpath('environ').read_bytes().split(b'\0') if part)
exe = str(proc.joinpath('exe').resolve())
for name, expected in EXPECTED.items():
    assert digest(ROOT / name) == expected, f'Live file changed: {name}'
    assert (STAGE / name).is_file()
for name in EXPECTED:
    compile((STAGE / name).read_text(), name, 'exec')
for _ in range(3):
    assert stationary(get_telemetry(), True), 'Vehicle is not freshly confirmed stationary; aborted'
    time.sleep(.15)

backup = STAGE / 'backup'
backup.mkdir()
for name in EXPECTED:
    shutil.copy2(ROOT / name, backup / name)
before = get_telemetry()
(STAGE / 'before.json').write_text(json.dumps(before, ensure_ascii=False, indent=2))
terminate(pid)
print('Original controller stopped gracefully; LiDAR/SLAM unchanged', flush=True)


def launch():
    with (ROOT / 'runtime' / 'brain.log').open('ab', buffering=0) as log:
        return subprocess.Popen(cmd, executable=exe, cwd=ROOT, env=env,
                                stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                                start_new_session=True)


child = None
try:
    for name in EXPECTED:
        target = ROOT / name
        staged = ROOT / (name + '.frontier-fix-new')
        shutil.copy2(STAGE / name, staged)
        staged.chmod(target.stat().st_mode)
        os.replace(staged, target)
    child = launch()
    (ROOT / 'runtime' / 'brain.pid').write_text(str(child.pid) + '\n')
    deadline = time.monotonic() + 15
    last_error = None
    while time.monotonic() < deadline:
        assert child.poll() is None, f'Controller exited: {child.returncode}'
        try:
            after = get_telemetry()
            if stationary(after) and after['control'].get('fault') is None:
                break
        except Exception as exc:
            last_error = type(exc).__name__
        time.sleep(.25)
    else:
        raise RuntimeError(f'No fresh disarmed telemetry after restart: {last_error}')
    (STAGE / 'after.json').write_text(json.dumps(after, ensure_ascii=False, indent=2))
    result = dict(pid=child.pid, backup=str(backup), status='APPLIED_DISARMED',
                  hashes={name: digest(ROOT / name) for name in EXPECTED})
    (STAGE / 'result.json').write_text(json.dumps(result, indent=2))
    print(json.dumps(result), flush=True)
except Exception:
    if child is not None and child.poll() is None:
        terminate(child.pid)
    for name in EXPECTED:
        shutil.copy2(backup / name, ROOT / name)
    old = launch()
    (ROOT / 'runtime' / 'brain.pid').write_text(str(old.pid) + '\n')
    print(f'Rolled back original files; controller PID {old.pid}', flush=True)
    raise
