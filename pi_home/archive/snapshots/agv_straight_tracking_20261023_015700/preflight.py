import os
import sys
import py_compile

STAGE = '/home/khangho/agv_straight_tracking_20261023_015700'
ROOT = '/home/khangho/agv_codex_reader_20261003_0652'

# 1. Compile both staged files
for f in ['agv_unified_brain.py', 'agv_speed_profile.py']:
    p = os.path.join(STAGE, f)
    py_compile.compile(p, doraise=True)

# 2. Test imports with STAGE first in sys.path
sys.path.insert(0, STAGE)
sys.path.insert(1, ROOT)

import agv_speed_profile
assert hasattr(agv_speed_profile, 'ARC_INNER_MIN_RPM')
assert hasattr(agv_speed_profile, 'NORMAL_RPM')
assert hasattr(agv_speed_profile, 'SLOW_RPM')

import agv_unified_brain
assert hasattr(agv_unified_brain, 'AGVROSNode')
assert hasattr(agv_unified_brain.AGVROSNode, '_shared_checked_recovery')
assert hasattr(agv_unified_brain, 'PathTarget')

print('PREFLIGHT_OK')
