"""Local, offline first pass: drop technical failures and thin out bursts.

Nothing leaves this PC here, and originals are only ever read. The thresholds are
deliberately cautious: a weak frame that survives costs a little AI time, while a
good frame removed here is lost for good.
"""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from statistics import median

import cv2
import numpy as np
from PIL import Image, ImageOps

EXTENSIONS = {".jpg", ".jpeg"}
ANALYSIS_EDGE = 1024
EXIF_IFD = 0x8769
EXIF_DATETIME_ORIGINAL = 36867
EXIF_DATETIME = 306

# Calibrated on 306 kept frames, including 56 portfolio picks. The softest of them
# peaks at 126, and ring-detail and soft black-and-white picks fall as low as 11% of
# their shoot's median, so sharpness alone can't judge focus. These limits catch only
# frames with no sharp area at all. Claude's `missed_focus` flag handles the rest.
NO_DETAIL_PEAK = 100
MIN_PHOTOS_FOR_BLUR_CHECK = 8  # a shoot's median means little below this
BLUR_RATIO = 0.05              # also under this fraction of the shoot's median
BURST_MAX_HASH_DISTANCE = 10   # out of 64 bits
BURST_MAX_GAP_SECONDS = 20
BURST_KEEP = 3


@dataclass
class Photo:
    path: str
    name: str
    taken: str | None = None
    sharpness: float = 0.0
    brightness: float = 0.0
    contrast: float = 0.0
    dhash: int = 0
    reject_reason: str | None = None

    def to_dict(self):
        data = asdict(self)
        del data["dhash"]
        return data


def load_rgb(path, edge):
    """Open a JPEG upright and in RGB, no larger than `edge` on its long side."""
    with Image.open(path) as im:
        im.draft("RGB", (edge, edge))  # decodes large JPEGs much faster
        upright = ImageOps.exif_transpose(im).convert("RGB")
    upright.thumbnail((edge, edge), Image.LANCZOS)
    return upright


def capture_time(path):
    try:
        with Image.open(path) as im:
            exif = im.getexif()
            raw = exif.get_ifd(EXIF_IFD).get(EXIF_DATETIME_ORIGINAL) or exif.get(EXIF_DATETIME)
        return datetime.strptime(str(raw).strip(), "%Y:%m:%d %H:%M:%S").isoformat() if raw else None
    except (OSError, ValueError):
        return None


def peak_sharpness(gray):
    """Sharpness of the sharpest region, so soft backgrounds aren't penalised."""
    laplacian = cv2.Laplacian(gray, cv2.CV_64F)
    h, w = laplacian.shape
    tiles = [
        laplacian[h * r // 8:h * (r + 1) // 8, w * c // 8:w * (c + 1) // 8].var()
        for r in range(8) for c in range(8)
    ]
    return float(max(tiles))


def difference_hash(gray):
    small = cv2.resize(gray, (9, 8), interpolation=cv2.INTER_AREA)
    bits = (small[:, 1:] > small[:, :-1]).flatten()
    return int("".join("1" if b else "0" for b in bits), 2)


def analyse(path):
    photo = Photo(path=str(path), name=path.name, taken=capture_time(path))
    try:
        gray = np.asarray(load_rgb(path, ANALYSIS_EDGE).convert("L"))
    except OSError as exc:
        photo.reject_reason = f"unreadable file ({exc})"
        return photo
    photo.sharpness = peak_sharpness(gray)
    photo.brightness = float(gray.mean())
    photo.contrast = float(gray.std())
    photo.dhash = difference_hash(gray)

    # Only true misfires: dark and bright portraits still have a sharp area somewhere.
    if photo.sharpness < NO_DETAIL_PEAK:
        if (gray <= 8).mean() > 0.92:
            photo.reject_reason = "almost entirely black"
        elif (gray >= 250).mean() > 0.92:
            photo.reject_reason = "almost entirely white"
        elif photo.contrast < 6:
            photo.reject_reason = "misfire (almost no detail)"
    return photo


def seconds_apart(a, b):
    if not a.taken or not b.taken:
        return None
    return abs((datetime.fromisoformat(a.taken) - datetime.fromisoformat(b.taken)).total_seconds())


def is_same_burst(a, b):
    if (a.dhash ^ b.dhash).bit_count() > BURST_MAX_HASH_DISTANCE:
        return False
    gap = seconds_apart(a, b)
    return gap is None or gap <= BURST_MAX_GAP_SECONDS


def thin_bursts(photos):
    """Keep the sharpest few of each run of near-identical consecutive frames."""
    bursts, current = [], []
    for photo in photos:
        if current and not is_same_burst(current[-1], photo):
            bursts.append(current)
            current = []
        current.append(photo)
    if current:
        bursts.append(current)
    for burst in bursts:
        for extra in sorted(burst, key=lambda p: p.sharpness, reverse=True)[BURST_KEEP:]:
            extra.reject_reason = "near-duplicate of a sharper frame in the same burst"


def cull(folder):
    """Returns (candidates, rejected) in shooting order."""
    paths = [p for p in Path(folder).iterdir() if p.is_file() and p.suffix.lower() in EXTENSIONS]
    with ThreadPoolExecutor(max_workers=8) as pool:
        photos = list(pool.map(analyse, paths))
    photos.sort(key=lambda p: (p.taken or "9999", p.name))

    usable = [p for p in photos if not p.reject_reason]
    if len(usable) >= MIN_PHOTOS_FOR_BLUR_CHECK:
        cutoff = median(p.sharpness for p in usable) * BLUR_RATIO
        for photo in usable:
            if photo.sharpness < min(cutoff, NO_DETAIL_PEAK):
                photo.reject_reason = "blurry compared with the rest of this shoot"
    thin_bursts([p for p in usable if not p.reject_reason])
    return [p for p in photos if not p.reject_reason], [p for p in photos if p.reject_reason]
