with open('app.js', 'r', encoding='utf-8') as f:
    lines = f.readlines()

depth = 0
for idx in range(1720, len(lines)):
    line = lines[idx]
    prev_depth = depth
    clean = ""
    in_str = None
    j = 0
    while j < len(line):
        c = line[j]
        if in_str:
            if c == '\\':
                j += 1
            elif c == in_str:
                in_str = None
        else:
            if c in ('"', "'", '`'):
                in_str = c
            elif c == '/' and j + 1 < len(line) and line[j+1] == '/':
                break
            else:
                clean += c
        j += 1

    for c in clean:
        if c == '{':
            depth += 1
        elif c == '}':
            depth -= 1

    if prev_depth == 0 and depth > 0:
        print(f"Line {idx+1} [ENTER DEPTH {depth}]: {line.strip()[:80]}")
    elif prev_depth > 0 and depth == 0:
        print(f"Line {idx+1} [LEAVE DEPTH 0]: {line.strip()[:80]}")

print(f"\nFinal Depth from 1720: {depth}")
