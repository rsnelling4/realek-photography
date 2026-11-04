"""The background service: watches the Drive folder, builds galleries, and runs the approval page.

  python tools/preview/watcher.py
"""
import logging
import os
import sys
import time
import webbrowser
import winreg
from pathlib import Path

from dotenv import dotenv_values

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))

import publish as r2  # noqa: E402
import shoots as flow  # noqa: E402
from render import WORK_ROOT  # noqa: E402
from review_server import PORT, App, start_server  # noqa: E402

DEFAULT_INCOMING = r"G:\My Drive\Realek Galleries\Incoming"
POLL_SECONDS = 30
DAILY_SECONDS = 24 * 60 * 60
PAGE_URL = f"http://127.0.0.1:{PORT}/"
PUSH_SETTINGS = r"Software\Microsoft\Windows\CurrentVersion\PushNotifications"


def windows_notifications_on():
    """Windows drops notifications silently when they're switched off, so this asks first."""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, PUSH_SETTINGS) as key:
            return winreg.QueryValueEx(key, "ToastEnabled")[0] != 0
    except OSError:  # never changed from the default, which is on
        return True


def notify(title, message):
    """A Windows notification, or the approval page itself if notifications are off.
    A failure here never stops the work."""
    try:
        if not windows_notifications_on():
            opened = webbrowser.open(PAGE_URL)
            logging.info("%s: %s. Notifications are off, so opened the approval page (%s)", title, message, opened)
            return
        from winotify import Notification

        toast = Notification(app_id="REALEK Galleries", title=title, msg=message, launch=PAGE_URL)
        toast.add_actions(label="Review", launch=PAGE_URL)
        toast.show()
        logging.info("%s: %s. Sent a notification", title, message)
    except Exception:
        logging.exception("Couldn't let Robert know a gallery is ready")


def get_r2():
    settings = r2.load_settings(dotenv_values(ROOT / ".env"))
    return r2.make_client(settings), settings


def daily_tidy(store):
    """Marks expired galleries, and deletes any over a month old in case the bucket rule ever goes."""
    flow.mark_expired(store)
    try:
        s3, settings = get_r2()
        deleted = r2.delete_expired(s3, settings)
        if deleted:
            logging.info("Deleted %s expired gallery files", deleted)
    except Exception:
        logging.exception("Couldn't check for expired galleries; trying again tomorrow")


def run(incoming, store):
    flow.recover(store)
    next_tidy = 0
    warned_missing = False
    while True:
        if time.time() >= next_tidy:
            daily_tidy(store)
            next_tidy = time.time() + DAILY_SECONDS
        if not Path(incoming).is_dir() and not warned_missing:
            logging.warning("Can't see %s. Is Google Drive running?", incoming)
            warned_missing = True
        elif Path(incoming).is_dir():
            warned_missing = False
        try:
            for name in flow.scan(store, incoming):
                logging.info("Building %s", name)
                try:
                    record = flow.build(store, name, incoming)
                except Exception as exc:
                    logging.exception("Build failed for %s", name)
                    store.update(name, status="waiting", stable_since=time.time(), error=f"Building failed: {exc}")
                    continue
                count = len(record.get("photos", []))
                notify("Gallery ready for approval", f"{record['client']}: {count} photos")
        except Exception:  # for example, Drive going offline mid-scan; try again next time
            logging.exception("Scan failed")
        time.sleep(POLL_SECONDS)


def main():
    WORK_ROOT.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(filename=WORK_ROOT / "watcher.log", level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    incoming = dotenv_values(ROOT / ".env").get("GALLERY_INCOMING") or DEFAULT_INCOMING
    store = flow.Store(WORK_ROOT)
    try:
        start_server(App(store, get_r2))
    except OSError:  # the port is taken, which means the service is already running
        logging.info("Already running; exiting.")
        return
    logging.info("Started. Watching %s, approval page at %s", incoming, PAGE_URL)
    print(f"Watching {incoming}\nApproval page: {PAGE_URL}", flush=True) if sys.stdout else None
    run(incoming, store)


if __name__ == "__main__":
    os.chdir(HERE)
    main()
