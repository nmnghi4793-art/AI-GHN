with open('app.js', 'r', encoding='utf-8') as f:
    lines = f.readlines()

depth = 0
for idx, line in enumerate(lines):
    # Remove string literals and comments
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

    if depth < 0:
        print(f"Negative depth at line {idx+1}: {depth}")

print(f"Final depth at end of file (line {len(lines)}): {depth}")
