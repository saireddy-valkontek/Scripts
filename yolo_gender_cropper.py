import logging
import os
import shutil
import threading
import time
from collections import deque
from pathlib import Path

import cv2
import PIL.Image as PILImage
from PIL import ImageTk
from tkinter import *
from tkinter import font as tkfont, messagebox, ttk
from transformers import pipeline as hf_pipeline
from ultralytics import YOLO

# ──────────────────────────────────────────────────────────────────────────────
# LOGGING
# ──────────────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# SETTINGS  (edit these)
# ──────────────────────────────────────────────────────────────────────────────
IMAGE_FOLDER   = r"C:\Users\valkontek005\Downloads\pin\b"
OUTPUT_BASE    = "accepted_crops"
UNUSABLE_FOLDER = "unusable_images"
YOLO_MODEL     = "yolov8m.pt"
YOLO_CONF      = 0.40
GENDER_MODEL   = "rizvandwiki/gender-classification-2"
PREFETCH_AHEAD = 15 
PREFETCH_BEHIND = 5
UNDO_LIMIT     = 30
HANDLE_RADIUS  = 5    # px on canvas
HANDLE_MARGIN  = 12   # px hit-test tolerance on canvas
MIN_IMAGE_WIDTH  = 64
MIN_IMAGE_HEIGHT = 64
ZOOM_STEP        = 1.18
ZOOM_MIN         = 0.25
ZOOM_MAX         = 4.5

# ──────────────────────────────────────────────────────────────────────────────
# PALETTE
# ──────────────────────────────────────────────────────────────────────────────
C_FEMALE   = "#ff69b4"
C_MALE     = "#4fc3f7"
C_UNKNOWN  = "#aaaaaa"
C_SELECTED = "#ffff00"
C_SAVED    = "#444444"
C_BG       = "#111111"
C_PANEL    = "#1a1a1a"
C_PANEL2   = "#222222"
C_TEXT     = "#e0e0e0"
C_SUCCESS  = "#00e676"
C_WARNING  = "#ffeb3b"
C_ERROR    = "#ff5252"
C_INFO     = "#00e5ff"
C_MUTED    = "#555555"

GENDER_COLORS = {"female": C_FEMALE, "male": C_MALE, "unknown": C_UNKNOWN}
GENDER_CYCLE  = ["male", "female", "unknown"]

# ──────────────────────────────────────────────────────────────────────────────
# LOAD MODELS
# ──────────────────────────────────────────────────────────────────────────────
log.info("Loading YOLO model…")
try:
    yolo_model = YOLO(YOLO_MODEL)
    log.info("YOLO ready.")
except Exception as exc:
    log.critical("Failed to load YOLO: %s", exc)
    raise SystemExit(1) from exc

log.info("Loading gender classifier…")
try:
    gender_clf = hf_pipeline(
        "image-classification",
        model=GENDER_MODEL,
        device=-1,
    )
    log.info("Gender classifier ready.")
except Exception as exc:
    log.warning("Gender model unavailable: %s", exc)
    gender_clf = None

# ──────────────────────────────────────────────────────────────────────────────
# DISCOVER IMAGES
# ──────────────────────────────────────────────────────────────────────────────
VALID_EXT = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
image_files: list[str] = sorted(
    str(p) for p in Path(IMAGE_FOLDER).iterdir() if p.suffix.lower() in VALID_EXT
)
if not image_files:
    log.critical("No images found in: %s", IMAGE_FOLDER)
    raise SystemExit(1)
log.info("Found %d images.", len(image_files))

# ──────────────────────────────────────────────────────────────────────────────
# APPLICATION STATE  (single object instead of scattered globals)
# ──────────────────────────────────────────────────────────────────────────────
class AppState:
    def __init__(self) -> None:
        self.current_index:  int   = 0
        self.persons:        list  = []   # [{box, gender, conf, saved}, …]
        self.selected_idx:   int   = -1
        self.original_image        = None  # cv2 BGR ndarray
        self.tk_image              = None  # kept alive to prevent GC

        # Canvas viewport (updated on Configure event)
        self.canvas_w: int = 800
        self.canvas_h: int = 600

        # View transform
        self.scale:    float = 1.0
        self.offset_x: int   = 0
        self.offset_y: int   = 0
        self.zoom:     float = 1.0

        # Mouse drag state
        self.dragging:     bool         = False
        self.resize_mode:  str | None   = None
        self.drag_start:   tuple[int,int] = (0, 0)
        self.temp_new_box: list | None  = None

        # Undo / Redo
        self.undo_stack: deque = deque(maxlen=UNDO_LIMIT)
        self.redo_stack: deque = deque(maxlen=UNDO_LIMIT)

        # Stats
        self.total_saved: int = 0


st = AppState()

# ──────────────────────────────────────────────────────────────────────────────
# BACKGROUND INFERENCE CACHE
# ──────────────────────────────────────────────────────────────────────────────
inference_cache: dict = {}   # index → {image: ndarray|None, persons: list}
cache_lock   = threading.Lock()
stop_event   = threading.Event()
skipped_indices: set[int] = set()

# ──────────────────────────────────────────────────────────────────────────────
# UTILITY HELPERS
# ──────────────────────────────────────────────────────────────────────────────
def deep_copy_persons(persons: list) -> list:
    return [dict(p, box=list(p["box"])) for p in persons]


def clamp_box(box: list, w: int, h: int) -> list:
    x1, y1, x2, y2 = box
    x1, x2 = sorted([x1, x2])
    y1, y2 = sorted([y1, y2])
    return [max(0, x1), max(0, y1), min(w, x2), min(h, y2)]


def get_image_path(index: int) -> str | None:
    if 0 <= index < len(image_files) and index not in skipped_indices:
        return image_files[index]
    return None


def find_next_valid_index(start: int, step: int = 1) -> int | None:
    index = start
    while 0 <= index < len(image_files):
        if index not in skipped_indices:
            return index
        index += step
    return None


def normalize_current_index() -> bool:
    if get_image_path(st.current_index) is not None:
        return True
    next_index = find_next_valid_index(st.current_index + 1, 1)
    if next_index is not None:
        st.current_index = next_index
        return True
    prev_index = find_next_valid_index(st.current_index - 1, -1)
    if prev_index is not None:
        st.current_index = prev_index
        return True
    return False


def _rects_overlap(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> bool:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    return not (ax2 < bx1 or ax1 > bx2 or ay2 < by1 or ay1 > by2)


def _box_iou(a: list[int], b: list[int]) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    inter_x1 = max(ax1, bx1)
    inter_y1 = max(ay1, by1)
    inter_x2 = min(ax2, bx2)
    inter_y2 = min(ay2, by2)
    if inter_x2 <= inter_x1 or inter_y2 <= inter_y1:
        return 0.0
    inter_area = (inter_x2 - inter_x1) * (inter_y2 - inter_y1)
    area_a = max(0, ax2 - ax1) * max(0, ay2 - ay1)
    area_b = max(0, bx2 - bx1) * max(0, by2 - by1)
    union_area = area_a + area_b - inter_area
    return inter_area / union_area if union_area > 0 else 0.0


def filter_overlapping_boxes(persons: list[dict], iou_threshold: float = 0.35) -> list[dict]:
    kept: list[dict] = []
    sorted_persons = sorted(persons, key=lambda x: x["conf"], reverse=True)
    for person in sorted_persons:
        if any(_box_iou(person["box"], other["box"]) > iou_threshold for other in kept):
            continue
        kept.append(person)
    return sorted(kept, key=lambda x: x["box"])


def compute_label_positions(persons: list[dict]) -> list[tuple[int, int]]:
    positions = []
    occupied: list[tuple[int,int,int,int]] = []
    for p in persons:
        x1, y1, x2, y2 = p["box"]
        cx1, cy1 = orig_to_canvas(x1, y1)
        cx2, cy2 = orig_to_canvas(x2, y2)
        label = f"{p['gender'].upper()} {p['conf']:.0%}" if p["conf"] > 0 else p['gender'].upper()
        text_width = max(80, len(label) * 7)
        text_height = 16

        candidates = [
            (cx1 + 6, cy1 - text_height - 6),
            (cx2 - text_width - 6, cy1 - text_height - 6),
            (cx1 + 6, cy2 + 6),
            (cx2 - text_width - 6, cy2 + 6),
        ]

        chosen = None
        for x, y in candidates:
            rect = (x - 4, y - text_height - 2, x + text_width + 4, y + 4)
            if x < 4 or y < 4 or rect[2] > st.canvas_w - 4 or rect[3] > st.canvas_h - 4:
                continue
            if not any(_rects_overlap(rect, occ) for occ in occupied):
                chosen = (x, y)
                occupied.append(rect)
                break

        if chosen is None:
            x, y = candidates[0]
            rect = (x - 4, y - text_height - 2, x + text_width + 4, y + 4)
            attempts = 0
            while any(_rects_overlap(rect, occ) for occ in occupied) and attempts < 8:
                y -= text_height + 6
                if y < 4:
                    y = cy2 + 6
                rect = (x - 4, y - text_height - 2, x + text_width + 4, y + 4)
                attempts += 1
            occupied.append(rect)
            chosen = (x, y)

        positions.append(chosen)
    return positions


def move_current_image(target_dir: str, message: str) -> None:
    current = get_image_path(st.current_index)
    if current is None:
        return
    src = Path(current)
    dest = Path(target_dir) / src.name
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        shutil.move(str(src), str(dest))
    except Exception as exc:
        log.error("Failed to move %s to %s: %s", src, dest, exc)
        set_status(f"Failed to move file: {src.name}", C_ERROR)
        return
    skipped_indices.add(st.current_index)
    with cache_lock:
        inference_cache.pop(st.current_index, None)
    set_status(message, C_WARNING)
    if not normalize_current_index():
        st.original_image = None
        st.persons = []
        render()
        set_status("No remaining images.", C_INFO)
    else:
        show_image()


def delete_current_image(message: str) -> None:
    current = get_image_path(st.current_index)
    if current is None:
        return
    try:
        Path(current).unlink()
    except Exception as exc:
        log.error("Failed to delete %s: %s", current, exc)
        set_status(f"Failed to delete {Path(current).name}", C_ERROR)
        return
    skipped_indices.add(st.current_index)
    with cache_lock:
        inference_cache.pop(st.current_index, None)
    set_status(message, C_SUCCESS)
    if not normalize_current_index():
        st.original_image = None
        st.persons = []
        render()
        set_status("No remaining images.", C_INFO)
    else:
        show_image()


def cleanup_current_after_save() -> bool:
    if not st.persons or any(not p['saved'] for p in st.persons):
        return False
    if get_image_path(st.current_index) is None:
        return False
    delete_current_image("All crops saved; source image removed.")
    return True


def zoom_at(cursor_x: int, cursor_y: int, scale_delta: float) -> None:
    if st.original_image is None:
        return
    old_scale = st.scale
    st.zoom = max(ZOOM_MIN, min(ZOOM_MAX, st.zoom * scale_delta))
    if old_scale == 0:
        return
    img_x, img_y = canvas_to_orig(cursor_x, cursor_y)
    st.scale = min(st.canvas_w / st.original_image.shape[1], st.canvas_h / st.original_image.shape[0], 1.0) * st.zoom
    cx, cy = orig_to_canvas(img_x, img_y)
    st.offset_x += cursor_x - cx
    st.offset_y += cursor_y - cy
    render()


def zoom_in(e=None) -> None:
    if st.original_image is None:
        return
    zoom_at(st.canvas_w // 2, st.canvas_h // 2, ZOOM_STEP)


def zoom_out(e=None) -> None:
    if st.original_image is None:
        return
    zoom_at(st.canvas_w // 2, st.canvas_h // 2, 1.0 / ZOOM_STEP)


def zoom_reset(e=None) -> None:
    if st.original_image is None:
        return
    st.zoom = 1.0
    render()


def mouse_wheel_zoom(event) -> None:
    if st.original_image is None:
        return
    delta = 1.0 + (ZOOM_STEP - 1.0) if event.delta > 0 else 1.0 / (ZOOM_STEP + 0.0)
    zoom_at(event.x, event.y, delta)


def mark_current_unusable(e=None) -> None:
    move_current_image(Path(OUTPUT_BASE) / UNUSABLE_FOLDER, "Marked as unusable and moved away.")


# ──────────────────────────────────────────────────────────────────────────────
# UNDO / REDO
# ──────────────────────────────────────────────────────────────────────────────
def push_undo() -> None:
    st.undo_stack.append((deep_copy_persons(st.persons), st.selected_idx))
    st.redo_stack.clear()


def undo(e=None) -> None:
    if not st.undo_stack:
        set_status("Nothing to undo.", C_WARNING)
        return
    st.redo_stack.append((deep_copy_persons(st.persons), st.selected_idx))
    st.persons, st.selected_idx = st.undo_stack.pop()
    render()
    set_status("Undo.", C_INFO)


def redo(e=None) -> None:
    if not st.redo_stack:
        set_status("Nothing to redo.", C_WARNING)
        return
    st.undo_stack.append((deep_copy_persons(st.persons), st.selected_idx))
    st.persons, st.selected_idx = st.redo_stack.pop()
    render()
    set_status("Redo.", C_INFO)


# ──────────────────────────────────────────────────────────────────────────────
# GENDER CLASSIFICATION
# ──────────────────────────────────────────────────────────────────────────────
def classify_gender(cv2_img, box: list) -> tuple[str, float]:
    if gender_clf is None or cv2_img is None:
        return "unknown", 0.0
    h, w = cv2_img.shape[:2]
    x1, y1, x2, y2 = clamp_box([int(v) for v in box], w, h)
    if x2 <= x1 or y2 <= y1:
        return "unknown", 0.0
    crop = cv2_img[y1:y2, x1:x2]
    if crop.size == 0:
        return "unknown", 0.0
    try:
        rgb  = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
        pil  = PILImage.fromarray(rgb)
        res  = gender_clf(pil)[0]
        lbl  = res["label"].lower()
        conf = round(float(res["score"]), 4)
        if "female" in lbl:
            return "female", conf
        if "male" in lbl:
            return "male", conf
        return "unknown", conf
    except Exception as exc:
        log.debug("classify_gender error: %s", exc)
        return "unknown", 0.0


# ──────────────────────────────────────────────────────────────────────────────
# PERSON DETECTION
# ──────────────────────────────────────────────────────────────────────────────
def detect_people(image) -> list:
    persons = []
    try:
        results = yolo_model(image, verbose=False)
        for result in results:
            for box in result.boxes:
                if int(box.cls[0]) != 0:   # class 0 = person
                    continue
                conf = float(box.conf[0])
                if conf < YOLO_CONF:
                    continue
                coords = list(map(int, box.xyxy[0]))
                gender, gconf = classify_gender(image, coords)
                persons.append({
                    "box":    coords,
                    "gender": gender,
                    "conf":   gconf,
                    "saved":  False,
                })
        persons = filter_overlapping_boxes(persons)
    except Exception as exc:
        log.error("detect_people error: %s", exc)
    return persons


# ──────────────────────────────────────────────────────────────────────────────
# BACKGROUND WORKER
# ──────────────────────────────────────────────────────────────────────────────
def inference_worker() -> None:
    while not stop_event.is_set():
        ci = st.current_index  # atomic read on CPython

        with cache_lock:
            keep = set(i for i in range(max(0, ci - PREFETCH_BEHIND),
                                        min(len(image_files), ci + PREFETCH_AHEAD))
                       if i not in skipped_indices)
            # Evict stale entries
            for k in list(inference_cache):
                if k not in keep:
                    del inference_cache[k]
            # Find first uncached index ahead of cursor
            to_process = next(
                (i for i in range(ci, ci + PREFETCH_AHEAD)
                 if i < len(image_files) and i not in inference_cache and i not in skipped_indices),
                None,
            )

        if to_process is None:
            stop_event.wait(timeout=0.1)
            continue

        path = image_files[to_process]
        try:
            img = cv2.imread(path)
            entry = (
                {"image": img, "persons": detect_people(img)}
                if img is not None
                else {"image": None, "persons": []}
            )
            if img is None:
                log.warning("Could not read: %s", path)
        except Exception as exc:
            log.error("Worker error on %s: %s", path, exc)
            entry = {"image": None, "persons": []}

        with cache_lock:
            # Don't overwrite if user manually navigated here already
            if to_process not in inference_cache:
                inference_cache[to_process] = entry

        root.after(0, update_prefetch_bar)
        stop_event.wait(timeout=0.01)


# ──────────────────────────────────────────────────────────────────────────────
# COORDINATE HELPERS
# ──────────────────────────────────────────────────────────────────────────────
def orig_to_canvas(x: float, y: float) -> tuple[int, int]:
    return (int(x * st.scale + st.offset_x),
            int(y * st.scale + st.offset_y))


def canvas_to_orig(x: float, y: float) -> tuple[int, int]:
    s = st.scale or 1.0
    return (int((x - st.offset_x) / s),
            int((y - st.offset_y) / s))


# ──────────────────────────────────────────────────────────────────────────────
# PREFETCH BAR
# ──────────────────────────────────────────────────────────────────────────────
def update_prefetch_bar() -> None:
    ci = st.current_index
    if ci < 0 or ci >= len(image_files):
        prefetch_bar["value"] = 100
        return
    with cache_lock:
        valid = [i for i in range(ci, min(len(image_files), ci + PREFETCH_AHEAD)) if i not in skipped_indices]
        total = len(valid)
        if total == 0:
            prefetch_bar["value"] = 100
            return
        cached = sum(1 for i in valid if i in inference_cache)
    prefetch_bar["value"] = int(cached / total * 100)


# ──────────────────────────────────────────────────────────────────────────────
# RENDER
# ──────────────────────────────────────────────────────────────────────────────
def render() -> None:
    if st.original_image is None:
        canvas.delete("all")
        canvas.create_text(
            st.canvas_w // 2, st.canvas_h // 2,
            text="⏳  Processing Image…",
            fill="white", font=("Segoe UI", 16),
        )
        _update_info()
        return

    img   = st.original_image
    h, w  = img.shape[:2]
    fit_scale = min(st.canvas_w / w, st.canvas_h / h, 1.0) if w > 0 and h > 0 else 1.0
    st.scale = max(ZOOM_MIN, min(ZOOM_MAX, fit_scale * st.zoom))
    nw, nh = int(w * st.scale), int(h * st.scale)
    st.offset_x = (st.canvas_w - nw) // 2
    st.offset_y = (st.canvas_h - nh) // 2

    resized   = cv2.resize(img, (nw, nh), interpolation=cv2.INTER_AREA)
    rgb       = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
    st.tk_image = ImageTk.PhotoImage(PILImage.fromarray(rgb))

    canvas.delete("all")
    canvas.create_image(st.offset_x, st.offset_y, image=st.tk_image, anchor=NW)

    label_positions = compute_label_positions(st.persons)
    for i, p in enumerate(st.persons):
        _draw_box(i, p, label_positions[i])

    if st.temp_new_box:
        x1, y1, x2, y2 = st.temp_new_box
        cx1, cy1 = orig_to_canvas(x1, y1)
        cx2, cy2 = orig_to_canvas(x2, y2)
        canvas.create_rectangle(cx1, cy1, cx2, cy2,
                                 outline=C_SELECTED, width=2, dash=(5, 3))

    current_path = get_image_path(st.current_index)
    name = Path(current_path).name if current_path else "(skipped)"
    root.title(f"YOLO Gender Cropper  ·  {st.current_index + 1}/{len(image_files)}  ·  {name}")
    _update_info()


def _draw_box(i: int, p: dict, label_pos: tuple[int, int]) -> None:
    x1, y1, x2, y2 = p["box"]
    cx1, cy1 = orig_to_canvas(x1, y1)
    cx2, cy2 = orig_to_canvas(x2, y2)
    is_sel   = (i == st.selected_idx)

    if p["saved"]:
        color = C_SAVED
    elif is_sel:
        color = C_SELECTED
    else:
        color = GENDER_COLORS.get(p["gender"], C_UNKNOWN)

    canvas.create_rectangle(cx1, cy1, cx2, cy2,
                             outline=color, width=3 if is_sel else 2)

    # 8-point resize handles on selected box
    if is_sel:
        mx, my = (cx1 + cx2) // 2, (cy1 + cy2) // 2
        r = HANDLE_RADIUS
        for hx, hy in [(cx1, cy1), (mx, cy1), (cx2, cy1),
                       (cx1,  my),             (cx2,  my),
                       (cx1, cy2), (mx, cy2), (cx2, cy2)]:
            canvas.create_oval(hx - r, hy - r, hx + r, hy + r,
                                fill=color, outline="white", width=1)

    # Label with drop-shadow and background
    conf_str  = f" {p['conf']:.0%}" if p["conf"] > 0 else ""
    saved_str = " ✓" if p["saved"] else ""
    label     = f"{p['gender'].upper()}{conf_str}{saved_str}"
    lx, ly = label_pos
    text_font = ("Consolas", 9, "bold")
    text_id = canvas.create_text(lx + 1, ly + 1, text=label, fill="black",
                                 anchor=NW, font=text_font)
    bbox = canvas.bbox(text_id)
    if bbox:
        canvas.create_rectangle(bbox[0] - 3, bbox[1] - 2,
                                bbox[2] + 3, bbox[3] + 2,
                                fill="#111111", outline=color, width=1)
        canvas.lift(text_id)
    canvas.create_text(lx, ly, text=label, fill=color,
                       anchor=NW, font=text_font)


def _update_info() -> None:
    persons = st.persons
    males   = sum(1 for p in persons if p["gender"] == "male")
    females = sum(1 for p in persons if p["gender"] == "female")
    unknown = sum(1 for p in persons if p["gender"] == "unknown")
    saved   = sum(1 for p in persons if p["saved"])

    img_size = "N/A"
    if st.original_image is not None:
        h, w = st.original_image.shape[:2]
        img_size = f"{w}×{h}"

    lines = [
        f"📁  {Path(image_files[st.current_index]).name}",
        f"    {st.current_index + 1} / {len(image_files)}",
        "",
        f"🖼  Res      {img_size}",
        f"🔍  Zoom     {int(st.zoom * 100)}%",
        "",
        f"👥  Total    {len(persons)}",
        f"♂   Male     {males}",
        f"♀   Female   {females}",
        f"?   Unknown  {unknown}",
        f"✓   Saved    {saved}",
        f"💾  Total    {st.total_saved}",
    ]
    if 0 <= st.selected_idx < len(persons):
        p  = persons[st.selected_idx]
        bx = p["box"]
        lines += [
            "",
            f"── Box #{st.selected_idx + 1} selected ──",
            f"   Gender  {p['gender'].upper()}",
            f"   Conf    {p['conf']:.1%}",
            f"   Size    {bx[2]-bx[0]}×{bx[3]-bx[1]} px",
            f"   Saved   {'Yes ✓' if p['saved'] else 'No'}",
        ]
    else:
        lines.append("\n  No box selected")

    sidebar_info.config(text="\n".join(lines))


# ──────────────────────────────────────────────────────────────────────────────
# NAVIGATION
# ──────────────────────────────────────────────────────────────────────────────
def poll_cache() -> None:
    if not normalize_current_index():
        st.original_image = None
        st.persons = []
        render()
        set_status("No images remaining.", C_INFO)
        return

    with cache_lock:
        data = inference_cache.get(st.current_index)

    if data is not None:
        st.original_image = data["image"].copy() if data["image"] is not None else None
        st.persons        = deep_copy_persons(data["persons"])
        st.selected_idx   = 0 if st.persons else -1
        st.undo_stack.clear()
        st.redo_stack.clear()
        if st.original_image is not None:
            h, w = st.original_image.shape[:2]
            if w < MIN_IMAGE_WIDTH or h < MIN_IMAGE_HEIGHT:
                move_current_image(Path(OUTPUT_BASE) / UNUSABLE_FOLDER,
                                   f"Moved {Path(image_files[st.current_index]).name} to unusable (too small).")
                return
        current = get_image_path(st.current_index)
        name = Path(current).name if current else "(unknown)"
        set_status(f"Loaded: {name}", C_SUCCESS)
        render()
    else:
        st.original_image = None
        st.persons        = []
        render()
        set_status("Processing in background…", C_WARNING)
        root.after(100, poll_cache)


def show_image() -> None:
    if not normalize_current_index():
        st.original_image = None
        st.persons = []
        render()
        set_status("No valid images to show.", C_INFO)
        return
    update_prefetch_bar()
    poll_cache()


def _navigate(delta: int) -> None:
    start = st.current_index + delta
    step = 1 if delta >= 0 else -1
    next_index = find_next_valid_index(start, step)
    if next_index is not None:
        st.current_index = next_index
        show_image()


def next_image(e=None) -> None: _navigate(+1)
def prev_image(e=None) -> None: _navigate(-1)


def goto_next_unprocessed(e=None) -> None:
    """Jump to the next image that still has at least one unsaved person."""
    for i in range(st.current_index + 1, len(image_files)):
        if i in skipped_indices:
            continue
        with cache_lock:
            data = inference_cache.get(i)
        if data is None or any(not p["saved"] for p in data["persons"]):
            st.current_index = i
            show_image()
            return
    set_status("No more unprocessed images ahead.", C_INFO)


def next_person(e=None) -> None:
    if not st.persons: return
    st.selected_idx = (st.selected_idx + 1) % len(st.persons)
    render()


def prev_person(e=None) -> None:
    if not st.persons: return
    st.selected_idx = (st.selected_idx - 1) % len(st.persons)
    render()


# ──────────────────────────────────────────────────────────────────────────────
# EDITING ACTIONS
# ──────────────────────────────────────────────────────────────────────────────
def toggle_gender(e=None) -> None:
    if not st.persons or st.selected_idx < 0: return
    push_undo()
    p = st.persons[st.selected_idx]
    if p["gender"] == "female":
        p["gender"] = "male"
    else:
        p["gender"] = "female"
    render()


def reclassify_selected(e=None) -> None:
    if st.original_image is None or st.selected_idx < 0: return
    push_undo()
    p = st.persons[st.selected_idx]
    set_status("Reclassifying…", C_WARNING)
    root.update_idletasks()
    gender, conf = classify_gender(st.original_image, p["box"])
    p["gender"], p["conf"] = gender, conf
    render()
    set_status(f"Reclassified → {gender.upper()} ({conf:.1%})", C_SUCCESS)


def delete_person(e=None) -> None:
    if not st.persons or st.selected_idx < 0: return
    push_undo()
    del st.persons[st.selected_idx]
    st.selected_idx = min(st.selected_idx, len(st.persons) - 1)
    if not st.persons:
        st.selected_idx = -1
    render()
    set_status("Box deleted.", C_ERROR)


def _save_person(img_idx: int, person_idx: int, p: dict) -> None:
    img_path = image_files[img_idx]
    stem     = Path(img_path).stem
    h, w     = st.original_image.shape[:2]
    x1, y1, x2, y2 = clamp_box(p["box"], w, h)

    if x2 <= x1 or y2 <= y1:
        log.warning("Degenerate box skipped: %s", p["box"])
        return

    crop       = st.original_image[y1:y2, x1:x2]
    out_folder = Path(OUTPUT_BASE) / p["gender"]
    out_folder.mkdir(parents=True, exist_ok=True)

    # Unique filename
    counter = 0
    while True:
        suffix    = f"_{counter}" if counter else ""
        filename  = f"{stem}_person{person_idx + 1}{suffix}.jpg"
        save_path = out_folder / filename
        if not save_path.exists():
            break
        counter += 1

    cv2.imwrite(str(save_path), crop)

    p["saved"] = True
    st.total_saved += 1
    log.info("Saved: %s", save_path)


def accept_selected(e=None) -> None:
    if st.original_image is None or st.selected_idx < 0:
        set_status("No box selected.", C_WARNING)
        return
    p = st.persons[st.selected_idx]
    if p["saved"]:
        set_status("Already saved.", C_WARNING)
        return
    _save_person(st.current_index, st.selected_idx, p)
    render()
    set_status(f"Saved box #{st.selected_idx + 1}.", C_SUCCESS)
    if cleanup_current_after_save():
        return


def accept_all(e=None) -> None:
    if st.original_image is None:
        set_status("No image loaded.", C_WARNING)
        return
    if not st.persons:
        set_status("No persons detected.", C_WARNING)
        root.after(400, next_image)
        return

    count = 0
    for i, p in enumerate(st.persons):
        if not p["saved"]:
            _save_person(st.current_index, i, p)
            count += 1

    render()
    if cleanup_current_after_save():
        return
    msg = f"Saved {count} new crop(s). Moving on…" if count else "All already saved. Moving on…"
    set_status(msg, C_SUCCESS if count else C_INFO)
    root.after(600, next_image)


# ──────────────────────────────────────────────────────────────────────────────
# MOUSE EVENTS
# ──────────────────────────────────────────────────────────────────────────────
def _resolve_resize_mode(cx: float, cy: float,
                         box_canvas: tuple[int,int,int,int]) -> str:
    """Return 'move' or a named edge/corner based on proximity to handles."""
    cx1, cy1, cx2, cy2 = box_canvas
    mx, my = (cx1 + cx2) // 2, (cy1 + cy2) // 2
    m = HANDLE_MARGIN
    tests = [
        (cx1, cy1, "top_left"),    (mx, cy1, "top"),    (cx2, cy1, "top_right"),
        (cx1,  my, "left"),                              (cx2,  my, "right"),
        (cx1, cy2, "bottom_left"), (mx, cy2, "bottom"), (cx2, cy2, "bottom_right"),
    ]
    for hx, hy, mode in tests:
        if abs(cx - hx) <= m and abs(cy - hy) <= m:
            return mode
    return "move"


def canvas_click(event) -> None:
    if st.original_image is None: return
    ox, oy = canvas_to_orig(event.x, event.y)
    margin = HANDLE_MARGIN / (st.scale or 1.0)

    st.dragging   = True
    st.drag_start = (ox, oy)

    # Hit-test persons in reverse paint order (topmost first)
    for i in range(len(st.persons) - 1, -1, -1):
        p = st.persons[i]
        x1, y1, x2, y2 = p["box"]
        if x1 - margin <= ox <= x2 + margin and y1 - margin <= oy <= y2 + margin:
            st.selected_idx = i
            bc = (*orig_to_canvas(x1, y1), *orig_to_canvas(x2, y2))
            st.resize_mode  = _resolve_resize_mode(event.x, event.y, bc)
            render()
            return

    # Empty space → start drawing new box
    st.selected_idx  = -1
    st.resize_mode   = "create"
    st.temp_new_box  = [ox, oy, ox, oy]
    render()


def drag_box(event) -> None:
    if not st.dragging or st.original_image is None: return
    h, w = st.original_image.shape[:2]
    ox   = max(0, min(w, canvas_to_orig(event.x, event.y)[0]))
    oy   = max(0, min(h, canvas_to_orig(event.x, event.y)[1]))
    sx, sy = st.drag_start

    if st.resize_mode == "create":
        st.temp_new_box = [min(sx, ox), min(sy, oy), max(sx, ox), max(sy, oy)]
        render()
        return

    if st.selected_idx < 0: return
    p  = st.persons[st.selected_idx]
    x1, y1, x2, y2 = p["box"]
    dx, dy = ox - sx, oy - sy
    m = st.resize_mode

    if   m == "move":         x1+=dx; x2+=dx; y1+=dy; y2+=dy
    elif m == "left":         x1+=dx
    elif m == "right":        x2+=dx
    elif m == "top":          y1+=dy
    elif m == "bottom":       y2+=dy
    elif m == "top_left":     x1+=dx; y1+=dy
    elif m == "top_right":    x2+=dx; y1+=dy
    elif m == "bottom_left":  x1+=dx; y2+=dy
    elif m == "bottom_right": x2+=dx; y2+=dy

    p["box"]      = [x1, y1, x2, y2]
    st.drag_start = (ox, oy)
    render()


def stop_drag(event) -> None:
    if not st.dragging: return

    if st.resize_mode == "create" and st.temp_new_box:
        x1, y1, x2, y2 = st.temp_new_box
        if abs(x2 - x1) > 20 and abs(y2 - y1) > 20:
            push_undo()
            set_status("Classifying new box…", C_WARNING)
            root.update_idletasks()
            gender, conf = classify_gender(st.original_image, st.temp_new_box)
            st.persons.append({
                "box":    [int(x1), int(y1), int(x2), int(y2)],
                "gender": gender,
                "conf":   conf,
                "saved":  False,
            })
            st.selected_idx = len(st.persons) - 1
            set_status(f"Added box: {gender.upper()} ({conf:.1%})", C_SUCCESS)
        st.temp_new_box = None

    elif st.selected_idx >= 0 and st.original_image is not None:
        h, w = st.original_image.shape[:2]
        st.persons[st.selected_idx]["box"] = clamp_box(
            st.persons[st.selected_idx]["box"], w, h
        )

    st.dragging    = False
    st.resize_mode = None
    render()


# ──────────────────────────────────────────────────────────────────────────────
# CANVAS RESIZE
# ──────────────────────────────────────────────────────────────────────────────
def on_canvas_resize(event) -> None:
    st.canvas_w = event.width
    st.canvas_h = event.height
    render()


# ──────────────────────────────────────────────────────────────────────────────
# GUI CONSTRUCTION
# ──────────────────────────────────────────────────────────────────────────────
root = Tk()
root.title("YOLO Gender Cropper")
root.geometry("1240x780")
root.minsize(980, 680)
root.configure(bg=C_BG)

main_paned = PanedWindow(root, orient=HORIZONTAL, bg=C_BG,
                          sashwidth=5, sashrelief=FLAT)
main_paned.pack(fill=BOTH, expand=True)

# ── Left: controls ───────────────────────────────────────────────────────────
left_sidebar = Frame(main_paned, bg=C_PANEL, width=260)
main_paned.add(left_sidebar, stretch="never")

# ── Center: image ─────────────────────────────────────────────────────────────
center_frame = Frame(main_paned, bg="black")
main_paned.add(center_frame, stretch="always")

canvas = Canvas(center_frame, bg="#0a0a0a", highlightthickness=0)
canvas.pack(fill=BOTH, expand=True)
canvas.bind("<Button-1>",        canvas_click)
canvas.bind("<B1-Motion>",       drag_box)
canvas.bind("<ButtonRelease-1>", stop_drag)
canvas.bind("<Configure>",       on_canvas_resize)
canvas.bind("<MouseWheel>",      mouse_wheel_zoom)

# ── Right: controls ──────────────────────────────────────────────────────────
right_sidebar = Frame(main_paned, bg=C_PANEL, width=260)
main_paned.add(right_sidebar, stretch="never")


def _section(parent: Frame, title: str) -> None:
    f = Frame(parent, bg=C_PANEL)
    f.pack(fill=X, padx=10, pady=(10, 2))
    Label(f, text=title, bg=C_PANEL, fg="#666666",
          font=("Segoe UI", 7, "bold")).pack(side=LEFT)
    Frame(f, bg="#333333", height=1).pack(side=LEFT, fill=X, expand=True, padx=(6, 0))


def _btn(parent: Frame, text: str, cmd, bg: str, key: str = "") -> Button:
    row = Frame(parent, bg=C_PANEL)
    row.pack(fill=X, padx=10, pady=2)
    b = Button(row, text=text, command=cmd, bg=bg, fg="white",
               activebackground=bg, activeforeground=C_SELECTED,
               font=("Segoe UI", 9, "bold"), relief=FLAT,
               cursor="hand2", pady=5, anchor=W, padx=8)
    b.pack(side=LEFT, fill=X, expand=True)
    if key:
        Label(row, text=key, bg=C_PANEL, fg="#555555",
              font=("Consolas", 8)).pack(side=RIGHT, padx=(4, 0))
    return b


Label(right_sidebar, text="YOLO  GENDER  CROPPER",
      bg=C_PANEL, fg=C_INFO, font=("Consolas", 10, "bold")).pack(pady=(14, 4))

# Stats panel
sidebar_info = Label(
    right_sidebar, text="", bg="#131313", fg=C_INFO,
    font=("Consolas", 9), justify=LEFT, anchor="nw",
    padx=10, pady=8,
)
sidebar_info.pack(fill=X, padx=10, pady=4)

# Prefetch progress
_section(right_sidebar, "PREFETCH")
pf_row = Frame(right_sidebar, bg=C_PANEL)
pf_row.pack(fill=X, padx=10, pady=2)
Label(pf_row, text="Cache:", bg=C_PANEL, fg="#666666",
      font=("Segoe UI", 8)).pack(side=LEFT)
prefetch_bar = ttk.Progressbar(pf_row, length=170, mode="determinate")
prefetch_bar.pack(side=LEFT, padx=6)

# Navigation
_section(left_sidebar, "NAVIGATION")
_btn(left_sidebar, "◀  Prev Image",          prev_image,            "#1a237e", "←")
_btn(left_sidebar, "▶  Next Image",          next_image,            "#1a237e", "→")
_btn(left_sidebar, "⏭  Next Unprocessed",    goto_next_unprocessed, "#283593", "N")

# Selection
_section(left_sidebar, "PERSON SELECT")
_btn(left_sidebar, "▲  Prev Person",         prev_person,           "#4a148c", "↑")
_btn(left_sidebar, "▼  Next Person",         next_person,           "#6a1b9a", "↓")

# Zoom & Review
_section(left_sidebar, "VIEW & ZOOM")
_btn(left_sidebar, "＋ Zoom In",             zoom_in,               "#33691e", "Ctrl++")
_btn(left_sidebar, "－ Zoom Out",            zoom_out,              "#33691e", "Ctrl+-")
_btn(left_sidebar, "Reset Zoom",            zoom_reset,            "#455a64", "Ctrl+0")
_btn(left_sidebar, "🚫 Mark Unusable",      mark_current_unusable, "#d84315", "U")

# Editing
_section(right_sidebar, "EDITING")
_btn(right_sidebar, "♀/♂  Toggle Gender",     toggle_gender,         "#00695c", "G")
_btn(right_sidebar, "🔄  Reclassify w/ AI",   reclassify_selected,   "#006064", "R")
_btn(right_sidebar, "✖  Delete Box",          delete_person,         "#b71c1c", "Del")
_btn(right_sidebar, "↩  Undo",               undo,                  "#37474f", "Ctrl+Z")
_btn(right_sidebar, "↪  Redo",               redo,                  "#37474f", "Ctrl+Y")

# Save
_section(right_sidebar, "SAVE")
_btn(right_sidebar, "💾  Save Selected",      accept_selected,       "#1b5e20", "S")
_btn(right_sidebar, "✔  Save ALL + Next",    accept_all,            "#2e7d32", "Space")

# ── Status bar ────────────────────────────────────────────────────────────────
status_var = StringVar(value="  Ready")
status_bar = Label(root, textvariable=status_var,
                   bg="#181818", fg="#aaaaaa",
                   anchor=W, font=("Segoe UI", 9), padx=12, pady=4)
status_bar.pack(fill=X, side=BOTTOM)


def set_status(msg: str, color: str = "#aaaaaa") -> None:
    status_var.set(f"  {msg}")
    status_bar.config(fg=color)


# ──────────────────────────────────────────────────────────────────────────────
# KEYBOARD SHORTCUTS
# ──────────────────────────────────────────────────────────────────────────────
root.bind("<Right>",    next_image)
root.bind("<Left>",     prev_image)
root.bind("<Up>",       prev_person)
root.bind("<Down>",     next_person)
root.bind("<g>",        toggle_gender)
root.bind("<r>",        reclassify_selected)
root.bind("<n>",        goto_next_unprocessed)
root.bind("<u>",        mark_current_unusable)
root.bind("<s>",        accept_selected)
root.bind("<Delete>",   delete_person)
root.bind("<BackSpace>", delete_person)
root.bind("<space>",    accept_all)
root.bind("<Control-plus>",  zoom_in)
root.bind("<Control-minus>", zoom_out)
root.bind("<Control-0>",     zoom_reset)
root.bind("<Control-z>", undo)
root.bind("<Control-y>", redo)
root.bind("<Control-Z>", undo)   # Shift+Ctrl+Z on some layouts

# ──────────────────────────────────────────────────────────────────────────────
# STARTUP & SHUTDOWN
# ──────────────────────────────────────────────────────────────────────────────
def on_close() -> None:
    if messagebox.askokcancel("Quit", "Exit YOLO Gender Cropper?"):
        stop_event.set()
        root.destroy()

root.protocol("WM_DELETE_WINDOW", on_close)

worker = threading.Thread(target=inference_worker, daemon=True, name="InferenceWorker")
worker.start()

set_status("Starting up…", C_INFO)
show_image()
root.mainloop()
