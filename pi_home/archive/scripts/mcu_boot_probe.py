import serial
import time

s = serial.Serial('/dev/ttyUSB0', 115200, timeout=0.3)
# pulse DTR to force a clean MCU boot
s.dtr = False
time.sleep(0.1)
s.dtr = True
time.sleep(0.1)
s.reset_input_buffer()

end = time.time() + 15
buf = b''
while time.time() < end:
    buf += s.read(256)
s.close()

lines = [l for l in buf.split(b'\r\n') if l.strip()]
print('bytes', len(buf), 'lines', len(lines))
for l in lines[:25]:
    print(l[:140])
