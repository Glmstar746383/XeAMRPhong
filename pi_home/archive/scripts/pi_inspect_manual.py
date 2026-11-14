import re

P = '/home/khangho/agv_codex_reader_20261003_0652/agv_unified_brain.py'
s = open(P, encoding='utf-8').read()

print('len', len(s))
for pat in ('min_m', 'zones', 'front_obstacle', 'obstacle', 'hold', 'blocked', 'veto'):
    print(pat, len(re.findall(pat, s)))

print('\n=== cmd handler ===')
m = re.search(r"elif path == '/api/cmd'", s)
print(s[m.start():m.start() + 1200] if m else 'not found')

print('\n=== zone veto candidates ===')
for mm in re.finditer(r'zones', s):
    line_start = s.rfind('\n', 0, mm.start() - 200)
    ctx = s[max(0, mm.start() - 220):mm.start() + 220].replace('\n', '\n  ')
    print('---', s[:mm.start()].count('\n') + 1)
    print('  ' + ctx)
