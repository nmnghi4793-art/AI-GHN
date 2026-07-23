import sys
sys.stdout.reconfigure(encoding='utf-8')

with open('app.js', 'r', encoding='utf-8') as f:
    lines = f.readlines()

depth = 0
for idx, line in enumerate(lines):
    # Strip comments and strings roughly
    clean_line = ""
    in_str = None
    j = 0
    while j < len(line):
        ch = line[j]
        if in_str:
            if ch == '\\':
                j += 1
            elif ch == in_str:
                in_str = None
        else:
            if ch in ('"', "'", '`'):
                in_str = ch
            elif ch == '/' and j + 1 < len(line) and line[j+1] == '/':
                break
            else:
                clean_line += ch
        j += 1

    for ch in clean_line:
        if ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1

    if 'await ' in clean_line and depth <= 1:
        print(f"Line {idx+1} (depth={depth}): {line.strip()[:90]}")
