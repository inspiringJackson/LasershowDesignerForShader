from PIL import Image
import os

png_path = "src/resources/logo.png"
ico_path = "src/resources/logo.ico"

if os.path.exists(png_path):
    img = Image.open(png_path)
    img.save(ico_path, format="ICO")
    print(f"Created {ico_path}")
else:
    print(f"File not found: {png_path}")
