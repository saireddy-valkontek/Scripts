from PIL import Image
from pathlib import Path

# Folder containing WEBP images
input_folder = Path(r"C:\Users\valkontek005\Data\adobe11-17")

# Fallback to local if not found
if not input_folder.exists():
    input_folder = Path("./adobe11-17")

if not input_folder.exists():
    import sys
    print(f"❌ Input folder not found: {input_folder}")
    sys.exit(1)

# Output folder for JPG images
output_folder = Path("jpg_images")
output_folder.mkdir(exist_ok=True)

# Convert all WEBP files
for webp_file in input_folder.glob("*.webp"):
    
    # Output JPG path
    jpg_file = output_folder / f"{webp_file.stem}.jpg"

    try:
        # Open and convert image
        img = Image.open(webp_file).convert("RGB")

        # Save as JPG
        img.save(jpg_file, "JPEG", quality=95)

        print(f"Converted: {webp_file.name}")

    except Exception as e:
        print(f"Failed: {webp_file.name} -> {e}")

print("Done!")