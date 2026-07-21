import os
import re
import io
import base64
from PIL import Image

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INDEX_PATH = os.path.join(BASE_DIR, "index.html")
LOGO_ROOT = os.path.join(BASE_DIR, "ghn_logo.png")
LOGO_FRONTEND = os.path.join(BASE_DIR, "frontend", "ghn_logo.png")

USER_IMG_PATH = r"C:\Users\Admin\.gemini\antigravity-ide\brain\fc12ac2f-f926-459e-8b54-362e3c5b61f4\media__1784653844221.png"

im = Image.open(USER_IMG_PATH)
crop_box = (51, 48, 278, 158)
logo_crop = im.crop(crop_box)

# Save PNG
logo_crop.save(LOGO_ROOT, format="PNG")
logo_crop.save(LOGO_FRONTEND, format="PNG")

# Base64 encoding
buf = io.BytesIO()
logo_crop.save(buf, format="PNG")
b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
data_uri = f"data:image/png;base64,{b64}"

# Update index.html
with open(INDEX_PATH, "r", encoding="utf-8") as f:
    content = f.read()

pattern = r'<img src="[^"]*" alt="GHN - Your Loads\. Our Roads\." class="login-ghn-logo-img"[^>]*>'
new_tag = f'<img src="{data_uri}" alt="GHN - Your Loads. Our Roads." class="login-ghn-logo-img" onerror="this.src=\'/ghn_logo.png\';">'

content = re.sub(pattern, new_tag, content)

with open(INDEX_PATH, "w", encoding="utf-8") as f:
    f.write(content)

print(f"Successfully extracted exact dark logo badge from user screenshot ({logo_crop.size}) and updated index.html!")
