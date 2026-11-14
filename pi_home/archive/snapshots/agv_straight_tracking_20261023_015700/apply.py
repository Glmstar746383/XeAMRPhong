import hashlib
import json
import os
import shutil

ROOT = '/home/khangho/agv_codex_reader_20261003_0652'
STAGE = '/home/khangho/agv_straight_tracking_20261023_015700'

for f in ['agv_unified_brain.py', 'agv_speed_profile.py']:
    src = os.path.join(STAGE, f)
    dst = os.path.join(ROOT, f)
    tmp = os.path.join(ROOT, f + '.straight-fix-new')
    shutil.copy2(src, tmp)
    if os.path.exists(dst):
        os.chmod(tmp, os.stat(dst).st_mode)
    else:
        os.chmod(tmp, 0o644)
    os.replace(tmp, dst)

hashes = {}
for f in ['agv_unified_brain.py', 'agv_speed_profile.py']:
    p = os.path.join(ROOT, f)
    with open(p, 'rb') as fp:
        hashes[f] = hashlib.sha256(fp.read()).hexdigest()

print('APPLY_START')
print(json.dumps(hashes))
print('APPLY_END')
