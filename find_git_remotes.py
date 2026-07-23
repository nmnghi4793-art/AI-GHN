import os, sys

print("Searching for git config or remotes under C:\\Users\\Admin ...")
for root, dirs, files in os.walk(r"C:\Users\Admin"):
    if "config" in files and ".git" in root:
        full = os.path.join(root, "config")
        print("GIT CONFIG AT:", full)
        try:
            with open(full, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                print(content[:300])
        except Exception as e:
            print("Error reading:", e)

print("Done search.")
