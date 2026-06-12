import os
import shutil
import cv2
import matplotlib.pyplot as plt
from matplotlib.widgets import Button
from tqdm import tqdm

# ==== CONFIG ====
DATASET_DIR = r"C:\Users\valkontek005\Downloads\Output_Files_From_Apex-20251030T111035Z-1-001\Output_Files_From_Apex\Sample_RGB_50-Images.v1i.kitti-segmentation\train"

# Fallback to local path if not found
if not os.path.exists(DATASET_DIR):
    DATASET_DIR = os.path.join(".", "train")

FLAGGED_DIR = os.path.join(DATASET_DIR, "flagged")
IMG_EXTENSIONS = [".jpg", ".jpeg", ".png"]

# Create flagged folder if it doesn't exist
os.makedirs(FLAGGED_DIR, exist_ok=True)

# ==== HELPERS ====
def parse_annotation(txt_path):
    boxes = []
    with open(txt_path, "r") as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) >= 8:
                cls = parts[0]
                x1, y1, x2, y2 = map(float, parts[4:8])
                boxes.append((cls, x1, y1, x2, y2))
    return boxes


def load_dataset():
    all_files = sorted(os.listdir(DATASET_DIR))
    img_files = [f for f in all_files if os.path.splitext(f)[1].lower() in IMG_EXTENSIONS]
    # Remove images already flagged
    img_files = [f for f in img_files if not os.path.exists(os.path.join(FLAGGED_DIR, f))]
    return img_files


class DatasetReviewer:
    def __init__(self, dataset_dir):
        self.dataset_dir = dataset_dir
        self.images = load_dataset()
        self.index = 0
        self.total = len(self.images)
        self.fig, self.ax = plt.subplots(figsize=(12, 8))
        plt.subplots_adjust(bottom=0.2)
        self.current_image = None
        self.boxes = None
        self.img_artist = None
        self.rects = []
        self.texts = []

        # Add buttons
        axprev = plt.axes([0.1, 0.05, 0.1, 0.075])
        axnext = plt.axes([0.21, 0.05, 0.1, 0.075])
        axflag = plt.axes([0.82, 0.05, 0.1, 0.075])
        self.bnext = Button(axnext, "Next ▶")
        self.bprev = Button(axprev, "◀ Prev")
        self.bflag = Button(axflag, "🚩 Flag")

        self.bnext.on_clicked(self.next_image)
        self.bprev.on_clicked(self.prev_image)
        self.bflag.on_clicked(self.flag_image)

        # Connect keyboard events
        self.fig.canvas.mpl_connect("key_press_event", self.on_key)

        self.show_image()

    def show_image(self):
        self.ax.clear()

        if not self.images:
            self.ax.text(0.5, 0.5, "No images to review!",
                         ha="center", va="center", fontsize=16, color="red")
            plt.draw()
            return

        img_name = self.images[self.index]
        img_path = os.path.join(self.dataset_dir, img_name)
        txt_path = os.path.splitext(img_path)[0] + ".txt"

        img = cv2.imread(img_path)
        if img is None:
            print(f"⚠️ Could not load {img_path}")
            self.ax.text(0.5, 0.5, f"Could not load image:\n{img_name}",
                         ha="center", va="center", fontsize=16, color="red")
            plt.draw()
            return
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

        boxes = parse_annotation(txt_path) if os.path.exists(txt_path) else []
        self.ax.imshow(img)
        for cls, x1, y1, x2, y2 in boxes:
            rect = plt.Rectangle((x1, y1), x2 - x1, y2 - y1,
                                 fill=False, edgecolor='lime', linewidth=2)
            self.ax.add_patch(rect)
            self.ax.text(x1, y1 - 5, cls, color='yellow', fontsize=10, weight='bold')

        progress = (self.index + 1) / self.total * 100
        self.ax.set_title(f"{img_name} — {self.index+1}/{self.total} ({progress:.1f}%)",
                          fontsize=14)
        plt.axis("off")
        plt.draw()

    def next_image(self, event=None):
        if self.index < self.total - 1:
            self.index += 1
            self.show_image()

    def prev_image(self, event=None):
        if self.index > 0:
            self.index -= 1
            self.show_image()

    def flag_image(self, event=None):
        img_name = self.images[self.index]
        txt_name = os.path.splitext(img_name)[0] + ".txt"
        img_path = os.path.join(self.dataset_dir, img_name)
        txt_path = os.path.join(self.dataset_dir, txt_name)

        shutil.move(img_path, os.path.join(FLAGGED_DIR, img_name))
        if os.path.exists(txt_path):
            shutil.move(txt_path, os.path.join(FLAGGED_DIR, txt_name))

        print(f"🚩 Flagged {img_name}")
        # Remove from list and refresh
        del self.images[self.index]
        self.total = len(self.images)
        if self.index >= self.total:
            self.index = max(0, self.total - 1)
        self.show_image()

    def on_key(self, event):
        if event.key in ("right", "d"):
            self.next_image()
        elif event.key in ("left", "a"):
            self.prev_image()
        elif event.key == "f":
            self.flag_image()


def main():
    reviewer = DatasetReviewer(DATASET_DIR)
    plt.show()


if __name__ == "__main__":
    main()
