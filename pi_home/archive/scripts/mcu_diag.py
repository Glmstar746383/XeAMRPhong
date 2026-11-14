import json
import time

import serial

ser = serial.Serial('/dev/ttyUSB0', 115200, timeout=0.05)
ser.reset_input_buffer()
time.sleep(0.3)


def pump(seconds, label):
    print(f'-- {label}')
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
                print('   raw:', txt[:100])
                continue
            if 'safety' in obj:
                continue
            print('   resp:', json.dumps(obj, ensure_ascii=False)[:160])


def send(cmd, seconds=0.7, label=None):
    print(f'>> {cmd}')
    ser.write((cmd + '\n').encode())
    pump(seconds, label or cmd)


try:
    pump(0.8, 'idle')
    send('PING', 0.5)
    send('CLEAR_FAULT', 1.2)
    send('ARM', 0.7)
    send('S 40 40', 0.6)
    send('STOP', 0.6)
finally:
    ser.write(b'STOP\n')
    ser.write(b'DISARM\n')
    time.sleep(0.3)
    ser.close()
    print('closed')
