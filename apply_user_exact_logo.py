import os
import re
import io
import base64
from PIL import Image

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INDEX_PATH = os.path.join(BASE_DIR, "index.html")
LOGO_ROOT = os.path.join(BASE_DIR, "ghn_logo.png")
LOGO_FRONTEND = os.path.join(BASE_DIR, "frontend", "ghn_logo.png")

USER_IMG_PATH = r"C:\Users\Admin\.gemini\antigravity-ide\brain\fc12ac2f-f926-459e-8b54-362e3c5b61f4\media__1784653409707.png"

im = Image.open(USER_IMG_PATH)
# Exact logo bounds inside user's screenshot: left=56, top=76, right=254, bottom=251
crop_box = (56, 76, 254, 251)
logo_crop = im.crop(crop_box)

# Save exact PNG
logo_crop.save(LOGO_ROOT, format="PNG")
logo_crop.save(LOGO_FRONTEND, format="PNG")

# Convert to Base64
buf = io.BytesIO()
logo_crop.save(buf, format="PNG")
b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
data_uri = f"data:image/png;base64,{b64}"

# Embed into index.html
with open(INDEX_PATH, "r", encoding="utf-8") as f:
    content = f.read()

pattern = r'<img src="[^"]*" alt="GHN - Your Loads\. Our Roads\." class="login-ghn-logo-img"[^>]*>'
new_tag = f'<img src="{data_uri}" alt="GHN - Your Loads. Our Roads." class="login-ghn-logo-img" onerror="this.src=\'/ghn_logo.png\';">'

content = re.sub(pattern, new_tag, content)

with open(INDEX_PATH, "w", encoding="utf-8") as f:
    f.write(content)

print(f"Successfully extracted exact logo from user's screenshot ({logo_crop.size}) and embedded into index.html!")
