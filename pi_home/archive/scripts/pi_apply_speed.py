"""Apply the manual-speed unlock to the deployed AGV stack (run on the Pi).

    python3 pi_apply_speed.py --apply
"""
import os
import py_compile
import shutil
import sys
import time

ROOT = os.path.expanduser('~/agv_codex_reader_20261003_0652')
APPLY = '--apply' in sys.argv

RULES = {
    'agv_speed_profile.py': [
        ('if not (10.0 <= normal_rpm <= 100.0):',
         'if not (10.0 <= normal_rpm <= 140.0):'),
    ],
    'agv_command_session.py': [
        ('max_s = NORMAL_RPM if (autonomous or not is_op) else 100.0',
         'max_s = 140.0 if (is_op and not autonomous) else NORMAL_RPM'),
        ('else NORMAL_RPM)',
         'else max(NORMAL_RPM, min(135.0, max(abs(w) for w in wheels))))'),
    ],
    'agv_unified_brain.py': [
        ("if spd_rpm not in (SLOW_RPM, NORMAL_RPM) or trn_rpm not in (SLOW_RPM, NORMAL_RPM):",
         "if not (SLOW_RPM <= spd_rpm <= 135.0) or not (SLOW_RPM <= trn_rpm <= 135.0):"),
        ("raise ValueError('Chọn tốc độ 40 hoặc 65 RPM')",
         "raise ValueError('Chọn tốc độ 40-135 RPM')"),
    ],
}

stamp = time.strftime('%Y%m%d_%H%M%S')
total = 0
for name, rules in RULES.items():
    path = os.path.join(ROOT, name)
    if not os.path.exists(path):
        print('MISSING', path)
        continue
    src = open(path, encoding='utf-8').read()
    out = src
    print('==', path)
    ok = True
    for old, new in rules:
        if new in out:
            print('   already patched:', old[:44])
            continue
        n = out.count(old)
        print(f'   count={n}: {old[:60]}')
        if n != 1:
            ok = False
            continue
        out = out.replace(old, new)
    if out == src:
        print('   unchanged')
        continue
    if not ok:
        print('   SKIPPED (ambiguous match)')
        continue
    if APPLY:
        shutil.copy2(path, path + f'.bak_speed_{stamp}')
        open(path, 'w', encoding='utf-8', newline='').write(out)
        py_compile.compile(path, doraise=True)
        print('   applied + compiled')
        total += 1
    else:
        print('   would apply')
        total += 1

print()
print(f"{'APPLIED' if APPLY else 'DRY RUN'}: {total} file(s)")
