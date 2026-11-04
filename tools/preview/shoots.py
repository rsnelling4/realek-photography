"""Tracks each shoot from the drop folder through to a published gallery.

    waiting -> building -> ready -> publishing -> published -> taken_down

Progress is saved after every step, so a restart picks up where things left off.
"""
import hashlib
import json
import os
import re
import shutil
import threading
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import publish as r2
import testimonials
from images import EXTENSIONS
from render import EXPIRY_DAYS, expiry_label, finish_gallery, list_photos, render_photos

QUIET_SECONDS = 300  # a folder must sit unchanged this long before it counts as fully copied


class Store:
    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / "shoots.json"
        self.lock = threading.RLock()
        self.shoots = json.loads(self.path.read_text(encoding="utf-8")) if self.path.exists() else {}

    def save(self):
        temp = self.path.with_suffix(".tmp")
        temp.write_text(json.dumps(self.shoots, indent=1, ensure_ascii=False), encoding="utf-8")
        os.replace(temp, self.path)

    def update(self, name, **changes):
        with self.lock:
            self.shoots[name].update(changes)
            self.save()
            return dict(self.shoots[name])

    def snapshot(self):
        with self.lock:
            return json.loads(json.dumps(self.shoots))

    def work_dir(self, record):
        return self.root / "shoots" / record["slug"]


def make_slug(name):
    """Readable, and unique even for names like "A + B" and "A B"."""
    readable = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:40] or "shoot"
    return f"{readable}-{hashlib.sha256(name.encode()).hexdigest()[:8]}"


def fingerprint(folder):
    """Changes whenever a file is added, removed, or still being written."""
    count, total, latest, others = 0, 0, 0.0, 0
    for entry in Path(folder).iterdir():
        if not entry.is_file():
            continue
        if entry.suffix.lower() not in EXTENSIONS:
            others += 1
            continue
        info = entry.stat()
        count, total, latest = count + 1, total + info.st_size, max(latest, info.st_mtime)
    return {"count": count, "print": f"{count}:{total}:{latest}", "others": others}


def recover(store):
    """Anything interrupted by a restart or crash goes back a step."""
    with store.lock:
        for record in store.shoots.values():
            if record["status"] == "building":
                record.update(status="waiting", stable_since=time.time())
            elif record["status"] == "publishing":
                record.update(status="ready", error="Publishing was interrupted. Please approve it again.")
        store.save()


def scan(store, incoming, now=None, quiet=QUIET_SECONDS):
    """Notes new and changed folders, and returns the names ready to build."""
    now = time.time() if now is None else now
    incoming = Path(incoming)
    if not incoming.is_dir():  # for example, the Drive app isn't running; don't touch any records
        return []
    present = {}
    for folder in incoming.iterdir():
        if folder.is_dir():
            try:
                present[folder.name] = fingerprint(folder)
            except OSError:
                continue  # still appearing; check again next time
    ready_to_build = []
    with store.lock:
        for name, info in present.items():
            record = store.shoots.get(name)
            if record is None:
                if info["count"]:
                    store.shoots[name] = {
                        "name": name, "slug": make_slug(name), "client": name, "status": "waiting",
                        "print": info["print"], "stable_since": now, "removed": [], "cover": None,
                    }
                continue
            status = record["status"]
            changed = info["print"] != record["print"]
            if status == "waiting":
                if changed:
                    record.update(print=info["print"], stable_since=now)
                elif info["count"] and now - record["stable_since"] >= quiet:
                    ready_to_build.append(name)
            elif status == "ready" and changed:
                record.update(status="waiting", print=info["print"], stable_since=now)
            elif status in ("published", "taken_down"):
                record["changed_after_publish"] = changed
        # A folder removed before publishing is dropped. Published records stay for their links.
        for name in [n for n, r in store.shoots.items() if n not in present and r["status"] in ("waiting", "ready")]:
            shutil.rmtree(store.work_dir(store.shoots[name]), ignore_errors=True)
            del store.shoots[name]
        store.save()
    return ready_to_build


def build(store, name, incoming):
    record = store.update(name, status="building", error=None)
    folder = Path(incoming) / name
    info = fingerprint(folder)
    rendered, failed = render_photos(list_photos(folder), store.work_dir(record))
    names = {p["name"] for p in rendered}
    with store.lock:
        current = store.shoots[name]
        return store.update(
            name, status="ready", print=info["print"], photos=rendered, failed=failed, others=info["others"],
            removed=[n for n in current.get("removed", []) if n in names],
            cover=current.get("cover") if current.get("cover") in names else None,
            built_at=time.time(),
            error=None if rendered else "None of these photos could be read.",
        )


def validate_choices(record, client, removed, cover):
    client = (client or "").strip()
    if not client:
        raise ValueError("Please enter the client's name.")
    known = {p["name"] for p in record.get("photos", [])}
    removed = [n for n in removed or [] if n in known]
    if len(removed) >= len(known):
        raise ValueError("A gallery needs at least one photo.")
    return client, removed, cover if cover in known and cover not in removed else None


def publish_shoot(store, name, client, removed, cover, s3, settings, today=None, live_check=None):
    """Runs after Robert approves. On any failure the shoot stays ready, with the reason shown."""
    live_check = live_check or r2.check_live
    with store.lock:
        record = store.shoots[name]
        if record["status"] != "ready":
            raise ValueError("This gallery isn't ready to publish.")
        client, removed, cover = validate_choices(record, client, removed, cover)
        token = record.get("token") or r2.new_token()
        record = store.update(name, status="publishing", client=client, removed=removed, cover=cover,
                              token=token, error=None)
    try:
        photos = [p for p in record["photos"] if p["name"] not in removed]
        cover_index = next((i for i, p in enumerate(photos) if p["name"] == cover), 0)
        # Dated from approval, so time spent waiting for review doesn't shorten the client's month.
        expires = (today or date.today()) + timedelta(days=EXPIRY_DAYS)
        out = store.work_dir(record)
        manifest = finish_gallery(photos, out, client, expires, cover_index, testimonials.page_settings(settings, token))
        url = r2.upload_gallery(s3, settings, out, manifest, token)
        if not live_check(url):
            raise RuntimeError("The upload finished, but the gallery didn't open at its address.")
    except Exception as exc:  # shown on the review page; the photos are still safe to retry
        return store.update(name, status="ready", error=f"Publishing failed: {exc}")
    shutil.rmtree(out, ignore_errors=True)  # gigabytes this PC no longer needs
    return store.update(
        name, status="published", url=url, expires=expires.isoformat(), expires_label=expiry_label(expires),
        message=r2.client_message(client, url, expiry_label(expires)), count=len(photos), size=manifest["zip"]["size"],
        published_at=datetime.now(timezone.utc).isoformat(), photos=[], changed_after_publish=False,
    )


def take_down_shoot(store, name, s3, settings):
    with store.lock:
        record = store.shoots[name]
        if record["status"] != "published":
            raise ValueError("Only a published gallery can be taken down.")
    deleted = r2.take_down(s3, settings, record["token"])
    return store.update(name, status="taken_down", url=None, message=None, deleted_files=deleted)


def mark_expired(store, today=None):
    today = (today or date.today()).isoformat()
    with store.lock:
        for record in store.shoots.values():
            if record["status"] == "published" and record.get("expires", "9999") < today:
                record.update(status="expired", message=None)
        store.save()
