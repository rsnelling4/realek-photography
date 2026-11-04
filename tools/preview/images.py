"""Reading photos: which files count, when they were taken, and opening them upright."""
from datetime import datetime

from PIL import Image, ImageOps

EXTENSIONS = {".jpg", ".jpeg"}
EXIF_IFD = 0x8769
EXIF_DATETIME_ORIGINAL = 36867
EXIF_DATETIME = 306


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
