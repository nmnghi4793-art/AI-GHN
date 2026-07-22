import sys, os, re

sys.stdout.reconfigure(encoding='utf-8')

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAIN_PY = os.path.join(BASE_DIR, "main.py")

with open(MAIN_PY, "r", encoding="utf-8", errors="ignore") as f:
    text = f.read()

print("--- SEARCHING FOR JSON / FILE SAVES IN MAIN.PY ---")
for line_no, line in enumerate(text.splitlines(), 1):
    if any(k in line.lower() for k in ["xe", "daily", "save", "write", "dump", "json", "open(", "sheet"]):
        if any(term in line.lower() for term in ["xe", "daily", "kpi", "storage", "data"]):
            print(f"L{line_no}: {line.strip()[:120]}")

print("\n--- ALL CONSTANTS / PATHS IN MAIN.PY ---")
for line_no, line in enumerate(text.splitlines(), 1):
    if line.strip().startswith(("DATA_DIR", "STORAGE", "PATH", "FILE", "JSON", "SHEET")):
        print(f"L{line_no}: {line.strip()}")
