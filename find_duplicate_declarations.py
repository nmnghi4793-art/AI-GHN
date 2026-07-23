import re

with open('app.js', 'r', encoding='utf-8') as f:
    lines = f.readlines()

declarations = {}
duplicates = []

for i, line in enumerate(lines):
    # Match let or const at top-level or inside root scope
    m = re.match(r'^(?:let|const|var)\s+([a-zA-Z0-9_$]+)\s*=', line.strip())
    if m:
        var_name = m.group(1)
        if var_name in declarations:
            duplicates.append((var_name, declarations[var_name], i + 1))
        else:
            declarations[var_name] = i + 1

print("=== DUPLICATE TOP-LEVEL VARIABLE DECLARATIONS IN APP.JS ===")
if duplicates:
    for var_name, line1, line2 in duplicates:
        print(f"DUPLICATE: '{var_name}' declared on line {line1} AND line {line2}")
else:
    print("NO DUPLICATE TOP-LEVEL DECLARATIONS FOUND!")
