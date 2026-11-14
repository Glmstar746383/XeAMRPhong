import os
import py_compile
import re

P = '/home/khangho/agv_codex_reader_20261003_0652/agv_command_session.py'
s = open(P, encoding='utf-8').read()

old = ("normal=(self.auto_speed_rpm if abs(sum(wheels))>1e-8 else self.auto_turn_rpm) "
       "if autonomous else (max(NORMAL_RPM, min(max_s, max(abs(w) for w in wheels))) "
       "if (is_op and parts[0] == 'S') else max(NORMAL_RPM, min(135.0, max(abs(w) for w in wheels))))")
new = ("normal=(self.auto_speed_rpm if abs(sum(wheels))>1e-8 else self.auto_turn_rpm) "
       "if autonomous else (max(SLOW_RPM, min(max_s, max(abs(w) for w in wheels))) "
       "if (is_op and parts[0] == 'S') else max(SLOW_RPM, min(135.0, max(abs(w) for w in wheels))))")

print('old present:', s.count(old))
assert s.count(old) == 1, s.count(old)

out = s.replace(old, new)
open(P + '.bak_manual_floor_20261102', 'w', encoding='utf-8', newline='').write(s)
open(P, 'w', encoding='utf-8', newline='').write(out)
py_compile.compile(P, doraise=True)
print('patched + compiled')

line = [l for l in out.splitlines() if 'normal=(self.auto_speed_rpm' in l]
print('now:', line[0].strip()[:240] if line else 'missing')
