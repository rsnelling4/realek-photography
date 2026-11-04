"""Puts a finished gallery on Cloudflare R2, and takes galleries down again."""
import re
import secrets
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

GALLERY_PREFIX = "p/"
TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9_-]{20,}$")
MAX_AGE_DAYS = 31  # matches the bucket's lifecycle rule; a backup in case that rule is ever removed
DELETE_BATCH = 1000
# Cloudflare keeps serving its cached copy after a delete, so these limit how long a
# gallery that's been taken down can still show. Downloads are free, so short costs nothing.
PHOTO_CACHE = "public, max-age=300"
PAGE_CACHE = "public, max-age=60"
ROBOTS = b"User-agent: *\nDisallow: /\n"
REQUIRED_SETTINGS = ("R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET", "GALLERY_BASE_URL")


@dataclass
class Settings:
    account_id: str
    access_key_id: str
    secret_access_key: str
    bucket: str
    base_url: str
    testimonials_url: str = None  # both optional; see testimonials.py
    testimonials_secret: str = None


def load_settings(env):
    missing = [key for key in REQUIRED_SETTINGS if not env.get(key)]
    if missing:
        raise ValueError(f"Missing from .env: {', '.join(missing)}")
    # Accepts just the ID, or the whole endpoint address Cloudflare shows.
    match = re.search(r"[0-9a-fA-F]{32}", env["R2_ACCOUNT_ID"])
    if not match:
        raise ValueError("R2_ACCOUNT_ID in .env doesn't contain a Cloudflare account ID.")
    return Settings(match.group(0), env["R2_ACCESS_KEY_ID"], env["R2_SECRET_ACCESS_KEY"], env["R2_BUCKET"],
                    env["GALLERY_BASE_URL"].rstrip("/"),
                    (env.get("VITE_TESTIMONIALS_URL") or "").rstrip("/") or None, env.get("TESTIMONIALS_SECRET") or None)


def make_client(settings):
    import boto3
    from botocore.config import Config

    return boto3.client(
        "s3",
        endpoint_url=f"https://{settings.account_id}.r2.cloudflarestorage.com",
        aws_access_key_id=settings.access_key_id,
        aws_secret_access_key=settings.secret_access_key,
        region_name="auto",
        config=Config(retries={"max_attempts": 5, "mode": "standard"}, connect_timeout=30, read_timeout=120,
                      request_checksum_calculation="when_required", response_checksum_validation="when_required"),
    )


def new_token():
    return secrets.token_urlsafe(24)


def gallery_url(settings, token):
    # R2 doesn't open index.html for a folder address, so links name the page.
    return f"{settings.base_url}/{GALLERY_PREFIX}{token}/index.html"


def attachment(file_name):
    """A download header that also survives accented letters in file names."""
    ascii_name = re.sub(r'[^A-Za-z0-9 ._()+-]', "_", file_name)
    return f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{urllib.parse.quote(file_name)}"


def upload_list(out, manifest):
    """Only what the page refers to, with the page last, so a link never works half-uploaded."""
    out = Path(out)
    files = []
    for photo in manifest["photos"]:
        files.append((out / photo["full"], photo["full"], "image/jpeg", PHOTO_CACHE, attachment(photo["name"])))
        files.append((out / photo["src"], photo["src"], "image/jpeg", PHOTO_CACHE, None))
        files.append((out / photo["thumb"], photo["thumb"], "image/jpeg", PHOTO_CACHE, None))
    zip_info = manifest["zip"]
    files.append((out / zip_info["src"], zip_info["src"], "application/zip", PHOTO_CACHE, attachment(zip_info["name"])))
    return files


def upload_gallery(s3, settings, out, manifest, token):
    prefix = f"{GALLERY_PREFIX}{token}/"

    def send(item):
        path, key, content_type, cache, disposition = item
        extra = {"ContentType": content_type, "CacheControl": cache}
        if disposition:
            extra["ContentDisposition"] = disposition
        s3.upload_file(str(path), settings.bucket, prefix + key, ExtraArgs=extra)

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(send, upload_list(out, manifest)))
    # Re-sent each time because the bucket's one-month rule deletes it too.
    s3.put_object(Bucket=settings.bucket, Key="robots.txt", Body=ROBOTS, ContentType="text/plain")
    s3.upload_file(str(Path(out) / "index.html"), settings.bucket, f"{prefix}index.html",
                   ExtraArgs={"ContentType": "text/html; charset=utf-8", "CacheControl": PAGE_CACHE})
    return gallery_url(settings, token)


def check_live(url):
    request = urllib.request.Request(url, headers={"User-Agent": "realek-gallery-check"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.status == 200
    except (urllib.error.URLError, OSError):
        return False


def _delete_keys(s3, settings, keys):
    for start in range(0, len(keys), DELETE_BATCH):
        batch = keys[start:start + DELETE_BATCH]
        s3.delete_objects(Bucket=settings.bucket, Delete={"Objects": [{"Key": k} for k in batch], "Quiet": True})


def take_down(s3, settings, token):
    """Deletes one gallery. Refuses anything that could widen to other galleries."""
    if not TOKEN_PATTERN.match(token or ""):
        raise ValueError("That doesn't look like a gallery token.")
    keys = []
    for page in s3.get_paginator("list_objects_v2").paginate(Bucket=settings.bucket, Prefix=f"{GALLERY_PREFIX}{token}/"):
        keys += [item["Key"] for item in page.get("Contents", [])]
    _delete_keys(s3, settings, keys)
    return len(keys)


def delete_expired(s3, settings, now=None, max_age_days=MAX_AGE_DAYS):
    """Backup for the bucket's lifecycle rule: removes gallery files past their month."""
    cutoff = (now or datetime.now(timezone.utc)) - timedelta(days=max_age_days)
    keys = []
    for page in s3.get_paginator("list_objects_v2").paginate(Bucket=settings.bucket, Prefix=GALLERY_PREFIX):
        keys += [item["Key"] for item in page.get("Contents", []) if item["LastModified"] < cutoff]
    _delete_keys(s3, settings, keys)
    return len(keys)


def client_message(client, url, expires_label):
    return (f"Hi {client}! Your photos are ready:\n\n{url}\n\n"
            f"You can watch the slideshow and download all your photos there. "
            f"The gallery is available until {expires_label}, so be sure to save them before then.\n\n"
            f"Thank you so much!")
