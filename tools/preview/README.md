# Client gallery tool

Turns a folder of finished, edited photos into a private client gallery, available for one
month. Every photo goes in, in shooting order, with a slideshow and downloads.

## Using it

1. Add a client's folder of edited JPEGs to `Realek Galleries/Incoming` in Google Drive.
2. About five minutes after copying finishes, a notification appears, or the approval page
   opens in your browser if Windows notifications are off. You can also go to
   http://127.0.0.1:8130/ on this PC at any time.
3. Check the client's name, remove any photos, choose the opening photo, and approve.
4. Copy the ready-made message and send it to your client.

The approval page also has **Take down gallery**, which ends a gallery early. A deleted
gallery can stay visible briefly because of caching.

## Testimonials

After a client's slideshow ends, or a moment after they download everything, the gallery asks once
whether they'd like to share their experience. A link on the gallery page stays available afterward.
They can give permission to post it, or send it to you privately.

New messages appear at the top of the approval page, with a notification, within about five minutes.
You can correct the name or a typo, then choose **Approve and post to website**. It shows on the main
site within a couple of minutes, with no rebuild. **Remove from website** puts it back in the queue.
Private messages can't be posted. Nothing shows on the site until you approve it, and the section
stays hidden until the first one.

Only galleries published after setup can ask; galleries already live keep the page they have.

### Setting it up, once

Run these from `tools/testimonials`. The first opens your browser to log in to Cloudflare.

    npx wrangler@4 login
    npx wrangler@4 kv namespace create TESTIMONIALS --binding TESTIMONIALS --update-config
    npx wrangler@4 secret put TESTIMONIAL_SECRET
    npx wrangler@4 deploy

For the secret, paste a long random value, such as the output of
`python -c "import secrets; print(secrets.token_urlsafe(32))"`. `deploy` prints the Worker's address.
Add both to the repo's `.env`:

    VITE_TESTIMONIALS_URL=https://realek-testimonials.<your-subdomain>.workers.dev
    TESTIMONIALS_SECRET=<the same secret>

Then restart the service (see below). The site reads the same address from `.env.production`, which is
committed because Cloudflare builds the site from the repo and never sees `.env`; pushing to `main` is
what updates the site. Until then, galleries publish as usual without asking.

Testimonials live in Cloudflare KV rather than the gallery bucket, because that bucket's one-month
rule would delete them.

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
    python tools/preview/tests/test_testimonials.py
    node --test tools/testimonials/test/
