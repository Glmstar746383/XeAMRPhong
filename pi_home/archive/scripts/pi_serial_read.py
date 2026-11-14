import time

import serial

s = serial.Serial('/dev/ttyUSB0', 115200, timeout=0.3)
s.reset_input_buffer()
end = time.time() + 5
buf = b''
while time.time() < end:
    buf += s.read(512)
s.close()

lines = [l for l in buf.split(b'\r\n') if l.strip()]
print('bytes', len(buf), 'lines', len(lines))
seen = set()
for l in lines[:200]:
    txt = l.decode('utf-8', 'replace')
    key = txt[:40]
    if key in seen:
        continue
    seen.add(key)
    print(txt[:160])
