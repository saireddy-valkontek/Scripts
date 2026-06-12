import os
import shutil
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

from transformers import pipeline
from PIL import Image
from tqdm import tqdm

# -------------------------------------------------
# SETTINGS
# -------------------------------------------------
INPUT_FOLDER = r"C:\Users\valkontek005\Downloads\a"

OUTPUT_FOLDER = r"C:\Users\valkontek005\Downloads\c"

GENDER_MODEL = "rizvandwiki/gender-classification-2"

VALID_EXT = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}

CONF_THRESHOLD = 0.70

NUM_WORKERS = 8

MOVE_FILES = False   # True = move, False = copy

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
# PROCESS SINGLE IMAGE
# -------------------------------------------------
def process_image(img_path):

    try:
        image = Image.open(img_path).convert("RGB")

        result = gender_clf(image)[0]

        label = result["label"].lower()
        score = float(result["score"])

        # -------------------------
        # CLASS DECISION
        # -------------------------
        if score < CONF_THRESHOLD:
            gender = "unknown"

        elif "female" in label:
            gender = "female"

        elif "male" in label:
            gender = "male"

        else:
            gender = "unknown"

        # -------------------------
        # DESTINATION
        # -------------------------
        if gender == "male":
            dst_dir = male_dir

        elif gender == "female":
            dst_dir = female_dir

        else:
            dst_dir = unknown_dir

        dst_path = os.path.join(dst_dir, img_path.name)

        # -------------------------
        # COPY / MOVE
        # -------------------------
        if MOVE_FILES:
            shutil.move(str(img_path), dst_path)
        else:
            shutil.copy2(str(img_path), dst_path)

        return f"{img_path.name} -> {gender} ({score:.2f})"

    except Exception as e:
        return f"ERROR: {img_path.name} -> {e}"


# -------------------------------------------------
# MULTI-THREAD PROCESSING
# -------------------------------------------------
results = []

with ThreadPoolExecutor(max_workers=NUM_WORKERS) as executor:

    futures = [
        executor.submit(process_image, img_path)
        for img_path in image_files
    ]

    for future in tqdm(
        as_completed(futures),
        total=len(futures),
        desc="Processing Images",
        ncols=100
    ):
        results.append(future.result())

# -------------------------------------------------
# SUMMARY
# -------------------------------------------------
print("\nDone.\n")

for r in results[:20]:
    print(r)

if len(results) > 20:
    print(f"\n... and {len(results)-20} more")