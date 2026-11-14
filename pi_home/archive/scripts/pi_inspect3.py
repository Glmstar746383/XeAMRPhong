import re

P = '/home/khangho/agv_codex_reader_20261003_0652/agv_command_session.py'
s = open(P, encoding='utf-8').read()


def show(name, n=2600):
    m = re.search(r'\n    def ' + name + r'\(', s)
    if not m:
        print('missing', name)
        return
    print('=' * 25, name, 'line', s[:m.start()].count('\n') + 1)
    print(s[m.start():m.start() + n])


for name in ('send_raw', 'drive'):
    show(name)

print('=' * 25, 'scan_clear / hold_for_scan uses')
for m in re.finditer(r'scan_clear|hold_for_scan|scan_holding', s):
    line = s[:m.start()].count('\n') + 1
    ctx = s[max(0, m.start() - 100):m.start() + 120].replace('\n', ' ')
    print(line, ctx)
