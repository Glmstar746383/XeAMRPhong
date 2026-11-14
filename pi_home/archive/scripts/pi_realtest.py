import json
import time
import urllib.parse
import urllib.request

BASE = 'http://127.0.0.1:8080'
MPS_PER_RPM = 0.0038326


def call(path):
    with urllib.request.urlopen(BASE + path, timeout=6) as r:
        return json.loads(r.read().decode())


def tel():
    with urllib.request.urlopen(BASE + '/api/telemetry', timeout=4) as r:
        return json.loads(r.read().decode())


def odom():
    r = tel().get('robot', {})
    return (r.get('x', 0.0), r.get('y', 0.0), r.get('th', 0.0))


def run(rpm, seconds):
    v = rpm * MPS_PER_RPM
    print(f'--- {rpm} RPM (V {v:.4f}) for {seconds}s ---')
    call('/api/cmd?val=STOP')
    time.sleep(0.8)
    x0, y0, th0 = odom()
    a = call('/api/cmd?val=ARM')
    print('  ARM:', a.get('reason'))
    time.sleep(0.3)
    t0 = time.time()
    while time.time() - t0 < seconds:
        call('/api/cmd?val=' + urllib.parse.quote(f'V {v:.4f} 0'))
        rob = tel().get('robot', {})
        print(f'  t={time.time()-t0:4.1f}s  l_rpm={rob.get("l_rpm",0):6.1f}  r_rpm={rob.get("r_rpm",0):6.1f}  pwm={rob.get("l_pwm",0):4}')
        time.sleep(0.2)
    print('  STOP:', call('/api/cmd?val=STOP').get('reason'))
    time.sleep(0.9)
    x1, y1, th1 = odom()
    dist = ((x1 - x0) ** 2 + (y1 - y0) ** 2) ** 0.5
    expect = v * seconds
    print(f'  odometry: ({x0:.3f},{y0:.3f}) -> ({x1:.3f},{y1:.3f})  dist={dist:.3f} m  expected~{expect:.3f} m')
    print()


try:
    run(40, 2.0)
    run(135, 1.5)
finally:
    call('/api/cmd?val=STOP')
    print('final STOP sent')
