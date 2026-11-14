import hashlib
import json
import os
import shutil

ROOT = '/home/khangho/agv_codex_reader_20261003_0652'
BACKUP = '/home/khangho/agv_straight_tracking_20261023_015700/backup'
res = {}
for f in ['agv_unified_brain.py', 'agv_speed_profile.py']:
    src = os.path.join(ROOT, f)
    dst = os.path.join(BACKUP, f)
    shutil.copy2(src, dst)
    with open(dst, 'rb') as fp:
        res[f] = hashlib.sha256(fp.read()).hexdigest()
print('BACKUP_START')
print(json.dumps(res))
print('BACKUP_END')
