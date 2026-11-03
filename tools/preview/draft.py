"""Build a draft preview from a shoot folder and write a local report to judge it.

  python tools/preview/draft.py "path/to/shoot"            local filter + Claude
  python tools/preview/draft.py "path/to/shoot" --no-ai    local only, nothing is sent
"""
import argparse
import html
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from dotenv import load_dotenv

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))

from cull import cull, load_rgb  # noqa: E402
from curate import Draft, curate, local_fallback  # noqa: E402

THUMB_EDGE = 480


def portfolio_picks(shoot_name):
    """Filenames from this shoot that scripts/build_gallery.py lists as portfolio picks."""
    source = (ROOT / "scripts" / "build_gallery.py").read_text(encoding="utf-8")
    return {name for shoot, name in re.findall(r'O\("([^"]+)","([^"]+)"\)', source) if shoot == shoot_name}


def card(photo, thumbs, caption="", highlight=False):
    classes = "card hit" if highlight else "card"
    return (f'<figure class="{classes}"><img loading="lazy" src="thumbs/{html.escape(thumbs[photo.path], quote=True)}">'
            f"<figcaption>{html.escape(photo.name)}<br>{html.escape(caption)}</figcaption></figure>")


def write_report(out, shoot, draft, candidates, rejected, picks_from_portfolio):
    thumbs_dir = out / "thumbs"
    thumbs_dir.mkdir(parents=True, exist_ok=True)
    everything = candidates + rejected
    thumbs = {p.path: f"{i:04d}.jpg" for i, p in enumerate(everything)}

    def make_thumb(photo):
        try:
            load_rgb(photo.path, THUMB_EDGE).save(thumbs_dir / thumbs[photo.path], "JPEG", quality=75)
        except OSError:
            pass  # an unreadable file already appears in the removed list
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(make_thumb, everything))

    def describe(photo):
        s = draft.scores.get(photo.name)
        if not s:
            return ""
        flags = f" · {', '.join(s['flags'])}" if s["flags"] else ""
        return f"{s['score']}/10 · {s['scene']}{flags}"

    picked = {p.name for p in draft.picks}
    matched = sorted(picked & picks_from_portfolio)
    sections = [f"<h1>{html.escape(shoot)}</h1>"]
    sections.append(
        f"<p>{len(candidates) + len(rejected)} photos · {len(rejected)} removed by the filter · "
        f"{len(draft.picks)} picked · estimated AI cost ${draft.estimated_cost:.2f} "
        f"({draft.input_tokens:,} input / {draft.output_tokens:,} output tokens)</p>")
    if draft.fallback_reason:
        sections.append(f'<p class="warn">AI wasn\'t used. This draft is local sharpness only: {html.escape(draft.fallback_reason)}</p>')
    if draft.notes:
        sections.append(f"<blockquote>{html.escape(draft.notes)}</blockquote>")
    if picks_from_portfolio:
        sections.append(f"<p>Your portfolio picks from this shoot that were chosen (green outline): "
                        f"{len(matched)} of {len(picks_from_portfolio)}.</p>")
    sections += [f'<p class="warn">{html.escape(w)}</p>' for w in draft.warnings]

    def grid(title, photos, caption=describe):
        cards = "".join(card(p, thumbs, caption(p), p.name in picks_from_portfolio) for p in photos)
        return f'<h2>{title} ({len(photos)})</h2><div class="grid">{cards}</div>'

    shown = picked | {p.name for p in draft.runners_up}
    sections.append(grid("Picks, in slideshow order", draft.picks))
    sections.append(grid("Runners-up", draft.runners_up))
    sections.append(grid("Not chosen", [p for p in candidates if p.name not in shown]))
    sections.append(grid("Removed by the local filter", rejected, lambda p: p.reject_reason))

    (out / "report.html").write_text(f"""<!doctype html><meta charset="utf-8"><title>{html.escape(shoot)}: draft</title>
<style>body{{font:15px system-ui;background:#FDFAF6;color:#2C1810;max-width:1200px;margin:2rem auto;padding:0 1rem}}
h1,h2{{font-family:Georgia,serif}}.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(210px,1fr));gap:12px}}
.card{{margin:0;background:#fff;padding:6px;border:3px solid transparent}}.hit{{border-color:#3d8b4f}}
img{{width:100%;height:210px;object-fit:contain;background:#F0E6D9}}figcaption{{font-size:12px;color:#8B5E3C;padding-top:4px}}
.warn{{background:#fbeadf;padding:.6rem;border-left:4px solid #C17A50}}blockquote{{font-style:italic}}</style>
{''.join(sections)}""", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("shoot", type=Path)
    parser.add_argument("--no-ai", action="store_true", help="local filter only; nothing is sent to the API")
    args = parser.parse_args()
    if not args.shoot.is_dir():
        parser.error(f"not a folder: {args.shoot}")

    load_dotenv(ROOT / ".env")
    shoot = args.shoot.resolve().name
    out = HERE / "_work" / re.sub(r"[^\w-]+", "-", shoot).strip("-").lower()
    out.mkdir(parents=True, exist_ok=True)

    print(f"Filtering {shoot}")
    candidates, rejected = cull(args.shoot)
    print(f"  {len(candidates)} candidates, {len(rejected)} removed")

    if args.no_ai:
        draft = Draft()
        local_fallback(draft, {f"P{i:03d}": p for i, p in enumerate(candidates, 1)}, "--no-ai was used")
    else:
        print("Asking Claude")
        draft = curate(candidates)

    write_report(out, shoot, draft, candidates, rejected, portfolio_picks(shoot))
    (out / "draft.json").write_text(json.dumps({
        "shoot": shoot,
        "picks": [p.to_dict() for p in draft.picks],
        "runners_up": [p.to_dict() for p in draft.runners_up],
        "rejected": [p.to_dict() for p in rejected],
        "scores": draft.scores,
        "notes": draft.notes,
        "fallback_reason": draft.fallback_reason,
        "warnings": draft.warnings,
        "usage": {"input_tokens": draft.input_tokens, "output_tokens": draft.output_tokens,
                  "estimated_cost_usd": round(draft.estimated_cost, 2)},
    }, indent=2), encoding="utf-8")
    print(f"{len(draft.picks)} picks, about ${draft.estimated_cost:.2f}")
    if draft.fallback_reason:
        print(f"AI not used: {draft.fallback_reason}")
    print(f"Report: {out / 'report.html'}")


if __name__ == "__main__":
    main()
