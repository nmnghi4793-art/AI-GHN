import os
import io
import re
import base64
from PIL import Image, ImageDraw, ImageFont

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INDEX_PATH = os.path.join(BASE_DIR, "index.html")
LOGO_ROOT = os.path.join(BASE_DIR, "ghn_logo.png")
LOGO_FRONTEND = os.path.join(BASE_DIR, "frontend", "ghn_logo.png")

# High-resolution official GHN logo canvas (520 x 200)
w, h = 520, 200
im = Image.new("RGBA", (w, h), (255, 255, 255, 255))
draw = ImageDraw.Draw(im)

# Load fonts
try:
    font_ghn = ImageFont.truetype("arialbd.ttf", 96)
    font_tag = ImageFont.truetype("arialbd.ttf", 20)
except Exception:
    font_ghn = ImageFont.load_default()
    font_tag = ImageFont.load_default()

# 1. Draw "GHN" in bold dark navy/black (#0f172a)
draw.text((25, 10), "GHN", fill=(15, 23, 42), font=font_ghn)

# 2. Draw red banner (#e11d48) with "YOUR LOADS. OUR ROADS."
draw.rectangle([25, 135, 490, 180], fill=(225, 29, 72))
draw.text((42, 145), "YOUR LOADS. OUR ROADS.", fill=(255, 255, 255), font=font_tag)

# Save logo images
im.save(LOGO_ROOT, format="PNG")
im.save(LOGO_FRONTEND, format="PNG")

# Convert to Base64 Data URI
buf = io.BytesIO()
im.save(buf, format="PNG")
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

print(f"Official GHN Logo ('GHN - YOUR LOADS. OUR ROADS.') created and embedded successfully!")
