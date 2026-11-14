import json
import time
import urllib.parse
import urllib.request

BASE = 'http://127.0.0.1:8080'
V = 40 * 0.0038326


def call(path):
    with urllib.request.urlopen(BASE + path, timeout=6) as r:
        return json.loads(r.read().decode())


def tel():
    with urllib.request.urlopen(BASE + '/api/telemetry', timeout=4) as r:
        return json.loads(r.read().decode())


print('STOP', call('/api/cmd?val=STOP')['reason'])
time.sleep(1.0)
print('ARM', call('/api/cmd?val=ARM')['reason'])
time.sleep(0.4)

end = time.time() + 2.2
while time.time() < end:
    call('/api/cmd?val=' + urllib.parse.quote(f'V {V:.4f} 0'))
    t = tel()
    rob = t.get('robot', {})
    print(f"  tgt {rob.get('l_tgt', '?'):>6} rpm {rob.get('l_rpm', 0):6.1f} pwm {rob.get('l_pwm', 0):4}")
    time.sleep(0.15)

print('STOP', call('/api/cmd?val=STOP')['reason'])
