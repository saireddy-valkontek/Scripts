import os
import shutil
import random
from pathlib import Path

# ======================
# CONFIG
# ======================
SOURCE_DIR = r"C:\Users\valkontek005\Downloads\car brand and model detection"
OUTPUT_DIR = r"C:\Users\valkontek005\Downloads\dataset"

SPLIT = (0.7, 0.15, 0.15)   # train, val, test
IMAGE_EXTS = [".jpg", ".jpeg", ".png", ".webp"]

random.seed(42)

# ======================
# BRAND NAME FIXES
# ======================
BRAND_MAP = {
    "maruthi": "Maruti",
    "Hyundai": "Hyundai",
    "Tata": "Tata"
}

MODEL_FIX = {
    "venue": "Venue",
    "Taigo": "Tiago",
    "Grand i10 Nios": "Grand_i10_Nios"
}


def get_images(folder):
    files = []
    for f in os.listdir(folder):
        ext = os.path.splitext(f)[1].lower()
        if ext in IMAGE_EXTS:
            files.append(os.path.join(folder, f))
    return files


def split_files(files):
    random.shuffle(files)
    n = len(files)

    train_end = int(n * SPLIT[0])
    val_end = train_end + int(n * SPLIT[1])

    return {
        "train": files[:train_end],
        "val": files[train_end:val_end],
        "test": files[val_end:]
    }


def copy_files(files, target_folder):
    os.makedirs(target_folder, exist_ok=True)

    for file in files:
        fname = os.path.basename(file)
        shutil.copy2(file, os.path.join(target_folder, fname))


def clean_name(name):
    return MODEL_FIX.get(name, name.replace(" ", "_"))


def process():
    src = Path(SOURCE_DIR)
    out = Path(OUTPUT_DIR)

    if out.exists():
        shutil.rmtree(out)

    print("Creating dataset...")

    for brand_folder in src.iterdir():

        if not brand_folder.is_dir():
            continue

        raw_brand = brand_folder.name
        brand = BRAND_MAP.get(raw_brand, raw_brand)

        # -------------------------
        # BRAND DATASET
        # -------------------------
        all_brand_images = []

        for model_folder in brand_folder.iterdir():
            if model_folder.is_dir():
                imgs = get_images(model_folder)
                all_brand_images.extend(imgs)

        brand_split = split_files(all_brand_images)

        for split_name, files in brand_split.items():
            target = out / "brand" / split_name / brand
            copy_files(files, target)

        # -------------------------
        # MODEL DATASET
        # -------------------------
        model_dataset_name = brand.lower() + "_models"

        for model_folder in brand_folder.iterdir():

            if not model_folder.is_dir():
                continue

            model = clean_name(model_folder.name)
            imgs = get_images(model_folder)

            model_split = split_files(imgs)

            for split_name, files in model_split.items():
                target = out / model_dataset_name / split_name / model
                copy_files(files, target)

    print("Done!")
    print("Saved to:", OUTPUT_DIR)


if __name__ == "__main__":
    process()
