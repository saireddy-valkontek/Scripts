import os
from PIL import Image

def resize_images_in_folder(folder_path, size=(640, 640)):
    if not os.path.exists(folder_path):
        print(f"Folder '{folder_path}' does not exist.")
        return

    output_folder = os.path.join(folder_path, "resized")
    os.makedirs(output_folder, exist_ok=True)

    count = 0
    for filename in os.listdir(folder_path):
        filepath = os.path.join(folder_path, filename)
        if os.path.isfile(filepath) and filename.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.gif', '.webp')):
            try:
                with Image.open(filepath) as img:
                    resized_img = img.resize(size)
                    output_path = os.path.join(output_folder, filename)
                    resized_img.save(output_path)
                    count += 1
            except Exception as e:
                print(f"Failed to process {filename}: {e}")

    print(f"✅ Resized {count} images to {size[0]}x{size[1]} and saved to: {output_folder}")

# --- Usage ---
if __name__ == "__main__":
    # Option 1: Hardcoded path
    folder_path = r"C:\Users\saireddy\Desktop\chassis_numbers\chassis_numbers-v1"

    # Fallback to local if not found
    if not os.path.exists(folder_path):
        folder_path = os.path.join(".", "chassis_numbers")

    # Option 2: User input (fallback if local folder doesn't exist either)
    if not os.path.exists(folder_path):
        folder_path = input("Enter folder path: ").strip()

    resize_images_in_folder(folder_path)