import os
import shutil

# Set paths
image_folder = r"C:\Users\valkontek005\Downloads\Output_Files_From_Apex - Copy\Sample_HD_THERMAL-50-Images.v1i.kitti-segmentation\train"
label_folder = r"C:\Users\valkontek005\Downloads\Output_Files_From_Apex - Copy\Sample_HD_THERMAL-50-Images.v1i.kitti-segmentation\train"

image_extensions = ('.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff')

# Get all image files
image_files = [f for f in os.listdir(image_folder) if f.lower().endswith(image_extensions)]

# Step 1: Rename to temporary names to avoid collisions
for idx, file in enumerate(image_files):
    name, ext = os.path.splitext(file)
    temp_image_name = f"temp_{idx}{ext}"
    temp_label_name = f"temp_{idx}.txt"

    # Rename image
    os.rename(os.path.join(image_folder, file), os.path.join(image_folder, temp_image_name))

    # Rename label if it exists
    label_path = os.path.join(label_folder, f"{name}.txt")
    if os.path.exists(label_path):
        os.rename(label_path, os.path.join(label_folder, temp_label_name))

# Step 2: Rename temp files to final names
temp_image_files = sorted([f for f in os.listdir(image_folder) if f.startswith("temp_")])
for idx, file in enumerate(temp_image_files, start=0):
    name, ext = os.path.splitext(file)
    final_image_name = f"{idx}{ext}"
    final_label_name = f"{idx}.txt"

    # Rename image
    os.rename(os.path.join(image_folder, file), os.path.join(image_folder, final_image_name))

    # Rename label if it exists
    temp_label_path = os.path.join(label_folder, f"{name}.txt")
    if os.path.exists(temp_label_path):
        os.rename(temp_label_path, os.path.join(label_folder, final_label_name))

    print(f"Renamed {file} and label to {final_image_name} / {final_label_name}")

print("Renaming complete for all images and labels!")