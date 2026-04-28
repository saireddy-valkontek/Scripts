"""
combine_yolo_datasets.py
------------------------
Combines multiple YOLO datasets that have different classes into one unified dataset.

Supports BOTH common dataset layouts automatically:

  Layout A (split-first):          Layout B (images/labels-first):
    dataset_root/                    dataset_root/
      train/                           images/
        images/                          train/
        labels/                          val/
      valid/  (or val/, test/)         labels/
        images/                          train/
        labels/                          val/
      data.yaml                        data.yaml

Split name aliases: "valid" is treated the same as "val".

Usage:
  python combine_yolo_datasets.py \
    --datasets /path/to/ds1 /path/to/ds2 /path/to/ds3 \
    --output   /path/to/combined \
    [--splits train val test] \
    [--copy]   # copy files instead of symlinking
"""

import argparse
import os
import shutil
import yaml
from pathlib import Path


# ─────────────────────────────────────────────
# Split name normalisation
# "valid" and "val" are the same split
# ─────────────────────────────────────────────

SPLIT_ALIASES: dict[str, str] = {
    "valid": "val",
}

def canonical_split(split: str) -> str:
    """Return the canonical name for a split (e.g. 'valid' → 'val')."""
    return SPLIT_ALIASES.get(split.lower(), split.lower())


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def load_yaml(path: Path) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def get_class_names(dataset_root: Path) -> list[str]:
    """Return class name list from data.yaml inside the dataset root."""
    yaml_path = dataset_root / "data.yaml"
    if not yaml_path.exists():
        raise FileNotFoundError(f"data.yaml not found in {dataset_root}")
    cfg = load_yaml(yaml_path)
    names = cfg.get("names")
    if names is None:
        raise ValueError(f"'names' key missing in {yaml_path}")
    # Support both list and dict formats
    if isinstance(names, dict):
        names = [names[i] for i in sorted(names)]
    return names


def find_split_dirs(dataset_root: Path, canonical: str) -> tuple[Path | None, Path | None]:
    """
    Locate the images/ and labels/ directories for a given split,
    supporting both layout styles and the 'valid'/'val' alias.

    Returns (img_dir, lbl_dir) — either may be None if not found.
    """
    # All folder names on disk that map to this canonical split
    aliases = {canonical}
    reverse = {v: k for k, v in SPLIT_ALIASES.items()}
    if canonical in reverse:
        aliases.add(reverse[canonical])   # e.g. 'val' → also look for 'valid'

    for folder_name in aliases:
        # ── Layout A: <root>/<split>/images  and  <root>/<split>/labels ──
        img_a = dataset_root / folder_name / "images"
        lbl_a = dataset_root / folder_name / "labels"
        if img_a.exists():
            return img_a, lbl_a if lbl_a.exists() else None

        # ── Layout B: <root>/images/<split>  and  <root>/labels/<split> ──
        img_b = dataset_root / "images" / folder_name
        lbl_b = dataset_root / "labels" / folder_name
        if img_b.exists():
            return img_b, lbl_b if lbl_b.exists() else None

    return None, None


def remap_label_file(
    src: Path,
    dst: Path,
    old_to_new: dict[int, int],
) -> None:
    """Read a YOLO .txt label file, remap class ids, write to dst."""
    lines_out = []
    with open(src) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split()
            old_cls = int(parts[0])
            new_cls = old_to_new.get(old_cls)
            if new_cls is None:
                continue  # Class not in mapping — skip
            lines_out.append(f"{new_cls} " + " ".join(parts[1:]))
    dst.parent.mkdir(parents=True, exist_ok=True)
    with open(dst, "w") as f:
        f.write("\n".join(lines_out) + ("\n" if lines_out else ""))


def transfer(src: Path, dst: Path, use_copy: bool) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if use_copy:
        shutil.copy2(src, dst)
    else:
        if dst.exists() or dst.is_symlink():
            dst.unlink()
        dst.symlink_to(src.resolve())


def unique_stem(stem: str, existing: set[str], dataset_idx: int) -> str:
    """Guarantee a unique file stem to avoid collisions across datasets."""
    candidate = f"ds{dataset_idx}_{stem}"
    if candidate not in existing:
        return candidate
    counter = 0
    while f"{candidate}_{counter}" in existing:
        counter += 1
    return f"{candidate}_{counter}"


# ─────────────────────────────────────────────
# Core
# ─────────────────────────────────────────────

def combine_datasets(
    dataset_roots: list[Path],
    output_root: Path,
    splits: list[str],
    use_copy: bool,
) -> None:

    # ── 1. Build unified class list ──────────────────────────────────────────
    global_names: list[str] = []
    name_to_global_id: dict[str, int] = {}
    per_dataset_remaps: list[dict[int, int]] = []

    for ds_root in dataset_roots:
        local_names = get_class_names(ds_root)
        remap: dict[int, int] = {}
        for local_id, name in enumerate(local_names):
            if name not in name_to_global_id:
                name_to_global_id[name] = len(global_names)
                global_names.append(name)
            remap[local_id] = name_to_global_id[name]
        per_dataset_remaps.append(remap)

    print(f"\nUnified class list ({len(global_names)} classes):")
    for i, n in enumerate(global_names):
        print(f"   {i:3d}  {n}")

    # ── 2. Process each split ────────────────────────────────────────────────
    for split in splits:
        canon = canonical_split(split)          # normalise e.g. "valid" → "val"
        print(f"\nProcessing split: {split}" + (f" (→ '{canon}')" if canon != split else ""))
        used_stems: set[str] = set()

        for ds_idx, ds_root in enumerate(dataset_roots):
            img_dir, lbl_dir = find_split_dirs(ds_root, canon)

            if img_dir is None:
                print(f"  {ds_root.name}: no images for split '{split}' — skipping")
                continue

            remap = per_dataset_remaps[ds_idx]

            image_files = sorted(
                p for p in img_dir.iterdir()
                if p.suffix.lower() in {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".webp"}
            )

            for img_src in image_files:
                stem = unique_stem(img_src.stem, used_stems, ds_idx)
                used_stems.add(stem)

                # Image — always output under canonical split name
                img_dst = output_root / "images" / canon / (stem + img_src.suffix)
                transfer(img_src, img_dst, use_copy)

                # Label (may not exist for background images)
                lbl_src = (lbl_dir / (img_src.stem + ".txt")) if lbl_dir else None
                lbl_dst = output_root / "labels" / canon / (stem + ".txt")

                if lbl_src and lbl_src.exists():
                    remap_label_file(lbl_src, lbl_dst, remap)
                else:
                    # Empty label file for background images
                    lbl_dst.parent.mkdir(parents=True, exist_ok=True)
                    lbl_dst.touch()

            print(f"  {ds_root.name}: {len(image_files)} images added to '{canon}'")

    # ── 3. Write combined data.yaml ──────────────────────────────────────────
    out_yaml = output_root / "data.yaml"
    yaml_content = {
        "path": str(output_root.resolve()),
        "train": "images/train",
        "val":   "images/val",
        "test":  "images/test",
        "nc":    len(global_names),
        "names": global_names,
    }
    with open(out_yaml, "w") as f:
        yaml.dump(yaml_content, f, default_flow_style=False, sort_keys=False)

    print(f"\ndata.yaml written → {out_yaml}")
    print(f"Combined dataset at: {output_root}\n")


# ─────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────

def parse_args():
    parser = argparse.ArgumentParser(
        description="Combine multiple YOLO datasets with different classes."
    )
    parser.add_argument(
        "--datasets", nargs="+", required=True,
        help="Paths to each dataset root (must contain data.yaml, images/, labels/)."
    )
    parser.add_argument(
        "--output", required=True,
        help="Path for the combined output dataset."
    )
    parser.add_argument(
        "--splits", nargs="+", default=["train", "valid"],
        help="Dataset splits to process (default: train valid). 'valid' and 'val' are interchangeable."
    )
    parser.add_argument(
        "--copy", action="store_true",
        help="Copy files instead of creating symlinks (slower but self-contained)."
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    dataset_roots = [Path(p) for p in args.datasets]
    output_root   = Path(args.output)

    for p in dataset_roots:
        if not p.exists():
            raise SystemExit(f"Dataset path not found: {p}")

    output_root.mkdir(parents=True, exist_ok=True)

    combine_datasets(
        dataset_roots=dataset_roots,
        output_root=output_root,
        splits=args.splits,
        use_copy=args.copy,
    )
    
    
"""
run command :
python C:\Users\valkontek005\Downloads\combine_yolo_datasets.py `
  --datasets C:\Users\valkontek005\Data\dent `
             C:\Users\valkontek005\Data\Number_Plate `
             C:\Users\valkontek005\Data\scratch `
             C:\Users\valkontek005\Data\windshield `
  --output   C:\Users\valkontek005\Data\combined `
  --splits   train valid `
  --copy
"""
