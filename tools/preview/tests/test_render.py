"""Runs offline on synthetic photos."""
import io
import json
import re
import sys
import tempfile
import unittest
import zipfile
from datetime import date
from pathlib import Path

import numpy as np
from PIL import Image, ImageCms

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from render import ZIP_NAME, list_photos, render_gallery, size_label  # noqa: E402

EXIF_ORIENTATION = 0x0112
EXIF_MAKE = 0x010F
EXIF_IFD = 0x8769
DATETIME_ORIGINAL = 36867
GPS_IFD = 0x8825
FOLDERS = ("full", "img", "thumb")


def photo(path, size, orientation=1, taken=None, **save_options):
    rng = np.random.default_rng(1)
    pixels = rng.integers(0, 255, (size[1] // 20, size[0] // 20, 3), dtype=np.uint8)
    im = Image.fromarray(pixels).resize(size, Image.NEAREST)
    exif = Image.Exif()
    exif[EXIF_MAKE] = "Canon"
    exif[EXIF_ORIENTATION] = orientation
    exif.get_ifd(GPS_IFD)[1] = "N"
    if taken:
        exif.get_ifd(EXIF_IFD)[DATETIME_ORIGINAL] = taken
    im.save(path, "JPEG", quality=90, exif=exif, **save_options)


class RenderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="SecretFolder")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.out = self.root / "out"
        self.source = self.root / "shoot"
        self.source.mkdir()
        photo(self.source / "IMG_1.jpg", (3000, 2000))
        photo(self.source / "IMG_2.jpg", (3000, 2000), orientation=6)  # stored sideways
        self.photos = [
            {"path": str(self.source / "IMG_1.jpg"), "name": "IMG_1.jpg"},
            {"path": str(self.source / "IMG_2.jpg"), "name": "IMG_2.jpg"},
        ]

    def render(self, photos=None, client="Ann + Bo", cover=0):
        return render_gallery(photos or self.photos, self.out, client, date(2027, 3, 5), cover)

    def html(self):
        return (self.out / "index.html").read_text(encoding="utf-8")

    def manifest(self):
        return json.loads(re.search(r"const data = (\{.*?\});\n", self.html(), re.S).group(1))

    def test_full_size_keeps_resolution_and_others_are_smaller(self):
        self.render()
        expected = {"full": (3000, 2000), "img": (1600, 1067), "thumb": (720, 480)}
        for folder, size in expected.items():
            with Image.open(self.out / folder / "001.jpg") as im:
                self.assertEqual(im.size, size)
            with Image.open(self.out / folder / "002.jpg") as im:
                self.assertEqual(im.size, size[::-1])  # rotated upright

    def test_all_metadata_is_stripped_from_every_size(self):
        xmp = b'<x:xmpmeta xmlns:x="adobe:ns:meta/"><GPSLatitude>38.2</GPSLatitude></x:xmpmeta>'
        photo(self.source / "tagged.jpg", (3000, 2000), xmp=xmp, comment=b"secret comment")
        self.render([{"path": str(self.source / "tagged.jpg"), "name": "tagged.jpg"}])
        for folder in FOLDERS:
            raw = (self.out / folder / "001.jpg").read_bytes()
            for marker in (b"GPSLatitude", b"Canon", b"secret comment", b"Exif"):
                self.assertNotIn(marker, raw, f"{marker} found in {folder}")
            with Image.open(self.out / folder / "001.jpg") as im:
                self.assertEqual(len(im.getexif()), 0)

    def test_color_profile_is_kept(self):
        icc = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
        photo(self.source / "icc.jpg", (3000, 2000), icc_profile=icc)
        self.render([{"path": str(self.source / "icc.jpg"), "name": "icc.jpg"}])
        for folder in FOLDERS:
            with Image.open(self.out / folder / "001.jpg") as im:
                self.assertEqual(im.info.get("icc_profile"), icc)

    def test_nothing_is_drawn_on_the_photos(self):
        Image.new("RGB", (3000, 2000), (120, 90, 60)).save(self.source / "flat.jpg", "JPEG", quality=95)
        self.render([{"path": str(self.source / "flat.jpg"), "name": "flat.jpg"}])
        for folder in FOLDERS:
            pixels = np.asarray(Image.open(self.out / folder / "001.jpg"), dtype=int)
            self.assertLess(np.ptp(pixels, axis=(0, 1)).max(), 8)

    def test_zip_holds_every_full_size_photo_under_its_own_name(self):
        self.render()
        with zipfile.ZipFile(self.out / ZIP_NAME) as archive:
            self.assertEqual(archive.namelist(), ["IMG_1.jpg", "IMG_2.jpg"])
            self.assertEqual(archive.read("IMG_2.jpg"), (self.out / "full" / "002.jpg").read_bytes())
            with Image.open(io.BytesIO(archive.read("IMG_1.jpg"))) as im:
                self.assertEqual(im.size, (3000, 2000))

    def test_page_data_is_complete_and_exposes_no_local_paths(self):
        self.render(cover=1)
        html, data = self.html(), self.manifest()
        self.assertEqual(data["client"], "Ann + Bo")
        self.assertEqual(data["expires"], "March 5, 2027")
        self.assertEqual(data["cover"], 1)
        self.assertEqual(data["zip"]["name"], "Ann-Bo.zip")
        self.assertEqual(data["zip"]["src"], ZIP_NAME)
        self.assertEqual([p["name"] for p in data["photos"]], ["IMG_1.jpg", "IMG_2.jpg"])
        self.assertEqual(data["photos"][1]["full"], "full/002.jpg")
        self.assertNotIn("SecretFolder", html)
        self.assertNotIn(str(self.root), html)
        self.assertNotIn("/*MANIFEST*/", html)
        self.assertIn('name="robots" content="noindex, nofollow"', html)

    def test_favorites_are_gone_from_the_page(self):
        self.render()
        html = self.html().lower()
        for word in ("favorite", "formspree", "heart", "localstorage"):
            self.assertNotIn(word, html)

    def test_hostile_client_name_cannot_break_out_of_the_script(self):
        evil = '</script><script>alert(1)</script>'
        self.render(client=evil)
        self.assertNotIn(evil, self.html())
        self.assertEqual(self.manifest()["client"], evil)

    def test_rerender_removes_photos_no_longer_in_the_gallery(self):
        self.render()
        self.render(self.photos[:1])
        for folder in FOLDERS:
            self.assertFalse((self.out / folder / "002.jpg").exists())
        with zipfile.ZipFile(self.out / ZIP_NAME) as archive:
            self.assertEqual(archive.namelist(), ["IMG_1.jpg"])

    def test_unreadable_photo_is_reported_and_left_out(self):
        (self.source / "broken.jpg").write_bytes(b"not a jpeg")
        failed = self.render([*self.photos, {"path": str(self.source / "broken.jpg"), "name": "broken.jpg"}])
        self.assertEqual([f["failed"] for f in failed], ["broken.jpg"])
        self.assertEqual(len(self.manifest()["photos"]), 2)
        with zipfile.ZipFile(self.out / ZIP_NAME) as archive:
            self.assertNotIn("broken.jpg", archive.namelist())

    def test_all_unreadable_stops_with_an_error(self):
        (self.source / "broken.jpg").write_bytes(b"not a jpeg")
        with self.assertRaises(ValueError):
            self.render([{"path": str(self.source / "broken.jpg"), "name": "broken.jpg"}])

    def test_originals_are_untouched(self):
        before = (self.source / "IMG_1.jpg").read_bytes()
        self.render()
        self.assertEqual((self.source / "IMG_1.jpg").read_bytes(), before)

    def test_list_photos_uses_shooting_order_and_jpegs_only(self):
        for f in self.source.iterdir():
            f.unlink()
        photo(self.source / "a_late.jpg", (100, 100), taken="2026:10:30 15:00:00")
        photo(self.source / "b_early.jpg", (100, 100), taken="2026:10:30 09:00:00")
        photo(self.source / "c_no_time.JPEG", (100, 100))
        (self.source / "notes.txt").write_text("x")
        (self.source / "raw.cr3").write_bytes(b"x")
        (self.source / "sub").mkdir()
        photo(self.source / "sub" / "nested.jpg", (100, 100))
        self.assertEqual([p["name"] for p in list_photos(self.source)], ["b_early.jpg", "a_late.jpg", "c_no_time.JPEG"])

    def test_size_label(self):
        self.assertEqual(size_label(3_400_000_000), "3.4 GB")
        self.assertEqual(size_label(12_300_000), "12 MB")


if __name__ == "__main__":
    unittest.main()
