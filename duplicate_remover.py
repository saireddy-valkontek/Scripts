from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk, ImageOps
import imagehash
import os

SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
HASH_THRESHOLD = 8
PREVIEW_SIZE = (450, 450)


class DuplicateImageReviewer:
    def __init__(self, root):
        self.root = root
        self.root.title("Duplicate Image Reviewer")
        self.root.geometry("1200x800")

        self.duplicate_pairs = []
        self.current_index = 0
        self.deleted_files = set()

        self.setup_ui()
        self.bind_keys()

    def setup_ui(self):
        top_frame = tk.Frame(self.root)
        top_frame.pack(pady=10)

        self.folder_label = tk.Label(
            top_frame,
            text="No folder selected",
            width=70,
            anchor="w",
        )
        self.folder_label.pack(side=tk.LEFT, padx=10)

        select_btn = tk.Button(
            top_frame,
            text="Select Folder",
            command=self.select_folder,
            width=15,
            height=2,
        )
        select_btn.pack(side=tk.LEFT)

        self.info_label = tk.Label(
            self.root,
            text="",
            font=("Arial", 12, "bold"),
        )
        self.info_label.pack(pady=5)

        image_frame = tk.Frame(self.root)
        image_frame.pack(expand=True, fill=tk.BOTH)

        self.left_panel = tk.Label(image_frame)
        self.left_panel.pack(side=tk.LEFT, padx=20, pady=20)
        # Middle text area between images
        middle_frame = tk.Frame(image_frame)
        middle_frame.pack(side=tk.LEFT, padx=20)

        self.right_panel = tk.Label(image_frame)
        self.right_panel.pack(side=tk.RIGHT, padx=20, pady=20)

    

        scrollbar = tk.Scrollbar(middle_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.path_text = tk.Text(
            middle_frame,
            width=40,
            height=20,
            wrap=tk.WORD,
            yscrollcommand=scrollbar.set,
            font=("Consolas", 10),
        )

        self.path_text.pack(side=tk.LEFT)

        scrollbar.config(command=self.path_text.yview)

        button_frame = tk.Frame(self.root)
        button_frame.pack(pady=10)

        tk.Button(
            button_frame,
            text="Delete Left (E)",
            command=lambda: self.delete_image("left"),
            bg="#cc4444",
            fg="white",
            width=18,
            height=2,
        ).grid(row=0, column=0, padx=10)

        tk.Button(
            button_frame,
            text="Keep Both / Next (SPACE)",
            command=self.next_pair,
            bg="#448844",
            fg="white",
            width=22,
            height=2,
        ).grid(row=0, column=1, padx=10)

        tk.Button(
            button_frame,
            text="Delete Right (R)",
            command=lambda: self.delete_image("right"),
            bg="#cc4444",
            fg="white",
            width=18,
            height=2,
        ).grid(row=0, column=2, padx=10)
        tk.Button(
            button_frame,
            text="Delete Both (B)",
            command=lambda: self.delete_both("left", "right"),
            bg="#B018B5",
            fg="white",
            width=18,
            height=2,
        ).grid(row=0, column=3, padx=10)
        tk.Button(
        button_frame,
            text="Auto Delete Low Res",
            command=self.auto_delete_low_res,
            bg="#ff8800",
            fg="white",
            width=20,
            height=2,
        ).grid(row=0, column=4, padx=10)
    def bind_keys(self):
        self.root.bind("e", lambda e: self.delete_image("left"))
        self.root.bind("r", lambda e: self.delete_image("right"))
        self.root.bind("b", lambda e: self.delete_both("left", "right"))
        self.root.bind("a", lambda e: self.auto_delete_low_res())
        self.root.bind("<space>", lambda e: self.next_pair())

    def select_folder(self):
        folder = filedialog.askdirectory()

        if not folder:
            return

        self.folder_path = Path(folder)

        self.folder_label.config(text=str(self.folder_path))

        self.find_duplicates()

    def get_image_files(self, folder):
        image_files = []

        for file in folder.rglob("*"):
            if file.suffix.lower() in SUPPORTED_EXTENSIONS:
                if file.is_file():
                    image_files.append(file)

        return image_files

    def compute_hashes(self, image_files):
        hashes = {}

        total = len(image_files)

        for idx, file in enumerate(image_files):
            try:
                with Image.open(file) as img:
                    img = ImageOps.exif_transpose(img)
                    img_hash = imagehash.phash(img)

                hashes[file] = img_hash

                self.info_label.config(
                    text=f"Processing {idx + 1}/{total}: {file.name}"
                )
                self.root.update_idletasks()

            except Exception as e:
                print(f"Failed: {file} -> {e}")

        return hashes
    def auto_delete_low_res(self):

        deleted_count = 0

        for left_img, right_img, _ in self.duplicate_pairs:

            # Skip already deleted files
            if (
                left_img in self.deleted_files
                or right_img in self.deleted_files
                or not left_img.exists()
                or not right_img.exists()
            ):
                continue

            try:
                with Image.open(left_img) as img1:
                    left_pixels = img1.width * img1.height

                with Image.open(right_img) as img2:
                    right_pixels = img2.width * img2.height

                # Decide smaller image
                if left_pixels < right_pixels:
                    target = left_img

                elif right_pixels < left_pixels:
                    target = right_img

                else:
                    continue    # same resolution → keep both

                os.remove(target)

                self.deleted_files.add(target)
                deleted_count += 1

                print(f"Deleted: {target}")

            except Exception as e:
                print(f"Error deleting : {e}")

        messagebox.showinfo(
            "Completed",
            f"Deleted {deleted_count} lower-resolution images"
        )

        self.show_pair()
    def find_duplicates(self):
        self.info_label.config(text="Scanning images...")
        self.root.update()

        image_files = self.get_image_files(self.folder_path)

        if not image_files:
            messagebox.showinfo("Info", "No images found")
            return

        hashes = self.compute_hashes(image_files)

        files = list(hashes.keys())

        duplicates = []
        seen = set()

        total = len(files)

        for i in range(total):
            for j in range(i + 1, total):

                file1 = files[i]
                file2 = files[j]

                pair_key = tuple(sorted((str(file1), str(file2))))

                if pair_key in seen:
                    continue

                seen.add(pair_key)

                diff = hashes[file1] - hashes[file2]

                if diff <= HASH_THRESHOLD:
                    duplicates.append((file1, file2, diff))

        duplicates.sort(key=lambda x: x[2])

        self.duplicate_pairs = duplicates
        self.current_index = 0

        if not duplicates:
            self.info_label.config(text="No similar images found")
            messagebox.showinfo("Done", "No duplicates found")
            return

        self.show_pair()

    def load_preview(self, image_path):
        try:
            with Image.open(image_path) as img:
                img = ImageOps.exif_transpose(img)
                img.thumbnail(PREVIEW_SIZE)

                preview = ImageTk.PhotoImage(img.copy())

            return preview

        except Exception as e:
            print(f"Preview failed: {image_path} -> {e}")
            return None

    def get_image_info(self, path):
        try:
            with Image.open(path) as img:
                resolution = f"{img.width} x {img.height}"

            size_mb = os.path.getsize(path) / (1024 * 1024)

            return resolution, f"{size_mb:.2f} MB"

        except Exception:
            return "Unknown", "Unknown"

    def show_pair(self):

        while self.current_index < len(self.duplicate_pairs):

            left_img, right_img, similarity = self.duplicate_pairs[
                self.current_index
            ]

            if (
                left_img in self.deleted_files
                or right_img in self.deleted_files
                or not left_img.exists()
                or not right_img.exists()
            ):
                self.current_index += 1
                continue

            left_preview = self.load_preview(left_img)
            right_preview = self.load_preview(right_img)

            if left_preview is None or right_preview is None:
                self.current_index += 1
                continue

            self.left_panel.config(image=left_preview)
            self.left_panel.image = left_preview

            self.right_panel.config(image=right_preview)
            self.right_panel.image = right_preview

            self.info_label.config(
                text=(
                    f"Pair {self.current_index + 1}"
                    f"/{len(self.duplicate_pairs)}"
                    f" | Hash Difference: {similarity}"
                )
            )

            left_res, left_size = self.get_image_info(left_img)
            right_res, right_size = self.get_image_info(right_img)

            info_text = (
                f"LEFT IMAGE\n"
                f"{'-'*50}\n"
                f"Name       : {left_img.name}\n"
                f"Resolution : {left_res}\n"
                f"Size       : {left_size}\n"
                f"Path       : {left_img}\n\n"
                f"RIGHT IMAGE\n"
                f"{'-'*50}\n"
                f"Name       : {right_img.name}\n"
                f"Resolution : {right_res}\n"
                f"Size       : {right_size}\n"
                f"Path       : {right_img}"
            )

            self.path_text.delete("1.0", tk.END)
            self.path_text.insert(tk.END, info_text)

            return

        self.finish_review()

    def delete_image(self, side):

        if self.current_index >= len(self.duplicate_pairs):
            return

        left_img, right_img, _ = self.duplicate_pairs[self.current_index]

        target = left_img if side == "left" else right_img

        if not target.exists():
            self.deleted_files.add(target)
            self.next_pair()
            return

        try:
            os.remove(target)

            self.deleted_files.add(target)

            print(f"Deleted: {target}")

        except Exception as e:
            messagebox.showerror(
                "Delete Error",
                f"Could not delete:\n\n{target}\n\n{e}",
            )
            return

        self.next_pair()
  
    def delete_both(self, side1, side2):

        if self.current_index >= len(self.duplicate_pairs):
            return

        left_img, right_img, _ = self.duplicate_pairs[self.current_index]
        target1=left_img
        target2=right_img
        

        if not target1.exists():
            self.deleted_files.add(target1)
            self.next_pair()
            return

        if not target2.exists():
            self.deleted_files.add(target2)
            self.next_pair()
            return

        try:
            os.remove(target1)
            os.remove(target2)

            self.deleted_files.add(target1)
            self.deleted_files.add(target2)

            print(f"Deleted: {target1} and {target2}")

        except Exception as e:
            messagebox.showerror(
                "Delete Error",
                f"Could not delete:\n\n{target1} and {target2}\n\n{e}",
            )
            return

        self.next_pair()

    def next_pair(self):
        self.current_index += 1
        self.show_pair()

    def finish_review(self):
        self.left_panel.config(image="")
        self.right_panel.config(image="")

        self.path_text.delete("1.0", tk.END)

        self.info_label.config(
            text="Finished reviewing duplicate images"
        )

        messagebox.showinfo(
            "Completed",
            "Finished reviewing all duplicate pairs.",
        )


if __name__ == "__main__":
    root = tk.Tk()
    app = DuplicateImageReviewer(root)
    root.mainloop()