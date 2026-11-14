import hashlib
import json
import os

STAGE = '/home/khangho/agv_straight_tracking_20261023_015700'
res = {}
for f in ['agv_unified_brain.py', 'agv_speed_profile.py']:
    p = os.path.join(STAGE, f)
    with open(p, 'rb') as fp:
        res[f] = hashlib.sha256(fp.read()).hexdigest()
print('STAGE_START')
print(json.dumps(res))
print('STAGE_END')
