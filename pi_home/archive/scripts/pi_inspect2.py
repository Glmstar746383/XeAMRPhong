import re

B = '/home/khangho/agv_codex_reader_20261003_0652/'
brain = open(B + 'agv_unified_brain.py', encoding='utf-8').read()
sess = open(B + 'agv_command_session.py', encoding='utf-8').read()

print('=== safety_status uses (brain) ===')
for m in re.finditer(r'safety_status', brain):
    line = brain[:m.start()].count('\n') + 1
    ctx = brain[max(0, m.start() - 80):m.start() + 90].replace('\n', ' ')
    print(line, ctx)

print()
print('=== session defs ===')
for m in re.finditer(r'^\s*def (\w+)\(', sess, re.M):
    print(m.group(1))
