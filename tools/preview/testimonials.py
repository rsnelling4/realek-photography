"""Talks to the testimonials Worker (tools/testimonials) for the approval page and service.

Optional: without TESTIMONIALS_SECRET and VITE_TESTIMONIALS_URL in .env, galleries simply don't
ask, and everything else works as before.
"""
import hashlib
import hmac
import json
import threading
import urllib.error
import urllib.request
from pathlib import Path

USER_AGENT = "realek-gallery-tool"  # Cloudflare can refuse Python's default


def gallery_key(secret, token):
    """Proves to the Worker that a submission came from a gallery published here."""
    return hmac.new(secret.encode(), f"gallery:{token}".encode(), hashlib.sha256).hexdigest()


def page_settings(settings, token):
    """What a gallery page needs in order to ask. The secret itself never goes in the page."""
    if not (settings.testimonials_url and settings.testimonials_secret):
        return None
    return {"url": settings.testimonials_url, "gallery": token, "key": gallery_key(settings.testimonials_secret, token)}


class Testimonials:
    def __init__(self, url, secret, root, opener=urllib.request.urlopen):
        self.url = url.rstrip("/")
        self.secret = secret
        self.seen_path = Path(root) / "testimonials_seen.json"
        self.opener = opener
        self.lock = threading.Lock()
        self.data = {"pending": [], "published": []}
        self.seen = set(json.loads(self.seen_path.read_text(encoding="utf-8"))) if self.seen_path.exists() else set()

    def _call(self, path, body=None):
        request = urllib.request.Request(
            f"{self.url}{path}", data=None if body is None else json.dumps(body).encode(),
            headers={"Authorization": f"Bearer {self.secret}", "Content-Type": "application/json", "User-Agent": USER_AGENT},
        )
        try:
            with self.opener(request, timeout=30) as response:
                return json.loads(response.read())
        except urllib.error.HTTPError as exc:
            try:
                reason = json.loads(exc.read()).get("error")
            except ValueError:
                reason = None
            raise ValueError(reason or f"The testimonials service answered {exc.code}.") from exc

    def sync(self):
        """Fetches the latest and returns those waiting that haven't been announced yet."""
        data = self._call("/admin/submissions")
        with self.lock:
            self.data = data
            new = [item for item in data["pending"] if item["id"] not in self.seen]
            if new:
                self.seen |= {item["id"] for item in new}
                self.seen_path.write_text(json.dumps(sorted(self.seen)), encoding="utf-8")
        return new

    def approve(self, testimonial_id, name, text):
        self._call("/admin/approve", {"id": testimonial_id, "name": name, "text": text})
        self.sync()

    def unpublish(self, testimonial_id):
        self._call("/admin/unpublish", {"id": testimonial_id})
        self.sync()

    def delete(self, testimonial_id):
        self._call("/admin/delete", {"id": testimonial_id})
        self.sync()
