import urllib.request
import zipfile
import os
import subprocess

scratch_dir = r"C:\Users\Admin\.gemini\antigravity-ide\scratch\ghn_dashboard\scratch"
zip_path = os.path.join(scratch_dir, "MinGit.zip")
git_dir = os.path.join(scratch_dir, "MinGit")

url = "https://github.com/git-for-windows/git/releases/download/v2.43.0.windows.1/MinGit-2.43.0-64-bit.zip"

print(f"Downloading MinGit from {url}...")
urllib.request.urlretrieve(url, zip_path)
print("Download complete. Extracting...")

with zipfile.ZipFile(zip_path, 'r') as zip_ref:
    zip_ref.extractall(git_dir)

print("Extraction complete!")
git_exe = os.path.join(git_dir, "cmd", "git.exe")
res = subprocess.run([git_exe, "--version"], capture_output=True, text=True)
print(f"Git version check: {res.stdout.strip()}")
