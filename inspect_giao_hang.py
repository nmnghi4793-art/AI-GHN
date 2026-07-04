with open('c:/Users/Admin/.gemini/antigravity/scratch/ghn_dashboard/giao_hang_scheduler.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if any(k in line for k in ['service_account', 'google', 'build', 'discovery', 'sheet', 'credentials']):
        print(f"Line {i+1}: {line.strip()}")
