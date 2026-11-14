import json
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = 'http://127.0.0.1:8080'
MPS_PER_RPM = 0.0038326


def call(path, timeout=6):
    try:
        with urllib.request.urlopen(BASE + path, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode())


def telemetry():
    try:
        with urllib.request.urlopen(BASE + '/api/telemetry', timeout=4) as r:
            return json.loads(r.read().decode())
    except Exception:
        return {}


def cmd(val):
    return call('/api/cmd?val=' + urllib.parse.quote(val))


print('== initial telemetry ==')
t = telemetry()
c = t.get('control', {})
print('  status', t.get('status'), '| armed', c.get('armed'), '| fault', c.get('fault'),
      '| d0_age', c.get('d0_age_s'), '| preflight', c.get('preflight_count'))

print('== STOP ==')
print(' ', cmd('STOP'))
time.sleep(1.2)

print('== ARM ==')
print(' ', cmd('ARM'))
time.sleep(0.5)

for rpm in (40, 135):
    v = rpm * MPS_PER_RPM
    print(f'== V {v:.3f} 0  ({rpm} RPM) x1.6s ==')
    peaks = []
    end = time.time() + 1.6
    while time.time() < end:
        cmd(f'V {v:.4f} 0')
        t = telemetry()
        rob = t.get('robot', {})
        peaks.append(abs(rob.get('l_rpm', 0)))
        time.sleep(0.12)
    print(f'   peak l_rpm {max(peaks) if peaks else None:.1f} | final {peaks[-1] if peaks else None:.1f}')
    cmd('STOP')
    time.sleep(1.0)
    cmd('ARM')
    time.sleep(0.4)

print('== final STOP ==')
print(' ', cmd('STOP'))
t = telemetry()
print('  armed', t.get('control', {}).get('armed'), '| robot', t.get('robot'))
