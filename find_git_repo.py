import os

print("Searching for .git folder on C:\\ ...")
for root, dirs, files in os.walk("C:\\Users\\Admin"):
    if ".git" in dirs:
        full_path = os.path.join(root, ".git")
        print("FOUND GIT REPO AT:", root)
    # Skip huge dirs
    dirs[:] = [d for d in dirs if d.lower() not in ("windows", "$recycle.bin", "node_modules", ".venv", "site-packages", "appdata")]

print("Done search.")
