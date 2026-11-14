cd ~/agv_codex_reader_20261003_0652 || exit 1
grep -n "40-135" *.py
grep -n "SLOW_RPM" agv_speed_profile.py | head -5
for q in "speed=40&turn=40" "speed=100&turn=100" "speed=135&turn=100" "speed=135&turn=135" "speed=134&turn=134"; do
  printf '%s -> ' "$q"
  curl -s -m 5 "http://127.0.0.1:8080/api/auto_config?$q" | head -c 110
  echo
done
echo ---
grep -n "auto_target_speed_rpm\|auto_target_turn_rpm" agv_unified_brain.py | head -8
