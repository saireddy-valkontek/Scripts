import os
import shutil
from pathlib import Path

from transformers import pipeline
from PIL import Image

# -------------------------------------------------
# SETTINGS
# -------------------------------------------------
INPUT_FOLDER = r"C:\Users\valkontek005\Downloads\UTKface_inthewild-20260518T121813Z-3-001\UTKface_inthewild\part1"

OUTPUT_FOLDER = r"C:\Users\valkontek005\Downloads\b"

GENDER_MODEL = "rizvandwiki/gender-classification-2"

VALID_EXT = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}

# -------------------------------------------------
# CREATE OUTPUT FOLDERS
# -------------------------------------------------
male_dir = os.path.join(OUTPUT_FOLDER, "male")
female_dir = os.path.join(OUTPUT_FOLDER, "female")
unknown_dir = os.path.join(OUTPUT_FOLDER, "unknown")

os.makedirs(male_dir, exist_ok=True)
os.makedirs(female_dir, exist_ok=True)
os.makedirs(unknown_dir, exist_ok=True)

# -------------------------------------------------
# LOAD MODEL
# -------------------------------------------------
print("Loading gender model...")

gender_clf = pipeline(
    "image-classification",
    model=GENDER_MODEL,
    device=-1
)

print("Model loaded.")

# -------------------------------------------------
# GET IMAGES
# -------------------------------------------------
image_files = [
    p for p in Path(INPUT_FOLDER).iterdir()
    if p.suffix.lower() in VALID_EXT
]

print(f"Found {len(image_files)} images")

# -------------------------------------------------
# PROCESS IMAGES
# -------------------------------------------------
for img_path in image_files:

    try:
        image = Image.open(img_path).convert("RGB")

        result = gender_clf(image)[0]

        label = result["label"].lower()
        score = float(result["score"])

        # optional confidence threshold
        if score < 0.70:
            gender = "unknown"

        elif "female" in label:
            gender = "female"

        elif "male" in label:
            gender = "male"

        else:
            gender = "unknown"

        # destination
        if gender == "male":
            dst = male_dir

        elif gender == "female":
            dst = female_dir

        else:
            dst = unknown_dir

        shutil.copy(str(img_path), os.path.join(dst, img_path.name))

        print(f"{img_path.name} -> {gender} ({score:.2f})")

    except Exception as e:
        print(f"Error processing {img_path.name}: {e}")

print("Done.")