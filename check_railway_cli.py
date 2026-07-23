import subprocess, shutil, os

print("Shutil railway:", shutil.which("railway"))

# Check npx railway
res = subprocess.run("npx --no-install railway status", shell=True, capture_output=True, text=True)
print("npx railway status stdout:", res.stdout)
print("npx railway status stderr:", res.stderr)
