import shutil
import os
ROOT = '/home/khangho/agv_codex_reader_20261003_0652'
BACKUP = '/home/khangho/agv_straight_tracking_20261023_015700/backup'
for f in ['agv_unified_brain.py', 'agv_speed_profile.py']:
    shutil.copy2(os.path.join(BACKUP, f), os.path.join(ROOT, f))
print('ROLLED_BACK')
