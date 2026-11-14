import serial

try:
    s = serial.Serial('/dev/ttyUSB0', 115200, timeout=3)
except Exception as e:
    print('open failed', e)
    raise SystemExit

s.reset_input_buffer()
data = s.read(200)
print('bytes:', len(data))
print('head:', repr(data[:120]))
s.close()
