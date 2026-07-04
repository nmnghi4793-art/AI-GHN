import os
import glob

files = glob.glob('*.py') + glob.glob('backend/*.py')
for f in files:
    try:
        with open(f, 'r', encoding='utf-8') as fh:
            content = fh.read()
            if 'service_account' in content or 'alien-oarlock' in content or 'build(' in content:
                print(f"Found in {f}")
    except Exception as e:
        pass
