with open('app.js', 'r', encoding='utf-8') as f:
    lines = f.readlines()

for idx, line in enumerate(lines):
    if 'await ' in line:
        # Check preceding 50 lines for async function declaration
        start_search = max(0, idx - 50)
        preceding = "".join(lines[start_search:idx+1])
        if 'async function' not in preceding and 'async (' not in preceding and 'async (' not in line and 'async function' not in line and 'async (e' not in preceding:
            print(f"Line {idx+1}: {line.strip()[:90]}")
