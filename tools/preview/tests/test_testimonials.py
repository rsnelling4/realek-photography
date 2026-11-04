"""Runs offline: a stand-in plays the Worker, whose own tests are in tools/testimonials/test."""
import io
import json
import sys
import tempfile
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import publish as r2  # noqa: E402
import shoots as flow  # noqa: E402
import testimonials as t  # noqa: E402
import watcher  # noqa: E402
from review_server import App, start_server  # noqa: E402

SECRET = "test-secret"
GALLERY = "abcdefghijklmnopqrstuvwxyz"
WAITING = {"id": f"{GALLERY}:1", "gallery": GALLERY, "name": "Ann", "text": "Lovely.", "share": True,
           "submitted": "2026-11-04T00:00:00Z"}
PRIVATE = {**WAITING, "id": f"{GALLERY}:2", "share": False}


class FakeWorker:
    """Answers like the Worker does, and records what it was asked."""

    def __init__(self):
        self.pending, self.published, self.calls, self.fail = [dict(WAITING)], [], [], None

    def __call__(self, request, timeout=None):
        if self.fail:
            raise self.fail
        path = request.full_url.split("test", 1)[1]
        body = json.loads(request.data) if request.data else None
        self.calls.append((path, body, dict(request.header_items())))
        if path == "/admin/approve":
            self.published = [{**self.pending.pop(0), **body}]
        elif path == "/admin/delete":
            self.pending = [p for p in self.pending if p["id"] != body["id"]]
        elif path == "/admin/unpublish":
            self.pending, self.published = self.published, []
        answer = {"pending": self.pending, "published": self.published}
        return mock.MagicMock(__enter__=lambda s: io.BytesIO(json.dumps(answer).encode()), __exit__=lambda *a: None)


class Base(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.worker = FakeWorker()
        self.client = t.Testimonials("https://worker.test/", SECRET, self.root, opener=self.worker)


class KeyTests(unittest.TestCase):
    def test_matches_what_the_worker_checks(self):
        # The same pair is in tools/testimonials/test/worker.test.js.
        self.assertEqual(t.gallery_key(SECRET, GALLERY), "cb00ae7aad970690276ee2234adf465e375e8d272e2fd0bc170ecf93aca1c51b")

    def settings(self, **env):
        base = {"R2_ACCOUNT_ID": "a" * 32, "R2_ACCESS_KEY_ID": "i", "R2_SECRET_ACCESS_KEY": "s", "R2_BUCKET": "b",
                "GALLERY_BASE_URL": "https://g.test"}
        return r2.load_settings({**base, **env})

    def test_pages_get_a_key_and_never_the_secret(self):
        settings = self.settings(VITE_TESTIMONIALS_URL="https://w.test/", TESTIMONIALS_SECRET=SECRET)
        page = t.page_settings(settings, GALLERY)
        self.assertEqual(page["url"], "https://w.test")
        self.assertEqual(page["gallery"], GALLERY)
        self.assertNotIn(SECRET, json.dumps(page))

    def test_galleries_publish_without_asking_until_it_is_set_up(self):
        self.assertIsNone(t.page_settings(self.settings(), GALLERY))
        self.assertIsNone(t.page_settings(self.settings(VITE_TESTIMONIALS_URL="https://w.test"), GALLERY))
        self.assertIsNone(t.page_settings(self.settings(TESTIMONIALS_SECRET=SECRET), GALLERY))


class ClientTests(Base):
    def test_each_message_is_announced_once_even_after_a_restart(self):
        self.assertEqual([i["id"] for i in self.client.sync()], [WAITING["id"]])
        self.assertEqual(self.client.sync(), [])
        again = t.Testimonials("https://worker.test", SECRET, self.root, opener=self.worker)
        self.assertEqual(again.sync(), [])

    def test_requests_carry_the_secret_and_a_named_client(self):
        self.client.sync()
        _, _, headers = self.worker.calls[0]
        self.assertEqual(headers["Authorization"], f"Bearer {SECRET}")
        self.assertEqual(headers["User-agent"], t.USER_AGENT)

    def test_the_workers_reason_is_passed_along(self):
        body = io.BytesIO(json.dumps({"error": "This client did not agree to have it posted."}).encode())
        self.worker.fail = urllib.error.HTTPError("u", 400, "Bad", {}, body)
        with self.assertRaisesRegex(ValueError, "did not agree"):
            self.client.approve(WAITING["id"], "Ann", "Lovely.")


class WatcherTests(Base):
    def setUp(self):
        super().setUp()
        self.store = flow.Store(self.root / "work")

    def test_a_new_message_sends_one_notification(self):
        self.store.shoots["Shoot"] = {"client": "Ann + Bo", "token": GALLERY}
        with mock.patch.object(watcher, "notify") as notify:
            watcher.check_testimonials(self.client, self.store)
            watcher.check_testimonials(self.client, self.store)
        notify.assert_called_once_with("New client testimonial", "From Ann + Bo")

    def test_a_failed_check_never_stops_the_service(self):
        self.worker.fail = OSError("offline")
        with mock.patch.object(watcher, "notify") as notify:
            watcher.check_testimonials(self.client, self.store)
        notify.assert_not_called()


class ServerTests(Base):
    def setUp(self):
        super().setUp()
        self.store = flow.Store(self.root / "work")
        self.store.shoots["Shoot"] = {"name": "Shoot", "client": "Ann + Bo", "token": GALLERY, "status": "published"}
        self.port = 18131
        self.server = start_server(App(self.store, lambda: None, self.client), self.port)
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)

    def get(self, path):
        with urllib.request.urlopen(f"http://127.0.0.1:{self.port}{path}") as response:
            return json.loads(response.read())

    def post(self, path, body, origin=None):
        request = urllib.request.Request(
            f"http://127.0.0.1:{self.port}{path}", data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json", "Origin": origin or f"http://127.0.0.1:{self.port}"})
        try:
            with urllib.request.urlopen(request) as response:
                return response.status, json.loads(response.read())
        except urllib.error.HTTPError as exc:
            return exc.code, json.loads(exc.read())

    def test_the_page_sees_the_client_name_and_not_the_private_link(self):
        data = self.get("/api/testimonials?fresh=1")
        self.assertTrue(data["configured"])
        self.assertEqual(data["pending"][0]["client"], "Ann + Bo")
        self.assertNotIn("gallery", data["pending"][0])

    def test_approve_sends_edits_through(self):
        self.get("/api/testimonials?fresh=1")
        status, _ = self.post("/api/testimonials/approve", {"id": WAITING["id"], "name": "Ann S.", "text": "Lovely!"})
        self.assertEqual(status, 200)
        data = self.get("/api/testimonials")
        self.assertEqual(data["pending"], [])
        self.assertEqual(data["published"][0]["name"], "Ann S.")

    def test_delete_and_unpublish_reach_the_worker(self):
        self.post("/api/testimonials/approve", {"id": WAITING["id"], "name": "Ann", "text": "Lovely."})
        self.assertEqual(self.post("/api/testimonials/unpublish", {"id": WAITING["id"]})[0], 200)
        self.assertEqual(len(self.get("/api/testimonials")["pending"]), 1)
        self.assertEqual(self.post("/api/testimonials/delete", {"id": WAITING["id"]})[0], 200)
        self.assertEqual(self.get("/api/testimonials")["pending"], [])

    def test_other_websites_cannot_approve(self):
        status, _ = self.post("/api/testimonials/approve", {"id": WAITING["id"]}, origin="https://evil.test")
        self.assertEqual(status, 403)
        self.assertFalse([c for c in self.worker.calls if c[0] == "/admin/approve"])

    def test_an_outage_is_reported_and_the_last_list_kept(self):
        self.get("/api/testimonials?fresh=1")
        self.worker.fail = OSError("offline")
        data = self.get("/api/testimonials?fresh=1")
        self.assertIn("offline", data["error"])
        self.assertEqual(len(data["pending"]), 1)


class NotSetUpTests(unittest.TestCase):
    def test_the_page_hides_the_section_and_actions_are_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            app = App(flow.Store(tmp), lambda: None)
            self.assertEqual(app.testimonial_data(fresh=True), {"configured": False})
            with self.assertRaises(ValueError):
                app.testimonial_action("approve", {"id": "x"})


if __name__ == "__main__":
    unittest.main()
