import json
import time

import serial


def read_lines(ser, seconds, collect=None):
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
                obj = None
            if obj is not None and collect is not None:
                collect.append(obj)
            elif obj is None:
                print('  <', txt[:120])
    return buf


ser = serial.Serial('/dev/ttyUSB0', 115200, timeout=0.05)
ser.reset_input_buffer()
time.sleep(0.3)

try:
    print('== ARM ==')
    ser.write(b'ARM\n')
    read_lines(ser, 0.8)

    for rpm in (40, 80, 135):
        print(f'== S {rpm} {rpm} (1.6s) ==')
        samples = []
        end = time.time() + 1.6
        while time.time() < end:
            ser.write(f'S {rpm} {rpm}\n'.encode())
            read_lines(ser, 0.15, samples)
        peaks = [abs(s.get('l_rpm', 0)) for s in samples if 'l_rpm' in s]
        pwms = [s.get('l_pwm', 0) for s in samples if 'l_pwm' in s]
        tgts = [s.get('l_tgt', 0) for s in samples if 'l_tgt' in s]
        tgt = max(tgts) if tgts else None
        print(f'   tgt {tgt} | peak rpm {max(peaks) if peaks else None} | pwm {max(pwms) if pwms else None}')
        ser.write(b'STOP\n')
        read_lines(ser, 0.6)
        time.sleep(0.2)

    print('== STOP ==')
    ser.write(b'STOP\n')
    read_lines(ser, 0.5)
finally:
    try:
        ser.write(b'STOP\n')
        ser.write(b'DISARM\n')
    except Exception:
        pass
    ser.close()
    print('port closed, motors stopped')
