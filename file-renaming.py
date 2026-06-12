import os
import uuid

# Path to your folder
folder_path = r"C:\Users\valkontek005\Data\Gender-Classifiation\person-faces\Unknown"

start_number = 1

if not os.path.exists(folder_path):
    print(f"❌ Folder not found: {folder_path}")
    exit(1)

files = [f for f in os.listdir(folder_path) if os.path.isfile(os.path.join(folder_path, f))]
files.sort() 

# Unique prefix for this run
temp_run_id = f"__temp_{uuid.uuid4().hex[:8]}_"

# Step 1: Rename all files to temporary names
temp_names = []
for i, filename in enumerate(files):
    _, ext = os.path.splitext(filename)
    temp_name = f"{temp_run_id}{i}{ext}"
    src = os.path.join(folder_path, filename)
    dst = os.path.join(folder_path, temp_name)
    os.rename(src, dst)
    temp_names.append((temp_name, ext))

# Step 2: Rename all temporary files to final names starting from `start_number`
for i, (temp_name, ext) in enumerate(temp_names, start=start_number):
    src = os.path.join(folder_path, temp_name)
    dst = os.path.join(folder_path, f"{i}{ext}")
    os.rename(src, dst)
    print(f"Renamed: {temp_name} → {i}{ext}")