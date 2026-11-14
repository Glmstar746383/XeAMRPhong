#!/bin/bash
pkill -9 -f agv_unified_brain.py 2>/dev/null || true
rm -f /tmp/agv_collector__dev_ttyUSB0.lock
source /opt/ros/jazzy/setup.bash
cd /home/khangho/agv
python3 -B -u agv_unified_brain.py --operator-control > runtime/brain.log 2>&1 &
sleep 2
ps aux | grep agv_unified_brain
