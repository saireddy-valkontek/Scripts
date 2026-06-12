import os
import shutil
import uuid

# Set paths (fallback to relative directories if missing)
image_folder = r"C:\Users\valkontek005\Data\windshield\valid\images"
label_folder = r"C:\Users\valkontek005\Data\windshield\valid\labels"

if not os.path.exists(image_folder):
    image_folder = os.path.join(".", "valid", "images")
if not os.path.exists(label_folder):
    label_folder = os.path.join(".", "valid", "labels")

image_extensions = ('.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff')

# Ask for starting number
while True:
    try:
        start_number = int(input("Enter the starting number for renaming: "))
        break
    except ValueError:
        print("Invalid input. Please enter a whole number.")

# Check folder exists
if not os.path.exists(image_folder):
    print(f"❌ Image folder not found: {image_folder}")
    exit(1)

# Get all image files
image_files = [f for f in os.listdir(image_folder) if f.lower().endswith(image_extensions)]

# Unique temp prefix for this run
temp_run_id = f"__temp_{uuid.uuid4().hex[:8]}_"

# Step 1: Rename to temporary names to avoid collisions
for idx, file in enumerate(image_files):
    name, ext = os.path.splitext(file)
    temp_image_name = f"{temp_run_id}{idx}{ext}"
    temp_label_name = f"{temp_run_id}{idx}.txt"

    # Rename image
    os.rename(os.path.join(image_folder, file), os.path.join(image_folder, temp_image_name))

    # Rename label if it exists
    label_path = os.path.join(label_folder, f"{name}.txt")
    if os.path.exists(label_path):
        os.rename(label_path, os.path.join(label_folder, temp_label_name))

# Step 2: Rename temp files to final names
temp_image_files = sorted([f for f in os.listdir(image_folder) if f.startswith(temp_run_id)],
                           key=lambda x: int(os.path.splitext(x)[0].split("_")[-1]))
for idx, file in enumerate(temp_image_files, start=start_number):
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