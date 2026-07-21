import base64
import io
import os
import re
from PIL import Image

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
GHN_DASHBOARD_DIR = os.path.dirname(BASE_DIR)
LOGO_PATH = os.path.join(GHN_DASHBOARD_DIR, "ghn_logo.png")
INDEX_PATH = os.path.join(GHN_DASHBOARD_DIR, "index.html")

im = Image.open(LOGO_PATH)
buf = io.BytesIO()
im.save(buf, format="JPEG", quality=85, optimize=True)
b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
data_uri = f"data:image/jpeg;base64,{b64}"

with open(INDEX_PATH, "r", encoding="utf-8") as f:
    content = f.read()

# Replace img src in index.html
old_img = '<img src="/static/ghn_logo.png" alt="GHN - Your Loads. Our Roads." class="login-ghn-logo-img" onerror="if(this.src.indexOf(\'/ghn_logo.png\')===-1)this.src=\'/ghn_logo.png\';">'

if old_img not in content:
    # try regex replacement
    pattern = r'<img src="[^"]*" alt="GHN - Your Loads\. Our Roads\." class="login-ghn-logo-img"[^>]*>'
    new_tag = f'<img src="{data_uri}" alt="GHN - Your Loads. Our Roads." class="login-ghn-logo-img" onerror="this.src=\'/ghn_logo.png\';">'
    content = re.sub(pattern, new_tag, content)
else:
    new_tag = f'<img src="{data_uri}" alt="GHN - Your Loads. Our Roads." class="login-ghn-logo-img" onerror="this.src=\'/ghn_logo.png\';">'
    content = content.replace(old_img, new_tag)

with open(INDEX_PATH, "w", encoding="utf-8") as f:
    f.write(content)

print("Successfully embedded logo Data URI into index.html!")
