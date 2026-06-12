import os
import shutil
import zipfile
import time
import yaml
import torch
import cv2
import gdown
from pathlib import Path
from ultralytics import YOLO

# ========== CONFIG ==========
class Config:
    """Configuration settings for the YOLO training pipeline."""
    WORKING_DIR = Path("/kaggle/working") if os.path.exists("/kaggle/working") else Path("./workspace")
    ZIP_PATH = WORKING_DIR / "yolo_dataset.zip"
    EXTRACT_DIR = WORKING_DIR / "yolo_data"
    YAML_PATH = EXTRACT_DIR / "data.yaml"
    MODEL_PATH = "yolov8n.pt"
    DATASET_URL = "https://drive.google.com/file/d/1cVks8umjCqEUKESH3YGKGZUvUze2rcRW/view?usp=sharing"
    WORKERS = min(4, os.cpu_count() // 2) if os.cpu_count() is not None else 2

# ========== HELPERS ==========
def clear_working_directory():
    """Clean the working directory while preserving input/lib."""
    print("🧹 Clearing working directory...")
    working_dir = Config.WORKING_DIR
    working_dir.mkdir(parents=True, exist_ok=True)

    for filename in os.listdir(working_dir):
        file_path = os.path.join(working_dir, filename)
        try:
            if os.path.isfile(file_path) or os.path.islink(file_path):
                os.unlink(file_path)
            elif os.path.isdir(file_path):
                shutil.rmtree(file_path)
        except Exception as e:
            print(f"Failed to delete {file_path}. Reason: {e}")
    print(" Workspace clean\n")

def download_dataset():
    """Download the dataset from Google Drive."""
    print(" Downloading dataset...")
    file_id = "1cVks8umjCqEUKESH3YGKGZUvUze2rcRW"
    gdown.download(f"https://drive.google.com/uc?id={file_id}", str(Config.ZIP_PATH), quiet=False)
    if not zipfile.is_zipfile(Config.ZIP_PATH):
        raise zipfile.BadZipFile(f"Downloaded file is not a valid zip file: {Config.ZIP_PATH}")
    print(" Download complete!")

def extract_dataset():
    """Extract the dataset zip file and clean up unnecessary files."""
    print(" Extracting dataset...")
    if not Config.ZIP_PATH.exists():
        raise FileNotFoundError(f"Dataset zip not found at {Config.ZIP_PATH}")
    try:
        with zipfile.ZipFile(Config.ZIP_PATH, 'r') as zip_ref:
            if zip_ref.testzip():
                raise zipfile.BadZipFile("Corrupted zip file detected")
            zip_ref.extractall(Config.EXTRACT_DIR)

        # Flatten folder if there's an extra top-level directory
        inner_dirs = list(Config.EXTRACT_DIR.iterdir())
        if len(inner_dirs) == 1 and inner_dirs[0].is_dir():
            inner_path = inner_dirs[0]
            for item in inner_path.iterdir():
                shutil.move(str(item), str(Config.EXTRACT_DIR))
            inner_path.rmdir()

        Config.ZIP_PATH.unlink()
        print(" Dataset extracted and cleaned\n")
    except Exception as e:
        raise Exception(f"Extraction failed: {e}")

def validate_dataset_structure():
    """Validate the dataset structure and ensure required fields are present."""
    print(" Validating dataset structure...")
    if not Config.YAML_PATH.exists():
        raise FileNotFoundError(f"YAML config not found at {Config.YAML_PATH}")
    with open(Config.YAML_PATH, 'r') as f:
        data = yaml.safe_load(f)
    required_fields = ['train', 'val', 'names']
    for field in required_fields:
        if field not in data:
            raise ValueError(f"Missing required field '{field}' in YAML")

    # Optional: Make class names more descriptive
    class_names = {
        i: name if not name.isdigit() else f"DIGIT_{name}"
        for i, name in enumerate(data['names'])
    }
    data['names'] = class_names

    with open(Config.YAML_PATH, 'w') as f:
        yaml.dump(data, f, sort_keys=False)

    print(" Dataset structure is valid\n")
    return data

def optimize_for_training():
    """Apply system-level optimizations for training."""
    print(" Applying training optimizations...")
    if torch.cuda.is_available():
        torch.backends.cudnn.benchmark = True
        torch.backends.cuda.matmul.allow_tf32 = True
    cv2.setNumThreads(Config.WORKERS)
    os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "max_split_size_mb:128"
    print(" Optimizations applied\n")

def train_model():
    """Train the YOLO model with the specified configuration."""
    print(" Starting model training...")
    model = YOLO(Config.MODEL_PATH)
    try:
        results = model.train(
            data=str(Config.YAML_PATH),
            epochs=100,
            imgsz=640,
            batch=8,
            workers=Config.WORKERS,
            device=0 if torch.cuda.is_available() else 'cpu',
            amp=True,
            patience=10,
            project="runs/detect",
            name="train",
            exist_ok=True,
            pretrained=True,
            optimizer="SGD",
            lr0=0.003,
            lrf=0.01,
            momentum=0.937,
            weight_decay=0.0005,
            warmup_epochs=5,
            warmup_momentum=0.8,
            box=5.0,
            cls=1.0,
            dfl=1.5,
            hsv_h=0.05,
            hsv_s=0.8,
            hsv_v=0.6,
            translate=0.2,
            scale=0.7,
            fliplr=0.5,
            mosaic=1.0,
            mixup=0.2
        )
        print("✅ Training complete")
        return results
    except Exception as e:
        print(f" Training failed: {e}")
        raise

# ========== MAIN ==========
def main():
    """Main function to execute the YOLO training pipeline."""
    start_time = time.time()
    try:
        # Step 1: Prepare the environment
        clear_working_directory()
        download_dataset()
        extract_dataset()
        validate_dataset_structure()
        optimize_for_training()

        # Step 2: Display system information
        print("\n⚡ System Information:")
        print(f"PyTorch: {torch.__version__}")
        print(f"CUDA: {torch.cuda.is_available()}")
        if torch.cuda.is_available():
            print(f"GPU: {torch.cuda.get_device_name(0)}")
            print(f"Memory: {torch.cuda.get_device_properties(0).total_memory / 1e9:.1f} GB")
        print(f"CPU Cores: {os.cpu_count()}\n")

        # Step 3: Train the model
        train_model()
        print(f"\n Pipeline completed in {time.time() - start_time:.1f} seconds")
    except Exception as e:
        print(f"\n Pipeline failed: {e}")
        raise

if __name__ == "__main__":
    main()
