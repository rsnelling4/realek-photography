"""Runs offline: synthetic photos and a stand-in for Cloudflare. Nothing is sent anywhere."""
import json
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.request
import zipfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import publish as r2  # noqa: E402
import shoots as flow  # noqa: E402
import watcher  # noqa: E402
from review_server import App, start_server  # noqa: E402

SETTINGS = r2.Settings("a" * 32, "id", "secret", "bucket", "https://galleries.test")
TOKEN = "abcdefghijklmnopqrstuvwxyz"


def photo(path, seed=1):
    rng = np.random.default_rng(seed)
    pixels = rng.integers(0, 255, (60, 80, 3), dtype=np.uint8)
    Image.fromarray(pixels).resize((800, 600), Image.NEAREST).save(path, "JPEG", quality=85)


class FakeS3:
    """Keeps uploads in memory, in the order they arrived."""

    def __init__(self):
        self.objects, self.order, self.fail_on = {}, [], None

    def upload_file(self, path, bucket, key, ExtraArgs=None):
        if self.fail_on and self.fail_on in key:
            raise OSError("connection lost")
        self.objects[key] = {"body": Path(path).read_bytes(), "extra": ExtraArgs or {},
                             "LastModified": datetime.now(timezone.utc)}
        self.order.append(key)

    def put_object(self, Bucket, Key, Body, ContentType):
        self.objects[Key] = {"body": Body, "extra": {"ContentType": ContentType},
                             "LastModified": datetime.now(timezone.utc)}

    def get_paginator(self, _name):
        return self

    def paginate(self, Bucket, Prefix):
        return [{"Contents": [{"Key": k, "LastModified": v["LastModified"]}
                              for k, v in self.objects.items() if k.startswith(Prefix)]}]

    def delete_objects(self, Bucket, Delete):
        for item in Delete["Objects"]:
            self.objects.pop(item["Key"], None)


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.incoming = root / "Incoming"
        self.incoming.mkdir()
        self.store = flow.Store(root / "work")
        self.s3 = FakeS3()

    def add_shoot(self, name="Ann + Bo", count=3):
        folder = self.incoming / name
        folder.mkdir(exist_ok=True)
        for i in range(count):
            photo(folder / f"IMG_{i}.jpg", i)
        return folder

    def ready_shoot(self, name="Ann + Bo", count=3):
        self.add_shoot(name, count)
        flow.scan(self.store, self.incoming, now=0)
        self.assertEqual(flow.scan(self.store, self.incoming, now=1000), [name])
        return flow.build(self.store, name, self.incoming)

    def publish(self, name="Ann + Bo", client="Ann + Bo", removed=(), cover=None, live=True, today=date(2026, 11, 3)):
        return flow.publish_shoot(self.store, name, client, list(removed), cover, self.s3, SETTINGS, today=today,
                                  live_check=lambda url: live)


class ScanTests(Base):
    def test_waits_until_the_folder_stops_changing(self):
        folder = self.add_shoot(count=1)
        self.assertEqual(flow.scan(self.store, self.incoming, now=0), [])
        self.assertEqual(flow.scan(self.store, self.incoming, now=200), [])
        photo(folder / "IMG_late.jpg", 9)  # still copying
        self.assertEqual(flow.scan(self.store, self.incoming, now=299), [])
        self.assertEqual(flow.scan(self.store, self.incoming, now=400), [])
        self.assertEqual(flow.scan(self.store, self.incoming, now=700), ["Ann + Bo"])

    def test_empty_folder_and_stray_files_are_ignored(self):
        (self.incoming / "Empty").mkdir()
        (self.incoming / "stray.jpg").write_bytes(b"x")
        flow.scan(self.store, self.incoming, now=0)
        self.assertEqual(flow.scan(self.store, self.incoming, now=1000), [])
        self.assertEqual(self.store.shoots, {})

    def test_missing_drive_changes_nothing(self):
        self.ready_shoot()
        self.assertEqual(flow.scan(self.store, self.incoming / "not-mounted", now=2000), [])
        self.assertEqual(self.store.shoots["Ann + Bo"]["status"], "ready")

    def test_adding_photos_before_approval_rebuilds_and_keeps_choices(self):
        record = self.ready_shoot()
        self.store.update("Ann + Bo", removed=["IMG_0.jpg"], cover="IMG_1.jpg")
        photo(self.incoming / "Ann + Bo" / "IMG_new.jpg", 7)
        flow.scan(self.store, self.incoming, now=2000)
        self.assertEqual(self.store.shoots["Ann + Bo"]["status"], "waiting")
        self.assertEqual(flow.scan(self.store, self.incoming, now=2500), ["Ann + Bo"])
        record = flow.build(self.store, "Ann + Bo", self.incoming)
        self.assertEqual(len(record["photos"]), 4)
        self.assertEqual(record["removed"], ["IMG_0.jpg"])
        self.assertEqual(record["cover"], "IMG_1.jpg")

    def test_published_shoot_is_not_rebuilt_but_flags_a_change(self):
        self.ready_shoot()
        self.publish()
        photo(self.incoming / "Ann + Bo" / "IMG_new.jpg", 7)
        self.assertEqual(flow.scan(self.store, self.incoming, now=5000), [])
        self.assertEqual(flow.scan(self.store, self.incoming, now=9000), [])
        record = self.store.shoots["Ann + Bo"]
        self.assertEqual(record["status"], "published")
        self.assertTrue(record["changed_after_publish"])

    def test_folder_removed_before_approval_is_dropped_but_published_stays(self):
        self.ready_shoot("A", 1)
        self.ready_shoot("B", 1)
        self.publish("B", "B")
        for name in ("A", "B"):
            for f in (self.incoming / name).iterdir():
                f.unlink()
            (self.incoming / name).rmdir()
        flow.scan(self.store, self.incoming, now=9000)
        self.assertNotIn("A", self.store.shoots)
        self.assertEqual(self.store.shoots["B"]["status"], "published")

    def test_restart_recovers_interrupted_work(self):
        self.ready_shoot("A", 1)
        self.ready_shoot("B", 1)
        self.store.update("A", status="building")
        self.store.update("B", status="publishing")
        reopened = flow.Store(self.store.root)
        flow.recover(reopened)
        self.assertEqual(reopened.shoots["A"]["status"], "waiting")
        self.assertEqual(reopened.shoots["B"]["status"], "ready")
        self.assertIn("interrupted", reopened.shoots["B"]["error"])

    def test_similar_folder_names_get_separate_work_folders(self):
        self.assertNotEqual(flow.make_slug("A + B"), flow.make_slug("A B"))


class PublishTests(Base):
    def test_nothing_is_uploaded_before_approval(self):
        self.ready_shoot()
        self.assertEqual(self.s3.objects, {})

    def test_publish_uploads_everything_with_the_page_last(self):
        self.ready_shoot()
        record = self.publish()
        self.assertEqual(record["status"], "published")
        prefix = f"p/{record['token']}/"
        self.assertEqual(self.s3.order[-1], f"{prefix}index.html")
        keys = set(self.s3.objects)
        for folder in ("full", "img", "thumb"):
            for n in ("001", "002", "003"):
                self.assertIn(f"{prefix}{folder}/{n}.jpg", keys)
        self.assertIn(f"{prefix}all-photos.zip", keys)
        self.assertIn("robots.txt", keys)
        self.assertEqual(record["url"], f"https://galleries.test/{prefix}index.html")
        self.assertIn(record["url"], record["message"])

    def test_token_is_long_and_differs_per_gallery(self):
        self.ready_shoot("A", 1)
        self.ready_shoot("B", 1)
        a, b = self.publish("A", "A")["token"], self.publish("B", "B")["token"]
        self.assertNotEqual(a, b)
        self.assertGreaterEqual(len(a), 30)

    def test_removed_photos_never_reach_the_cloud(self):
        self.ready_shoot()
        record = self.publish(removed=["IMG_1.jpg"])
        prefix = f"p/{record['token']}/"
        self.assertEqual(record["count"], 2)
        for folder in ("full", "img", "thumb"):
            self.assertNotIn(f"{prefix}{folder}/002.jpg", self.s3.objects)
        page = self.s3.objects[f"{prefix}index.html"]["body"].decode()
        self.assertNotIn("IMG_1.jpg", page)
        zip_path = self.store.root / "check.zip"
        zip_path.write_bytes(self.s3.objects[f"{prefix}all-photos.zip"]["body"])
        with zipfile.ZipFile(zip_path) as archive:
            self.assertEqual(sorted(archive.namelist()), ["IMG_0.jpg", "IMG_2.jpg"])

    def test_cover_and_name_and_dates_reach_the_page(self):
        self.ready_shoot()
        record = self.publish(client="Ann & Bo Smith", cover="IMG_2.jpg", today=date(2026, 11, 3))
        page = self.s3.objects[f"p/{record['token']}/index.html"]["body"].decode()
        self.assertIn('"cover": 2', page)
        self.assertIn("Ann & Bo Smith", page)
        self.assertIn("December 3, 2026", page)  # counted from approval
        self.assertEqual(record["expires"], "2026-12-03")

    def test_cover_index_accounts_for_removed_photos(self):
        self.ready_shoot()
        record = self.publish(removed=["IMG_0.jpg"], cover="IMG_2.jpg")
        self.assertIn('"cover": 1', self.s3.objects[f"p/{record['token']}/index.html"]["body"].decode())

    def test_removing_the_chosen_cover_falls_back_to_first(self):
        self.ready_shoot()
        record = self.publish(removed=["IMG_1.jpg"], cover="IMG_1.jpg")
        self.assertIn('"cover": 0', self.s3.objects[f"p/{record['token']}/index.html"]["body"].decode())

    def test_failed_upload_stays_ready_with_no_page_and_can_retry(self):
        record = self.ready_shoot()
        self.s3.fail_on = "all-photos.zip"
        record = self.publish()
        self.assertEqual(record["status"], "ready")
        self.assertIn("connection lost", record["error"])
        self.assertFalse([k for k in self.s3.objects if k.endswith("index.html")])
        token = record["token"]
        self.s3.fail_on = None
        record = self.publish()
        self.assertEqual(record["status"], "published")
        self.assertEqual(record["token"], token)  # retried in place, leaving no stray copy

    def test_gallery_that_does_not_open_is_not_marked_live(self):
        self.ready_shoot()
        record = self.publish(live=False)
        self.assertEqual(record["status"], "ready")
        self.assertIn("didn't open", record["error"])

    def test_cannot_publish_nothing_or_without_a_name_or_twice(self):
        self.ready_shoot(count=2)
        with self.assertRaises(ValueError):
            self.publish(removed=["IMG_0.jpg", "IMG_1.jpg"])
        with self.assertRaises(ValueError):
            self.publish(client="   ")
        self.publish()
        with self.assertRaises(ValueError):
            self.publish()

    def test_local_copies_are_cleared_after_publishing(self):
        record = self.ready_shoot()
        work = self.store.work_dir(record)
        self.assertTrue(work.exists())
        self.publish()
        self.assertFalse(work.exists())

    def test_downloads_carry_their_file_names(self):
        self.ready_shoot()
        record = self.publish()
        extra = self.s3.objects[f"p/{record['token']}/full/001.jpg"]["extra"]
        self.assertIn("IMG_", extra["ContentDisposition"])
        self.assertEqual(extra["ContentType"], "image/jpeg")
        self.assertEqual(r2.attachment('é"x.jpg').encode("ascii").decode(), r2.attachment('é"x.jpg'))


class TakeDownTests(Base):
    def test_only_that_gallery_is_deleted(self):
        self.ready_shoot("A", 1)
        self.ready_shoot("B", 1)
        a, b = self.publish("A", "A"), self.publish("B", "B")
        record = flow.take_down_shoot(self.store, "A", self.s3, SETTINGS)
        self.assertEqual(record["status"], "taken_down")
        self.assertIsNone(record["url"])
        self.assertFalse([k for k in self.s3.objects if k.startswith(f"p/{a['token']}/")])
        self.assertTrue([k for k in self.s3.objects if k.startswith(f"p/{b['token']}/")])

    def test_empty_or_odd_token_cannot_delete_everything(self):
        self.s3.objects["p/other/index.html"] = {"body": b"", "LastModified": datetime.now(timezone.utc)}
        for bad in ("", None, "..", "short", "a/b/c/d/e/f/g/h/i/j/k/l"):
            with self.assertRaises(ValueError):
                r2.take_down(self.s3, SETTINGS, bad)
        self.assertIn("p/other/index.html", self.s3.objects)

    def test_expired_files_are_deleted_and_recent_ones_kept(self):
        now = datetime(2026, 12, 31, tzinfo=timezone.utc)
        self.s3.objects["p/old/full/1.jpg"] = {"LastModified": now - timedelta(days=32)}
        self.s3.objects["p/new/full/1.jpg"] = {"LastModified": now - timedelta(days=30)}
        self.s3.objects["robots.txt"] = {"LastModified": now - timedelta(days=90)}
        self.assertEqual(r2.delete_expired(self.s3, SETTINGS, now=now), 1)
        self.assertEqual(set(self.s3.objects), {"p/new/full/1.jpg", "robots.txt"})

    def test_expired_records_lose_their_message(self):
        self.ready_shoot()
        self.publish(today=date(2026, 11, 3))
        flow.mark_expired(self.store, today=date(2026, 12, 3))
        self.assertEqual(self.store.shoots["Ann + Bo"]["status"], "published")
        flow.mark_expired(self.store, today=date(2026, 12, 4))
        self.assertEqual(self.store.shoots["Ann + Bo"]["status"], "expired")


class NotifyTests(unittest.TestCase):
    def test_opens_the_page_when_windows_notifications_are_off(self):
        with mock.patch.object(watcher, "windows_notifications_on", return_value=False), \
                mock.patch.object(watcher.webbrowser, "open", return_value=True) as opened:
            watcher.notify("Gallery ready", "Ann: 3 photos")
        opened.assert_called_once_with(watcher.PAGE_URL)

    def test_sends_a_notification_and_opens_nothing_when_they_are_on(self):
        with mock.patch.object(watcher, "windows_notifications_on", return_value=True), \
                mock.patch.object(watcher.webbrowser, "open") as opened, \
                mock.patch("winotify.Notification") as toast:
            watcher.notify("Gallery ready", "Ann: 3 photos")
        toast.return_value.show.assert_called_once()
        opened.assert_not_called()

    def test_a_failure_never_stops_the_work(self):
        with mock.patch.object(watcher, "windows_notifications_on", side_effect=RuntimeError("boom")):
            watcher.notify("Gallery ready", "Ann: 3 photos")


class SettingsTests(unittest.TestCase):
    def test_account_id_accepted_alone_or_as_the_full_address(self):
        env = {k: "x" for k in r2.REQUIRED_SETTINGS}
        for value in ("a" * 32, f"https://{'a' * 32}.r2.cloudflarestorage.com"):
            env["R2_ACCOUNT_ID"] = value
            self.assertEqual(r2.load_settings(env).account_id, "a" * 32)

    def test_missing_settings_are_named(self):
        with self.assertRaisesRegex(ValueError, "R2_BUCKET"):
            r2.load_settings({"R2_ACCOUNT_ID": "a" * 32})


class ServerTests(Base):
    def setUp(self):
        super().setUp()
        self.server = start_server(App(self.store, lambda: (self.s3, SETTINGS)), port=0)
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)

    def start_on_known_port(self):
        import socket
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
        server = start_server(App(self.store, lambda: (self.s3, SETTINGS)), port=port)
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        return port

    def call(self, port, path, body=None, headers=None):
        data = None if body is None else json.dumps(body).encode()
        request = urllib.request.Request(f"http://127.0.0.1:{port}{path}", data=data, headers=headers or {})
        try:
            with urllib.request.urlopen(request, timeout=10) as r:
                return r.status, r.read()
        except urllib.error.HTTPError as e:
            return e.code, e.read()

    def good_post(self, port):
        return {"Origin": f"http://127.0.0.1:{port}", "Content-Type": "application/json"}

    def test_page_and_data_load(self):
        port = self.start_on_known_port()
        self.ready_shoot()
        self.assertEqual(self.call(port, "/")[0], 200)
        status, body = self.call(port, "/api/shoots")
        self.assertEqual(status, 200)
        self.assertIn("Ann + Bo", json.loads(body)["shoots"])

    def test_thumbnail_is_served_and_other_paths_are_not(self):
        port = self.start_on_known_port()
        record = self.ready_shoot()
        self.assertEqual(self.call(port, f"/work/{record['slug']}/thumb/001.jpg")[0], 200)
        for path in (f"/work/{record['slug']}/full/001.jpg", "/work/../shoots.json",
                     f"/work/{record['slug']}/thumb/../../../shoots.json", "/shoots.json", "/work/x/thumb/999.jpg"):
            self.assertEqual(self.call(port, path)[0], 404, path)

    def test_other_websites_cannot_publish_or_take_down(self):
        port = self.start_on_known_port()
        self.ready_shoot()
        body = {"name": "Ann + Bo", "client": "x"}
        for headers in ({"Origin": "https://evil.example", "Content-Type": "application/json"},
                        {"Content-Type": "application/json"},
                        {"Origin": f"http://127.0.0.1:{port}", "Content-Type": "text/plain"},
                        {"Origin": "null", "Content-Type": "application/json"}):
            self.assertEqual(self.call(port, "/api/publish", body, headers)[0], 403, headers)
        self.assertEqual(self.s3.objects, {})

    def test_requests_with_another_host_name_are_refused(self):
        port = self.start_on_known_port()
        self.assertEqual(self.call(port, "/api/shoots", headers={"Host": "evil.example"})[0], 403)

    def test_publish_and_take_down_through_the_page(self):
        port = self.start_on_known_port()
        self.ready_shoot()
        with mock.patch.object(r2, "check_live", return_value=True):
            status, _ = self.call(port, "/api/publish", {"name": "Ann + Bo", "client": "Ann + Bo"}, self.good_post(port))
            self.assertEqual(status, 200)
            deadline = time.time() + 20
            while self.store.shoots["Ann + Bo"]["status"] != "published" and time.time() < deadline:
                time.sleep(0.05)
        record = self.store.shoots["Ann + Bo"]
        self.assertEqual(record["status"], "published", record.get("error"))
        prefix = f"p/{record['token']}/"
        self.assertIn(f"{prefix}index.html", self.s3.objects)

        status, _ = self.call(port, "/api/take-down", {"name": "Ann + Bo"}, self.good_post(port))
        self.assertEqual(status, 200)
        self.assertEqual(self.store.shoots["Ann + Bo"]["status"], "taken_down")
        self.assertFalse([k for k in self.s3.objects if k.startswith(prefix)])

    def test_bad_requests_get_clear_errors(self):
        port = self.start_on_known_port()
        status, body = self.call(port, "/api/publish", {"name": "Nobody", "client": "x"}, self.good_post(port))
        self.assertEqual(status, 400)
        self.assertIn("no longer exists", json.loads(body)["error"])


if __name__ == "__main__":
    unittest.main()
