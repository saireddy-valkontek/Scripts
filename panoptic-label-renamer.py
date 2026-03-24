import os

# ==== CONFIG ====
DATASET_DIR = r"C:\Users\valkontek005\Downloads\Output_Files_From_Apex\Sample_RGB_50-Images.v1i.kitti-segmentation\train\flagged"  # Folder containing the .txt files
BACKUP = True  # Set to False if you don't want backups

# Label mapping
REPLACEMENTS = {
    "Vegetation": "Vehicle",
    "Car": "Person"
}

def process_file(txt_path):
    with open(txt_path, "r") as f:
        lines = f.readlines()

    new_lines = []
    changed = False

    for line in lines:
        parts = line.strip().split()
        if not parts:
            continue

        label = parts[0]
        if label in REPLACEMENTS:
            new_label = REPLACEMENTS[label]
            parts[0] = new_label
            changed = True

        new_lines.append(" ".join(parts) + "\n")

    # Only overwrite if something actually changed
    if changed:
        if BACKUP:
            os.rename(txt_path, txt_path + ".bak")
        with open(txt_path, "w") as f:
            f.writelines(new_lines)
        print(f"✅ Updated labels in {os.path.basename(txt_path)}")
    else:
        print(f"→ No changes in {os.path.basename(txt_path)}")


def main():
    txt_files = [f for f in os.listdir(DATASET_DIR) if f.endswith(".txt")]
    print(f"Found {len(txt_files)} annotation files.\n")

    for txt_file in txt_files:
        process_file(os.path.join(DATASET_DIR, txt_file))

    print("\n🎉 Done! Label renaming complete.")


if __name__ == "__main__":
    main()
