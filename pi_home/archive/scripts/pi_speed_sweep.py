import json
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = 'http://127.0.0.1:8080'
MPS_PER_RPM = 0.0038326


def call(path):
    try:
        with urllib.request.urlopen(BASE + path, timeout=6) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode())
        except Exception:
            return e.code, {}
    except Exception as e:
        return 0, {'error': str(e)}


def tel():
    try:
        with urllib.request.urlopen(BASE + '/api/telemetry', timeout=4) as r:
            return json.loads(r.read().decode())
    except Exception:
        return {}


def cmd(v):
    return call('/api/cmd?val=' + urllib.parse.quote(v))


print('STOP:', cmd('STOP'))
time.sleep(1.0)

for rpm in (40, 50, 60, 70, 130, 135):
    r = cmd('ARM')
    time.sleep(0.35)
    v = rpm * MPS_PER_RPM
    samples = []
    end = time.time() + 1.15
    while time.time() < end:
        cmd(f'V {v:.4f} 0')
        t = tel()
        rob = t.get('robot', {})
        samples.append((rob.get('l_rpm', 0), rob.get('l_rpm', 0)))
        time.sleep(0.1)
    cmd('STOP')
    time.sleep(0.8)
    tail = samples[-5:]
    settled = sum(abs(x[0]) for x in tail) / len(tail) if tail else 0
    peak = max((abs(x[0]) for x in samples), default=0)
    arm_ok = r[1].get('reason', '?')
    print(f'{rpm:3d} RPM -> ARM {arm_ok:16s} peak {peak:6.1f} | settled {settled:6.1f}')

print('final STOP:', cmd('STOP'))
time.sleep(0.6)
t = tel()
print('robot:', t.get('robot'), '| armed', t.get('control', {}).get('armed'))
