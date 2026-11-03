"""Claude's role: score the candidates, then choose and order the highlights.

Only numbered, downscaled, metadata-free JPEGs are sent. Client names and filenames
are not. If the AI step fails for any reason, curate() still returns a draft built
from local sharpness scores, marked with `fallback_reason` for the review page.
"""
import base64
import io
import json
from dataclasses import dataclass, field
from typing import Literal

import anthropic
from pydantic import BaseModel, ValidationError

from cull import load_rgb

MODEL = "claude-opus-5-5"
FALLBACK_BETA = "server-side-fallback-2026-07-01"
INPUT_PRICE_PER_TOKEN = 4 / 1_000_000
OUTPUT_PRICE_PER_TOKEN = 20 / 1_000_000

SCORING_BATCH_SIZE = 25
SCORING_EDGE = 1024
SEQUENCING_EDGE = 768
SEQUENCING_POOL = 60
MIN_PICKS, MAX_PICKS = 25, 40
RUNNERS_UP = 10
UNSCORED_SCORE = 5
JPEG_QUALITY = 80

Flag = Literal["closed_eyes", "awkward_expression", "unflattering_pose", "distracting_background", "missed_focus"]
BLOCKING_FLAGS = {"closed_eyes", "missed_focus"}

SYSTEM = """You are the assistant to a professional portrait and wedding photographer. \
You help choose which photos from a shoot go in the private preview slideshow sent to the client.

These photos are unedited straight from the camera. Do not mark a photo down for color, \
white balance, exposure that editing would fix, or lack of retouching. Judge what editing \
cannot fix: the moment, genuine emotion and expression, pose, composition and focus on the subject. \
Ask whether the people in the photo would be delighted to see it. Deliberate choices such as a \
silhouette, soft-focus mood or eyes closed in a kiss or a laugh are not flaws."""


class PhotoScore(BaseModel):
    id: str
    score: int
    flags: list[Flag]
    scene: str


class ScoreBatch(BaseModel):
    photos: list[PhotoScore]


class Sequence(BaseModel):
    order: list[str]
    runners_up: list[str]
    notes: str


class AIStepFailed(Exception):
    pass


@dataclass
class Draft:
    picks: list = field(default_factory=list)
    runners_up: list = field(default_factory=list)
    scores: dict = field(default_factory=dict)
    notes: str = ""
    fallback_reason: str | None = None
    warnings: list = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def estimated_cost(self):
        return self.input_tokens * INPUT_PRICE_PER_TOKEN + self.output_tokens * OUTPUT_PRICE_PER_TOKEN


def image_block(photo, edge):
    buffer = io.BytesIO()
    load_rgb(photo.path, edge).save(buffer, "JPEG", quality=JPEG_QUALITY)  # no exif= strips metadata
    data = base64.standard_b64encode(buffer.getvalue()).decode()
    return {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": data}}


def labelled_images(ids_and_photos, edge):
    content = []
    for photo_id, photo in ids_and_photos:
        content.append({"type": "text", "text": f"Photo {photo_id}:"})
        content.append(image_block(photo, edge))
    return content


def ask(client, draft, content, schema, effort):
    response = client.beta.messages.parse(
        model=MODEL,
        max_tokens=16000,
        betas=[FALLBACK_BETA],
        fallbacks="default",
        system=SYSTEM,
        output_config={"effort": effort},
        output_format=schema,
        messages=[{"role": "user", "content": content}],
    )
    draft.input_tokens += response.usage.input_tokens
    draft.output_tokens += response.usage.output_tokens
    if response.stop_reason in ("refusal", "max_tokens") or response.parsed_output is None:
        raise AIStepFailed(f"Claude stopped early ({response.stop_reason})")
    return response.parsed_output


def score_batch(client, draft, batch):
    ids = [photo_id for photo_id, _ in batch]
    instructions = (
        "Score each photo above from 1 (would disappoint the client) to 10 (a favorite they'd frame). "
        f"Return exactly one entry per photo, for these ids: {', '.join(ids)}. "
        "Add any flags that apply, and a short scene label such as 'creek, family of four' "
        "so similar shots can be told apart later."
    )
    result = ask(client, draft, [*labelled_images(batch, SCORING_EDGE), {"type": "text", "text": instructions}],
                 ScoreBatch, "medium")
    return {
        s.id: {"score": max(1, min(10, s.score)), "flags": s.flags, "scene": s.scene}
        for s in result.photos if s.id in ids
    }


def score_all(client, draft, by_id):
    """A failed batch costs only its own scores, unless every batch fails."""
    items = list(by_id.items())
    batches = [items[i:i + SCORING_BATCH_SIZE] for i in range(0, len(items), SCORING_BATCH_SIZE)]
    last_error = None
    for number, batch in enumerate(batches, 1):
        print(f"  scoring batch {number}/{len(batches)}")
        try:
            draft.scores.update(score_batch(client, draft, batch))
        except (AIStepFailed, ValidationError, ValueError, json.JSONDecodeError) as exc:
            last_error = exc
            draft.warnings.append(f"Scoring batch {number} failed: {exc}")
    if not draft.scores:
        raise AIStepFailed(f"no photos could be scored ({last_error})")
    for photo_id in by_id:
        if photo_id not in draft.scores:
            draft.scores[photo_id] = {"score": UNSCORED_SCORE, "flags": [], "scene": "not scored"}
            draft.warnings.append(f"{by_id[photo_id].name} wasn't scored by AI, so it got a neutral score.")


def rank(by_id, scores):
    """Best first: unblocked photos, then AI score, then local sharpness."""
    def key(photo_id):
        s = scores[photo_id]
        return (not BLOCKING_FLAGS.intersection(s["flags"]), s["score"], by_id[photo_id].sharpness)
    return sorted(by_id, key=key, reverse=True)


def sequence(client, draft, by_id, ranked, min_picks, max_picks):
    pool = ranked[:SEQUENCING_POOL]
    summary = "\n".join(
        f"{i}: score {draft.scores[i]['score']}, {draft.scores[i]['scene']}, "
        f"flags: {', '.join(draft.scores[i]['flags']) or 'none'}"
        for i in pool
    )
    instructions = f"""These are the strongest photos from one shoot. Earlier notes on each:
{summary}

Choose between {min_picks} and {max_picks} for the client's preview slideshow, in viewing order, so it plays like a story:
- Open with a photo that makes them stop and smile.
- Vary scene, pose and framing. Mix wide shots, portraits and details. Avoid back-to-back near-identical frames.
- Keep each set or location flowing together where that feels natural.
- End on the strongest emotional moment.

Put the ids in `order`. Put up to {RUNNERS_UP} next-best ids in `runners_up`, none repeated from `order`. \
Use `notes` for one or two sentences to the photographer on your reasoning."""
    pairs = [(i, by_id[i]) for i in pool]
    result = ask(client, draft, [*labelled_images(pairs, SEQUENCING_EDGE), {"type": "text", "text": instructions}],
                 Sequence, "high")

    known = set(pool)
    order = list(dict.fromkeys(i for i in result.order if i in known))[:max_picks]
    runners = [i for i in dict.fromkeys(result.runners_up) if i in known and i not in order]
    for photo_id in ranked:  # top up if the reply came back short
        if len(order) >= min_picks:
            break
        if photo_id not in order:
            order.append(photo_id)
            draft.warnings.append(f"{by_id[photo_id].name} was added to reach the minimum photo count.")
    runners = [i for i in runners if i not in order]
    for photo_id in ranked:
        if len(runners) >= RUNNERS_UP:
            break
        if photo_id not in order and photo_id not in runners:
            runners.append(photo_id)
    draft.notes = result.notes
    return order, runners[:RUNNERS_UP]


def local_fallback(draft, by_id, reason):
    """Sharpest photos in shooting order. by_id is already in shooting order."""
    draft.fallback_reason = reason
    best = sorted(by_id, key=lambda i: by_id[i].sharpness, reverse=True)
    chosen, spare = set(best[:MAX_PICKS]), best[MAX_PICKS:MAX_PICKS + RUNNERS_UP]
    draft.picks = [by_id[i] for i in by_id if i in chosen]
    draft.runners_up = [by_id[i] for i in spare]
    draft.scores = {}


def curate(candidates, client=None):
    draft = Draft()
    by_id = {f"P{n:03d}": photo for n, photo in enumerate(candidates, 1)}
    if not by_id:
        draft.fallback_reason = "No usable photos were left after the local filter."
        return draft
    min_picks, max_picks = min(MIN_PICKS, len(by_id)), min(MAX_PICKS, len(by_id))
    try:
        client = client or anthropic.Anthropic()
        score_all(client, draft, by_id)
        print("  choosing and ordering highlights")
        order, runners = sequence(client, draft, by_id, rank(by_id, draft.scores), min_picks, max_picks)
    except (anthropic.AnthropicError, AIStepFailed, ValidationError, ValueError, TypeError) as exc:
        # TypeError is how the SDK reports missing credentials at request time.
        local_fallback(draft, by_id, f"{type(exc).__name__}: {exc}")
        return draft
    draft.picks = [by_id[i] for i in order]
    draft.runners_up = [by_id[i] for i in runners]
    draft.scores = {by_id[i].name: s for i, s in draft.scores.items()}
    return draft
