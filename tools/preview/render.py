"""Turn a folder of finished photos into a self-contained client gallery, ready to host.

  python tools/preview/render.py "path/to/shoot" --client "Display Name"

Every photo goes in, in shooting order, in three sizes: full size for downloading,
web size for viewing, and a thumbnail, plus a zip of all the full-size photos.
Metadata such as GPS location is stripped from all of them, and the page contains
no folder paths from this PC.
"""
import argparse
import json
import os
import re
import shutil
import sys
import zipfile
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from pathlib import Path

from PIL import Image, ImageOps

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from images import EXTENSIONS, capture_time, load_rgb  # noqa: E402

FULL_QUALITY = 95
WEB_EDGE, WEB_QUALITY = 1600, 82
THUMB_EDGE, THUMB_QUALITY = 720, 78
EXPIRY_DAYS = 30
ZIP_NAME = "all-photos.zip"
OUTPUT_FOLDERS = ("full", "img", "thumb")
TEMPLATE = HERE / "templates" / "viewer.html"
MANIFEST_SLOT = "/*MANIFEST*/null"
# Kept out of OneDrive and Google Drive so gigabytes of copies don't sync to the cloud.
WORK_ROOT = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "RealekGalleries"


def list_photos(folder):
    """Every JPEG directly in the folder, in shooting order. Files with no capture time go last."""
    paths = [p for p in Path(folder).iterdir() if p.is_file() and p.suffix.lower() in EXTENSIONS]
    timed = [(capture_time(p) or "9999", p.name, p) for p in paths]
    return [{"path": str(p), "name": name} for _, name, p in sorted(timed, key=lambda t: t[:2])]


def save_clean(im, dest, **options):
    """Saves with nothing carried over but the color profile, which keeps colors accurate."""
    icc = im.info.get("icc_profile")
    im.info = {}
    if icc:
        options["icc_profile"] = icc
    im.save(dest, "JPEG", optimize=True, progressive=True, **options)
    return im.size


def save_full(path, dest):
    with Image.open(path) as source:
        im = ImageOps.exif_transpose(source).convert("RGB")
    return save_clean(im, dest, quality=FULL_QUALITY, subsampling=0)


def render_photo(args):
    number, photo, out = args
    file_name = f"{number:03d}.jpg"
    try:
        save_full(photo["path"], out / "full" / file_name)
        width, height = save_clean(load_rgb(photo["path"], WEB_EDGE), out / "img" / file_name, quality=WEB_QUALITY)
        save_clean(load_rgb(photo["path"], THUMB_EDGE), out / "thumb" / file_name, quality=THUMB_QUALITY)
    except OSError as exc:  # for example, a file that didn't finish copying
        for folder in OUTPUT_FOLDERS:
            (out / folder / file_name).unlink(missing_ok=True)
        return {"failed": photo["name"], "reason": str(exc)}
    return {"src": f"img/{file_name}", "thumb": f"thumb/{file_name}", "full": f"full/{file_name}",
            "w": width, "h": height, "name": photo["name"]}


def render_photos(photos, out):
    """Makes every size of every photo, replacing any earlier build. Returns (rendered, failed)."""
    out = Path(out)
    for folder in OUTPUT_FOLDERS:
        shutil.rmtree(out / folder, ignore_errors=True)
        (out / folder).mkdir(parents=True)
    (out / ZIP_NAME).unlink(missing_ok=True)
    with ThreadPoolExecutor(max_workers=os.cpu_count() or 4) as pool:
        results = list(pool.map(render_photo, [(n, photo, out) for n, photo in enumerate(photos, 1)]))
    return [r for r in results if "failed" not in r], [r for r in results if "failed" in r]


def build_zip(out, photos):
    """Stored without compression: JPEGs don't shrink, and this is far faster."""
    with zipfile.ZipFile(out / ZIP_NAME, "w", zipfile.ZIP_STORED) as archive:
        for photo in photos:
            archive.write(out / photo["full"], arcname=photo["name"])
    return (out / ZIP_NAME).stat().st_size


def size_label(size):
    return f"{size / 1_000_000_000:.1f} GB" if size >= 1_000_000_000 else f"{max(1, round(size / 1_000_000))} MB"


def expiry_label(expires):
    return f"{expires:%B} {expires.day}, {expires.year}"


def finish_gallery(photos, out, client, expires, cover=0, feedback=None):
    """Writes the zip and page for exactly these photos and returns the page's data."""
    out = Path(out)
    if not photos:
        raise ValueError("A gallery needs at least one photo.")
    safe_client = re.sub(r"[^\w-]+", "-", client).strip("-") or "Gallery"
    manifest = {
        "client": client,
        "expires": expiry_label(expires),
        "cover": cover if 0 <= cover < len(photos) else 0,
        "zip": {"src": ZIP_NAME, "name": f"{safe_client}.zip", "size": size_label(build_zip(out, photos))},
        "photos": photos,
        "feedback": feedback,
    }
    # Escaping "<" keeps a client name from ever closing the script tag.
    data = json.dumps(manifest, ensure_ascii=False).replace("<", "\\u003c")
    page = TEMPLATE.read_text(encoding="utf-8")
    if page.count(MANIFEST_SLOT) != 1:
        raise ValueError(f"{TEMPLATE} must contain {MANIFEST_SLOT} exactly once")
    (out / "index.html").write_text(page.replace(MANIFEST_SLOT, data), encoding="utf-8")
    return manifest


def render_gallery(photos, out, client, expires, cover=0, feedback=None):
    """Builds a whole gallery. Returns the photos it couldn't read."""
    rendered, failed = render_photos(photos, out)
    if not rendered:
        raise ValueError("None of these photos could be read.")
    finish_gallery(rendered, out, client, expires, cover, feedback)
    return failed


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("shoot", type=Path, help="folder of finished JPEGs")
    parser.add_argument("--client", help="name shown to the client (default: the folder's name)")
    args = parser.parse_args()
    if not args.shoot.is_dir():
        parser.error(f"not a folder: {args.shoot}")

    shoot = args.shoot.resolve().name
    photos = list_photos(args.shoot)
    if not photos:
        parser.error(f"no JPEGs found in {args.shoot}")
    out = WORK_ROOT / "test-builds" / (re.sub(r"[^\w-]+", "-", shoot).strip("-").lower() or "gallery")
    print(f"Building a gallery of {len(photos)} photos")
    failed = render_gallery(photos, out, args.client or shoot, date.today() + timedelta(days=EXPIRY_DAYS))

    size = sum(f.stat().st_size for f in out.rglob("*") if f.is_file())
    print(f"Done: {len(photos) - len(failed)} photos, {size_label(size)} in total, in {out}")
    for item in failed:
        print(f"LEFT OUT, couldn't read {item['failed']}: {item['reason']}")
    print(f'To view it: python -m http.server 8123 --bind 127.0.0.1 --directory "{out}"')
    print("Then open http://127.0.0.1:8123/")


if __name__ == "__main__":
    main()
