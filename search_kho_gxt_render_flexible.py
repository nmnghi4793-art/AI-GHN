with open("c:/Users/Admin/.gemini/antigravity/scratch/ghn_dashboard/app.js", "r", encoding="utf-8") as f:
    content = f.read()

lines = content.split('\n')
for idx, line in enumerate(lines):
    if "khoGxtData" in line:
        print(f"Line {idx+1}: {line.strip()[:120]}")
        # Print a block around it if it looks like a rendering loop
        if ".map(" in line or ".forEach(" in line or "render" in line:
            start = max(0, idx - 5)
            end = min(len(lines), idx + 35)
            print("--- CONTEXT ---")
            for j in range(start, end):
                print(f"  Line {j+1}: {lines[j].strip()[:140]}")
            print("----------------")
