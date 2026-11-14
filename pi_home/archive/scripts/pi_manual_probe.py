import json
import urllib.error
import urllib.request

base = 'http://127.0.0.1:8080'


def call(path):
    try:
        with urllib.request.urlopen(base + path, timeout=10) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode())


s, t = call('/api/telemetry')
c = t.get('control', {})
print('telemetry: status', t.get('status'), '| armed', c.get('armed'), '| fault', c.get('fault'),
      '| d0_age', c.get('d0_age_s'))
print('  min_m', t.get('min_m'), '| zones front/back/left/right',
      {k: (t.get('zones') or {}).get(k) for k in ('front', 'back', 'left', 'right')})

for val in ('V 0.15 0', 'V -0.15 0', 'V 0 0.5'):
    s, r = call('/api/cmd?val=' + urllib.parse.quote(val))
    print(f'cmd {val!r:12s} -> http {s} | status {r.get("status")} | reason {r.get("reason")} | blockers {r.get("blockers")}')
