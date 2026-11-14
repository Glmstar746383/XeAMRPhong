import re

B = '/home/khangho/agv_codex_reader_20261003_0652/'
brain = open(B + 'agv_unified_brain.py', encoding='utf-8').read()
sess = open(B + 'agv_command_session.py', encoding='utf-8').read()

print('=== f_cone context ===')
i = brain.find('f_cone_min')
print(brain[max(0, i - 900):i + 1400])

print()
print('=== session: zone/obstacle hits ===')
for pat in ('zone', 'obstacle', 'hold', 'ZONE', 'min_m'):
    print(pat, len(re.findall(pat, sess)))

print()
print('=== send_cmd def ===')
m = re.search(r'def send_cmd\(', sess)
print(sess[m.start():m.start() + 3200] if m else 'not found')
