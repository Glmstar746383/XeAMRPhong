import json
import time
import urllib.request

url = 'http://127.0.0.1:8080/api/telemetry'
for i in range(5):
    d = json.load(urllib.request.urlopen(url, timeout=5))
    c = d.get('control', {})
    d0 = c.get('latest_d0') or {}
    print(i, 'd0_age', c.get('d0_age_s'), 'preflight', c.get('preflight_count'),
          'safety', d0.get('safety'), 'l_rpm', d0.get('l_rpm'), 'r_rpm', d0.get('r_rpm'),
          'fault', c.get('fault'))
    time.sleep(2)
