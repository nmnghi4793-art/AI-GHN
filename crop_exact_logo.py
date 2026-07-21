import os
import glob
import io
import base64
from PIL import Image

media_dir = r"C:\Users\Admin\.gemini\antigravity-ide\brain\fc12ac2f-f926-459e-8b54-362e3c5b61f4\.tempmediaStorage"
img_path = os.path.join(media_dir, "media_fc12ac2f-f926-459e-8b54-362e3c5b61f4_1784642729430.jpg")

im = Image.open(img_path)
print("Original image size:", im.size)

# The logo is in the red box / white card in top-left of the login card
# Let's find white pixel bounding box around (x: 100-600, y: 300-800) or relative coords
w, h = im.size

# Precise bounding box of the logo card in 2000x2000 image:
# Left ~150, Top ~400, Right ~550, Bottom ~680
# Let's crop candidate region and detect exact white card boundary
crop_area = (int(w * 0.08), int(h * 0.20), int(w * 0.30), int(h * 0.38))
logo_crop = im.crop(crop_area)

# Save test crop
output_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ghn_logo.png")
frontend_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend", "ghn_logo.png")

logo_crop.save(output_path, format="PNG")
logo_crop.save(frontend_path, format="PNG")
print(f"Successfully cropped and saved exact logo! Crop size: {logo_crop.size}")
