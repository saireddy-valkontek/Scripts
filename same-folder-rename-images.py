import os

# ==== CONFIG ====
FOLDER_PATH = r"C:\Users\valkontek005\Downloads\images"  # Folder with images and text files

IMG_EXTENSIONS = [".jpg", ".jpeg", ".png"]
TXT_EXT = ".txt"

# ==== MAIN LOGIC ====
def rename_files(prefix):
    files = os.listdir(FOLDER_PATH)

    # Collect image files
    image_files = [f for f in files if os.path.splitext(f)[1].lower() in IMG_EXTENSIONS]
    image_files.sort()

    renamed = 0
    for idx, img_file in enumerate(image_files, start=1):
        base_name, ext = os.path.splitext(img_file)
        txt_file = base_name + TXT_EXT

        img_path = os.path.join(FOLDER_PATH, img_file)
        txt_path = os.path.join(FOLDER_PATH, txt_file)

        new_base = f"{prefix}_{idx}"
        new_img_path = os.path.join(FOLDER_PATH, new_base + ext)
        new_txt_path = os.path.join(FOLDER_PATH, new_base + TXT_EXT)

        # Rename the image
        os.rename(img_path, new_img_path)

        # Rename the text file if it exists
        if os.path.exists(txt_path):
            os.rename(txt_path, new_txt_path)

        renamed += 1
        print(f"✅ {img_file} → {os.path.basename(new_img_path)}")

    print(f"\n🎉 Done! Renamed {renamed} image–text pairs using prefix '{prefix}'.")


def main():
    prefix = input("Enter prefix to use (e.g., 'o'): ").strip()
    if not prefix:
        print("❌ No prefix entered. Exiting.")
        return

    rename_files(prefix)


if __name__ == "__main__":
    main()
