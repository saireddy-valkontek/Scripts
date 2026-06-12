import os
import uuid

# ==== CONFIG ====
FOLDER_PATH = r"C:\Users\valkontek005\Downloads\images"  # Folder with images and text files

IMG_EXTENSIONS = [".jpg", ".jpeg", ".png"]
TXT_EXT = ".txt"

# ==== MAIN LOGIC ====
def rename_files(prefix):
    if not os.path.exists(FOLDER_PATH):
        print(f"❌ Folder not found: {FOLDER_PATH}")
        return

    files = os.listdir(FOLDER_PATH)

    # Collect image files
    image_files = [f for f in files if os.path.splitext(f)[1].lower() in IMG_EXTENSIONS]
    image_files.sort()

    # Generate a unique temp run prefix
    temp_run_id = f"__temp_rename_{uuid.uuid4().hex[:8]}_"

    temp_renamed = []

    # Pass 1: Rename all images and corresponding text files to temp names
    for idx, img_file in enumerate(image_files):
        base_name, ext = os.path.splitext(img_file)
        txt_file = base_name + TXT_EXT

        img_path = os.path.join(FOLDER_PATH, img_file)
        txt_path = os.path.join(FOLDER_PATH, txt_file)

        temp_img_name = f"{temp_run_id}{idx}{ext}"
        temp_txt_name = f"{temp_run_id}{idx}{TXT_EXT}"

        temp_img_path = os.path.join(FOLDER_PATH, temp_img_name)
        temp_txt_path = os.path.join(FOLDER_PATH, temp_txt_name)

        # Rename image
        os.rename(img_path, temp_img_path)

        # Rename text file if it exists
        has_txt = os.path.exists(txt_path)
        if has_txt:
            os.rename(txt_path, temp_txt_path)

        temp_renamed.append((temp_img_path, temp_txt_path if has_txt else None, ext))

    # Pass 2: Rename temp files to final names
    renamed = 0
    for idx, (temp_img_path, temp_txt_path, ext) in enumerate(temp_renamed, start=1):
        new_base = f"{prefix}_{idx}"
        new_img_path = os.path.join(FOLDER_PATH, new_base + ext)

        os.rename(temp_img_path, new_img_path)

        if temp_txt_path:
            new_txt_path = os.path.join(FOLDER_PATH, new_base + TXT_EXT)
            os.rename(temp_txt_path, new_txt_path)

        renamed += 1
        print(f"✅ {os.path.basename(image_files[idx-1])} → {os.path.basename(new_img_path)}")

    print(f"\n🎉 Done! Renamed {renamed} image–text pairs using prefix '{prefix}'.")


def main():
    prefix = input("Enter prefix to use (e.g., 'o'): ").strip()
    if not prefix:
        print("❌ No prefix entered. Exiting.")
        return

    rename_files(prefix)


if __name__ == "__main__":
    main()
