import sys, time
sys.path.insert(0, '/home/khangho/agv')
from cam_avoid import CamAvoid

c = CamAvoid(enabled=True, stop_m=0.30, clear_m=0.45, half_w=0.25, timeout_s=2.0)
now = 1000.0

def show(label, allow, reason, info):
    print("%-34s allow=%-5s reason=%-14s status=%s d=%s x=%s" %
          (label, allow, reason, info.get('status'),
           None if info.get('d') is None else round(info['d'], 2),
           None if info.get('x') is None else round(info['x'], 2)))

# 1. khong co du lieu -> fail open
show("no data", *c.gate(0.12, now))

# 2. duong trong
c.feed_range(9.9, now)
show("clear 9.9", *c.gate(0.12, now))

# 3. vat o 0.20m -> chan
c.feed_range(0.20, now)
show("obstacle 0.20m", *c.gate(0.12, now))

# 4. vat 0.35m trong tre (giua stop 0.30 va clear 0.45) -> van chan
c.feed_range(0.35, now)
show("obstacle 0.35m (hysteresis)", *c.gate(0.12, now))

# 5. 0.50m -> nha
c.feed_range(0.50, now)
show("obstacle 0.50m", *c.gate(0.12, now))

# 6. vat lech ngang 0.40m -> khong chan
c.feed_range(0.20, now); c.feed_obstacle(0.40, 0.20, now)
show("0.20m nhung lech 0.40m", *c.gate(0.12, now))

# 7. lui -> khong chan
c.feed_obstacle(0.0, 0.20, now)
show("vat 0.20m nhung LUI (v<0)", *c.gate(-0.10, now))

# 8. du lieu cu -> fail open
show("vat 0.20m nhung cu 3s", *c.gate(0.12, now + 3.0))

# 9. gate_cmd voi lenh M
c.feed_range(0.18, now)
show("lenh 'M 10 10'", *c.gate_cmd('M 10 10', now))
show("lenh 'M -10 -10'", *c.gate_cmd('M -10 -10', now))
show("lenh 'V 0.000 0.000'", *c.gate_cmd('V 0.000 0.000', now))

# 10. simulate
allow, reason, info = c.simulate(0.12, 0.15)
show("simulate d=0.15", allow, reason, info)

print("\nTAT CA OK neu: 1,2,5,6,7,8,10 allow=True; 3,4 allow=False; 9 M10 True / M-10 True")
