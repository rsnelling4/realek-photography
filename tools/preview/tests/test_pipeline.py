"""Runs offline: synthetic photos and a fake API server. Nothing is sent anywhere."""
import json
import re
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import anthropic
import cv2
import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cull import cull  # noqa: E402
from curate import curate  # noqa: E402


def textured(seed):
    rng = np.random.default_rng(seed)
    coarse = rng.integers(0, 255, (60, 80, 3), dtype=np.uint8)
    return cv2.resize(coarse, (800, 600), interpolation=cv2.INTER_NEAREST)


def save(folder, name, array):
    Image.fromarray(array).save(Path(folder) / name, "JPEG", quality=92)


def message(text, stop_reason="end_turn"):
    content = [{"type": "text", "text": text}] if text else []
    return {"id": "msg_1", "type": "message", "role": "assistant", "model": "claude-opus-5-5",
            "content": content, "stop_reason": stop_reason, "stop_sequence": None,
            "usage": {"input_tokens": 1000, "output_tokens": 100}}


class FakeAPI(BaseHTTPRequestHandler):
    requests, refuse = [], False

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["content-length"])))
        FakeAPI.requests.append({"headers": dict(self.headers), "body": body})
        blocks = body["messages"][0]["content"]
        text = blocks[-1]["text"]
        ids = re.findall(r"Photo (P\d+):", " ".join(b["text"] for b in blocks if b["type"] == "text"))
        if FakeAPI.refuse:
            reply = message("", "refusal")
        elif "Score each photo" in text:
            photos = [{"id": i, "score": 99 if i == ids[0] else 7, "flags": [], "scene": "woods"} for i in ids]
            reply = message(json.dumps({"photos": photos}))
        else:
            order = ids[::-1][:len(ids) // 2] + ["P999"]  # unknown id must be ignored
            reply = message(json.dumps({"order": order, "runners_up": ids[-2:], "notes": "ok"}))
        payload = json.dumps(reply).encode()
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *args):
        pass


class CullTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def test_removes_failures_and_keeps_good_frames(self):
        for i in range(10):
            save(self.tmp.name, f"good{i}.jpg", textured(i))
        save(self.tmp.name, "blurry.jpg", cv2.GaussianBlur(textured(50), (0, 0), 25))
        save(self.tmp.name, "black.jpg", np.zeros((600, 800, 3), np.uint8))
        save(self.tmp.name, "white.jpg", np.full((600, 800, 3), 255, np.uint8))
        (Path(self.tmp.name) / "broken.jpg").write_bytes(b"not a jpeg")
        kept, rejected = cull(self.tmp.name)
        self.assertEqual({p.name for p in kept}, {f"good{i}.jpg" for i in range(10)})
        self.assertEqual({p.name for p in rejected}, {"blurry.jpg", "black.jpg", "white.jpg", "broken.jpg"})

    def test_burst_keeps_the_three_sharpest(self):
        base = textured(1)
        save(self.tmp.name, "a.jpg", base)
        for i, sigma in enumerate((0.6, 0.9, 1.2, 1.5), 1):
            save(self.tmp.name, f"b{i}.jpg", cv2.GaussianBlur(base, (0, 0), sigma))
        kept, rejected = cull(self.tmp.name)
        self.assertEqual(len(kept), 3)
        self.assertIn("a.jpg", {p.name for p in kept})
        self.assertTrue(all("near-duplicate" in p.reject_reason for p in rejected))

    def test_mostly_black_or_white_photo_with_a_subject_is_kept(self):
        # A night silhouette or high-key portrait: over 92% of the frame is one tone,
        # but the small subject is sharp.
        for name, background in (("night.jpg", 0), ("highkey.jpg", 255)):
            frame = np.full((600, 800, 3), background, np.uint8)
            frame[250:350, 350:450] = textured(3)[:100, :100]
            save(self.tmp.name, name, frame)
        self.assertEqual({p.name for p in cull(self.tmp.name)[0]}, {"night.jpg", "highkey.jpg"})

    def test_soft_photo_in_a_sharp_shoot_is_kept_if_it_has_a_sharp_area(self):
        for i in range(10):
            save(self.tmp.name, f"good{i}.jpg", textured(i))
        ring_detail = cv2.GaussianBlur(textured(20), (0, 0), 25)
        ring_detail[280:320, 380:420] = textured(21)[:40, :40]
        save(self.tmp.name, "ring.jpg", ring_detail)
        self.assertIn("ring.jpg", {p.name for p in cull(self.tmp.name)[0]})

    def test_originals_are_untouched(self):
        save(self.tmp.name, "a.jpg", textured(1))
        path = Path(self.tmp.name) / "a.jpg"
        before = path.read_bytes()
        cull(self.tmp.name)
        self.assertEqual(path.read_bytes(), before)


class CurateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), FakeAPI)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.url = f"http://127.0.0.1:{cls.server.server_port}"
        cls.tmp = tempfile.TemporaryDirectory(prefix="Secret Client Name ")
        for i in range(30):
            save(cls.tmp.name, f"IMG_{i:04d}.jpg", textured(i + 100))
        cls.candidates = cull(cls.tmp.name)[0]

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.tmp.cleanup()

    def setUp(self):
        FakeAPI.requests, FakeAPI.refuse = [], False
        self.client = anthropic.Anthropic(api_key="test", base_url=self.url, max_retries=0)

    def test_request_shape_and_privacy(self):
        draft = curate(self.candidates, self.client)
        self.assertIsNone(draft.fallback_reason)
        self.assertEqual(len(FakeAPI.requests), 3)  # two scoring batches, one sequencing
        for request in FakeAPI.requests:
            body = request["body"]
            self.assertEqual(body["model"], "claude-opus-5-5")
            self.assertEqual(body["fallbacks"], "default")
            headers = {k.lower(): v for k, v in request["headers"].items()}
            self.assertIn("server-side-fallback-2026-07-01", headers.get("anthropic-beta", ""))
            self.assertIn("format", body["output_config"])
            self.assertNotIn("temperature", body)
            raw = json.dumps(body["messages"]) + body["system"]
            self.assertNotIn("Secret Client", raw)
            self.assertNotIn("IMG_", raw)
        self.assertEqual(FakeAPI.requests[0]["body"]["output_config"]["effort"], "medium")
        self.assertEqual(FakeAPI.requests[-1]["body"]["output_config"]["effort"], "high")

    def test_cleans_up_a_bad_sequence_reply(self):
        draft = curate(self.candidates, self.client)
        names = [p.name for p in draft.picks]
        self.assertEqual(len(names), len(set(names)))
        self.assertGreaterEqual(len(names), 25)  # reply was short, so it is topped up
        self.assertLessEqual(len(names), 40)
        self.assertFalse({p.name for p in draft.runners_up} & set(names))
        self.assertTrue(all(1 <= s["score"] <= 10 for s in draft.scores.values()))
        self.assertTrue(any(s["score"] == 10 for s in draft.scores.values()))  # 99 was clamped

    def test_refusal_gives_a_labelled_local_draft(self):
        FakeAPI.refuse = True
        draft = curate(self.candidates, self.client)
        self.assertIn("refusal", draft.fallback_reason)
        self.assertEqual([p.name for p in draft.picks], [p.name for p in self.candidates])

    def test_outage_gives_a_labelled_local_draft(self):
        dead = anthropic.Anthropic(api_key="test", base_url="http://127.0.0.1:9", max_retries=0)
        draft = curate(self.candidates, dead)
        self.assertIsNotNone(draft.fallback_reason)
        self.assertEqual(len(draft.picks), 30)

    def test_tiny_shoot_uses_every_photo(self):
        draft = curate(self.candidates[:3], self.client)
        self.assertEqual(len(draft.picks), 3)

    def test_empty_shoot(self):
        self.assertIsNotNone(curate([], self.client).fallback_reason)


if __name__ == "__main__":
    unittest.main()
