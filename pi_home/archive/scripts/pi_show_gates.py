P = '/home/khangho/agv_codex_reader_20261003_0652/agv_command_session.py'
lines = open(P, encoding='utf-8').read().splitlines()
for i in range(499, 600):
    print(i + 1, lines[i])
