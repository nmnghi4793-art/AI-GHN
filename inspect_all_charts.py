import re
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

with open('c:/Users/Admin/.gemini/antigravity/scratch/ghn_dashboard/app.js', 'r', encoding='utf-8') as f:
    content = f.read()

# Find chart definitions
chart_names = [
    'gtcTrend', 'b2bPrioTrend', 'fdTrend', 'donTao', 'backlog', 'nangSuat'
]

for name in chart_names:
    print(f"=== CHART: {name} ===")
    # Search for "new Chart(" containing the name or charts.name
    # Let's find matches in the js file
    pattern = r'(charts\.' + name + r'|' + name + r')\s*=\s*new\s+Chart\([^)]+\)'
    # Since Chart config spans multiple lines, let's find the assignment and print next 50 lines
    pos = 0
    while True:
        match = re.search(r'(charts\.' + name + r'|' + name + r')\s*=\s*new\s+Chart', content[pos:])
        if not match:
            break
        start_idx = pos + match.start()
        # Find matching closing parenthesis for new Chart(...)
        # Simple bracket matching
        bracket_count = 0
        end_idx = start_idx
        for j in range(start_idx, len(content)):
            if content[j] == '(':
                bracket_count += 1
            elif content[j] == ')':
                bracket_count -= 1
                if bracket_count == 0:
                    end_idx = j + 1
                    break
        chart_code = content[start_idx:end_idx]
        print(chart_code)
        print("-" * 40)
        pos = start_idx + len(match.group(0)) + 1
