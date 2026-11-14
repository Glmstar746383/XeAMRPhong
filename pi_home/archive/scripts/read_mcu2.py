import serial
import time

s = serial.Serial('/dev/ttyUSB0', 115200, timeout=0.5)
s.reset_input_buffer()
end = time.time() + 6
buf = b''
while time.time() < end:
    buf += s.read(256)
s.close()
print('bytes:', len(buf))
for line in buf.split(b'\r\n')[:40]:
    if line.strip():
        print(line[:160])
