with open("c:/Users/Admin/.gemini/antigravity/scratch/ghn_dashboard/app.js", "r", encoding="utf-8") as f:
    lines = f.readlines()

for idx, line in enumerate(lines):
    if "Danh Sách Kho GXT" in line or "Tên nhân viên" in line or "Tên kho GXT" in line:
        print(f"Line {idx+1}: {line.strip()[:150]}")
        # print around it
        for j in range(max(0, idx-5), min(idx+25, len(lines))):
            print(f"  Line {j+1}: {lines[j].strip()[:150]}")
