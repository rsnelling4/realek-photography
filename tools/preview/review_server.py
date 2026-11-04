"""The local approval page. Only this PC can reach it, and it rejects requests from other sites."""
import json
import re
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import shoots as flow

HERE = Path(__file__).resolve().parent
PORT = 8130
PAGE = HERE / "templates" / "review.html"
IMAGE_PATH = re.compile(r"^/work/([a-z0-9-]+)/(thumb|img)/(\d{3}\.jpg)$")
MAX_BODY = 1_000_000


class App:
    """What the page needs: the shoots, and the means to publish them."""

    def __init__(self, store, get_r2):
        self.store = store
        self.get_r2 = get_r2  # returns (s3 client, settings), and raises if they aren't set up

    def publish_in_background(self, name, client, removed, cover):
        with self.store.lock:
            record = self.store.shoots.get(name)
            if record is None:
                raise ValueError("That shoot no longer exists.")
            if record["status"] != "ready":
                raise ValueError("This gallery isn't ready to publish.")
            flow.validate_choices(record, client, removed, cover)
        s3, settings = self.get_r2()
        threading.Thread(target=flow.publish_shoot, args=(self.store, name, client, removed, cover, s3, settings),
                         daemon=True).start()

    def take_down(self, name):
        if name not in self.store.shoots:
            raise ValueError("That shoot no longer exists.")
        s3, settings = self.get_r2()
        flow.take_down_shoot(self.store, name, s3, settings)


def make_handler(app, port):
    allowed_hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def send_body(self, status, body, content_type):
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Frame-Options", "DENY")
            self.end_headers()
            self.wfile.write(body)

        def send_json(self, status, data):
            self.send_body(status, json.dumps(data).encode(), "application/json")

        def host_allowed(self):
            return self.headers.get("Host") in allowed_hosts

        def do_GET(self):
            if not self.host_allowed():
                return self.send_body(403, b"Forbidden", "text/plain")
            path = self.path.split("?", 1)[0]
            if path == "/":
                return self.send_body(200, PAGE.read_bytes(), "text/html; charset=utf-8")
            if path == "/api/shoots":
                return self.send_json(200, {"shoots": app.store.snapshot()})
            match = IMAGE_PATH.match(path)
            if match:
                slug, folder, file_name = match.groups()
                image = app.store.root / "shoots" / slug / folder / file_name
                if image.is_file():
                    return self.send_body(200, image.read_bytes(), "image/jpeg")
            return self.send_body(404, b"Not found", "text/plain")

        def do_POST(self):
            # A website you visit can send requests to this PC. These checks refuse them.
            origin = self.headers.get("Origin", "")
            if not self.host_allowed() or origin.split("//")[-1] not in allowed_hosts \
                    or self.headers.get("Content-Type") != "application/json":
                return self.send_json(403, {"error": "Forbidden"})
            try:
                length = int(self.headers.get("Content-Length", 0))
                if length > MAX_BODY:
                    raise ValueError("Request too large.")
                data = json.loads(self.rfile.read(length))
                if self.path == "/api/publish":
                    app.publish_in_background(data["name"], data.get("client"), data.get("removed"), data.get("cover"))
                elif self.path == "/api/take-down":
                    app.take_down(data["name"])
                else:
                    return self.send_json(404, {"error": "Not found"})
            except (ValueError, KeyError, TypeError) as exc:
                return self.send_json(400, {"error": str(exc)})
            except Exception as exc:  # shown to Robert on the page, for example a connection problem
                return self.send_json(500, {"error": f"That didn't work: {exc}"})
            return self.send_json(200, {"ok": True})

    return Handler


def start_server(app, port=PORT):
    server = ThreadingHTTPServer(("127.0.0.1", port), make_handler(app, port))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server
