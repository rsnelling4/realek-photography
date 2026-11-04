# Client gallery tool

Turns a folder of finished, edited photos into a private client gallery, available for one
month. Every photo goes in, in shooting order, with a slideshow and downloads.

## Using it

1. Add a client's folder of edited JPEGs to `Realek Galleries/Incoming` in Google Drive.
2. About five minutes after copying finishes, a notification appears. Click it, or open
   the approval page at http://127.0.0.1:8130/ on this PC.
3. Check the client's name, remove any photos, choose the opening photo, and approve.
4. Copy the ready-made message and send it to your client.

The approval page also has **Take down gallery**, which ends a gallery early. A deleted
gallery can stay visible briefly because of caching.

## Running it

The service starts when you log in to Windows. To install or restart it:

    pip install -r tools/preview/requirements.txt
    powershell -ExecutionPolicy Bypass -File tools/preview/install_task.ps1

To remove it: `Unregister-ScheduledTask -TaskName "REALEK Galleries" -Confirm:$false`

It logs to `%LOCALAPPDATA%\RealekGalleries\watcher.log`. Galleries are built in that folder,
outside OneDrive and Google Drive, and removed from this PC once published.

Settings live in the repo's `.env`: `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`,
`R2_BUCKET` and `GALLERY_BASE_URL`. Set `GALLERY_INCOMING` if Drive isn't at `G:\My Drive`.

The bucket has a lifecycle rule deleting files after 31 days. The service also deletes
anything older than that once a day while it's running, as a backup.

## For testing

To build a gallery locally without publishing:

    python tools/preview/render.py "path/to/shoot" --client "Display Name"

Originals are only read. Tests run offline, and need `numpy` too:

    python tools/preview/tests/test_render.py
    python tools/preview/tests/test_flow.py
