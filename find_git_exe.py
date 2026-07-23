import os, sys

print("Searching for git.exe on C:\\ ...")
matches = []
for root, dirs, files in os.walk("C:\\"):
    if "git.exe" in files:
        full_path = os.path.join(root, "git.exe")
        print("FOUND GIT:", full_path)
        matches.append(full_path)
    # Skip huge dirs
    dirs[:] = [d for d in dirs if d.lower() not in ("windows", "$recycle.bin", "node_modules", ".venv", "site-packages")]

print(f"Done search. Total found: {len(matches)}")
