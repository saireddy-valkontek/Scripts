import os
import random
import shutil
from pathlib import Path
from sklearn.model_selection import train_test_split

# =========================
# CONFIG
# =========================

SOURCE_DIR = r"C:\Users\valkontek005\Data\Gender-Classifiation\person-faces"

# Structure inside SOURCE_DIR:
# dataset_raw/
# ├── male/
# ├── female/
# └── unknown/

OUTPUT_DIR = r"C:\Users\valkontek005\Data\Gender-Classifiation\person-faces-dataset"

TRAIN_RATIO = 0.80
VAL_RATIO = 0.10
TEST_RATIO = 0.10

RANDOM_SEED = 42

IMAGE_EXTENSIONS = [".jpg", ".jpeg", ".png", ".webp", ".bmp"]

# =========================
# SETTINGS
# =========================

random.seed(RANDOM_SEED)

classes = ["Male", "Female", "Unknown"]

# =========================
# CREATE OUTPUT FOLDERS
# =========================

for split in ["train", "val", "test"]:
    for cls in classes:
        os.makedirs(os.path.join(OUTPUT_DIR, split, cls), exist_ok=True)

# =========================
# SPLIT FUNCTION
# =========================

def get_images(folder):
    images = []

    for ext in IMAGE_EXTENSIONS:
        images.extend(Path(folder).glob(f"*{ext}"))
        images.extend(Path(folder).glob(f"*{ext.upper()}"))

    return [str(img) for img in images]

# =========================
# PROCESS EACH CLASS
# =========================

for cls in classes:

    class_dir = os.path.join(SOURCE_DIR, cls)

    images = get_images(class_dir)

    print(f"\nClass: {cls}")
    print(f"Total Images: {len(images)}")

    # -------------------------
    # TRAIN SPLIT
    # -------------------------

    train_images, temp_images = train_test_split(
        images,
        test_size=(1 - TRAIN_RATIO),
        random_state=RANDOM_SEED,
        shuffle=True
    )

    # -------------------------
    # VAL + TEST SPLIT
    # -------------------------

    val_size_relative = VAL_RATIO / (VAL_RATIO + TEST_RATIO)

    val_images, test_images = train_test_split(
        temp_images,
        test_size=(1 - val_size_relative),
        random_state=RANDOM_SEED,
        shuffle=True
    )

    # =========================
    # COPY FILES
    # =========================

    split_map = {
        "train": train_images,
        "val": val_images,
        "test": test_images
    }

    for split_name, split_files in split_map.items():

        for file_path in split_files:

            filename = os.path.basename(file_path)

            dst_path = os.path.join(
                OUTPUT_DIR,
                split_name,
                cls,
                filename
            )

            shutil.copy2(file_path, dst_path)

    # =========================
    # PRINT COUNTS
    # =========================

    print(f"Train: {len(train_images)}")
    print(f"Val:   {len(val_images)}")
    print(f"Test:  {len(test_images)}")

print("\nDataset split completed successfully.")