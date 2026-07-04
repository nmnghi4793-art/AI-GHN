import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

with open("c:/Users/Admin/.gemini/antigravity/scratch/ghn_dashboard/app.js", "r", encoding="utf-8") as f:
    lines = f.readlines()

for j in range(2460, min(2550, len(lines))):
    print(f"Line {j+1}: {lines[j].strip()}")
