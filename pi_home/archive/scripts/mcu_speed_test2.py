import json
import time

import serial

ser = serial.Serial('/dev/ttyUSB0', 115200, timeout=0.02)
ser.reset_input_buffer()
time.sleep(0.3)


def drain(seconds, samples=None, tags=None):
    end = time.time() + seconds
    buf = b''
    while time.time() < end:
        buf += ser.read(512)
        while b'\r\n' in buf:
            line, buf = buf.split(b'\r\n', 1)
            txt = line.decode('utf-8', 'replace').strip()
            if not txt:
                continue
            try:
                obj = json.loads(txt)
            except Exception:
                continue
            if 'safety' in obj:
                if samples is not None:
                    samples.append(obj)
            elif tags is not None:
                tags.append(obj)


def burst(rpm, seconds):
    tgt = []
    print(f'>> ARM; S {rpm} {rpm} x{seconds:.1f}s')
    ser.write(b'ARM\n')
    drain(0.15, tags=tgt)
    samples = []
    end = time.time() + seconds
    while time.time() < end:
        ser.write(f'S {rpm} {rpm}\n'.encode())
        drain(0.1, samples, tgt)
    ser.write(b'STOP\n')
    drain(0.5, tags=tgt)
    peaks = [abs(s.get('l_rpm', 0)) for s in samples]
    pwms = [abs(s.get('l_pwm', 0)) for s in samples]
    rt = [abs(s.get('r_rpm', 0)) for s in samples]
    print(f'   target={max([s.get("l_tgt", 0) for s in samples] or [0]):.1f} '
          f'peak_l={max(peaks or [0]):.1f} peak_r={max(rt or [0]):.1f} pwm={max(pwms or [0])}')
    for t in tgt[-3:]:
        print('   resp:', json.dumps(t, ensure_ascii=False)[:120])


try:
    drain(0.8)
    ser.write(b'CLEAR_FAULT\n')
    drain(1.0, tags=[])
    for rpm in (40, 80, 135):
        burst(rpm, 1.5)
        time.sleep(0.4)
finally:
    ser.write(b'STOP\n')
    ser.write(b'DISARM\n')
    time.sleep(0.3)
    ser.close()
    print('STOPPED / closed')
