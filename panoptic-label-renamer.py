import os
import shutil

# ==== CONFIG ====
DATASET_DIR = r"C:\Users\valkontek005\Downloads\Output_Files_From_Apex\Sample_RGB_50-Images.v1i.kitti-segmentation\train\flagged"  # Folder containing the .txt files

# Fallback to local path if not found
if not os.path.exists(DATASET_DIR):
    DATASET_DIR = os.path.join(".", "train", "flagged")

BACKUP = True  # Set to False if you don't want backups

# Label mapping
REPLACEMENTS = {
    "Vegetation": "Vehicle",
    "Car": "Person"
}

def process_file(txt_path):
    try:
        with open(txt_path, "r") as f:
            lines = f.readlines()
    except Exception as e:
        print(f"❌ Failed to read {txt_path}: {e}")
        return

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
        backup_path = txt_path + ".bak"
        if BACKUP:
            try:
                shutil.copy2(txt_path, backup_path)
            except Exception as e:
                print(f"❌ Backup failed for {txt_path}: {e}. Skipping update to prevent data loss.")
                return

        try:
            with open(txt_path, "w") as f:
                f.writelines(new_lines)
            print(f"✅ Updated labels in {os.path.basename(txt_path)}")
        except Exception as e:
            print(f"❌ Failed to write updated labels to {txt_path}: {e}")
            if BACKUP and os.path.exists(backup_path):
                try:
                    shutil.move(backup_path, txt_path)
                    print(f"Restored original file from backup.")
                except Exception as restore_err:
                    print(f"❌ Critical error: Failed to restore backup: {restore_err}")
    else:
        print(f"→ No changes in {os.path.basename(txt_path)}")


def main():
    if not os.path.exists(DATASET_DIR):
        print(f"❌ Dataset directory not found: {DATASET_DIR}")
        return

    txt_files = [f for f in os.listdir(DATASET_DIR) if f.endswith(".txt")]
    print(f"Found {len(txt_files)} annotation files.\n")

    for txt_file in txt_files:
        process_file(os.path.join(DATASET_DIR, txt_file))

    print("\n🎉 Done! Label renaming complete.")


if __name__ == "__main__":
    main()
