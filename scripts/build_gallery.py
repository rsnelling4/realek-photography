import os, json
from PIL import Image, ImageOps

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ORIG = os.path.join(ROOT, "originals", "REALEK")
OUT = os.path.join(ROOT, "public", "gallery")
os.makedirs(os.path.join(OUT, "thumb"), exist_ok=True)

# (source path relative to ROOT, category, alt)
O = lambda shoot, f: os.path.join(ORIG, shoot, f)
P = lambda f: os.path.join(ROOT, "public", f)
photos = [
  # --- Little Ones
  (O("Amanda + Chad","IMG_2594 (1).jpg"), "Little Ones", "Grinning toddler in a straw hat and oversized sunglasses"),
  (O("Aspyne and Havyne","IMG_1171 (1).jpg"), "Little Ones", "Toddler taking steps across the grass at golden hour"),
  (O("Chamari Willis","IMG_5609.jpg"), "Little Ones", "Wide-eyed baby in a pink bow looking over a parent's shoulder"),
  (O("Amanda + Chad","IMG_2313.jpg"), "Little Ones", "Two little sisters cheek to cheek beside bright orange pumpkins"),
  (O("Aspyne and Havyne","IMG_1407.jpg"), "Little Ones", "Toddler with a rainbow number-one balloon in an open field"),
  (O("Amanda + Chad","IMG_3520.jpg"), "Little Ones", "Little girl beaming from a pile of golden corn"),
  (O("Milly","IMG_3641 (2).jpg"), "Little Ones", "Smiling baby in a lace headband held by her mother"),
  # --- Family
  (P("grass2.jpg"), "Family", "Two sisters sharing a secret in tall grass"),
  (O("Amanda + Chad","IMG_2677.jpg"), "Family", "Family of four laughing together against autumn trees"),
  (O("SanTarrah 10.30","IMG_5022.jpg"), "Family", "Maternity profile at the water's edge under a sunset sky"),
  (O("Aspyne and Havyne","IMG_1371 (1).jpg"), "Family", "Black-and-white family portrait on a picnic blanket"),
  (O("Chamari Willis","IMG_6036.jpg"), "Family", "Parents holding their baby beneath a willow tree"),
  (P("13.jpg"), "Family", "Brother and sister walking through a golden field"),
  (O("SanTarrah","_MG_1380(2).jpg"), "Family", "Maternity portrait of a family with two boys"),
  (O("Amanda + Chad","IMG_2910.jpg"), "Family", "Three generations standing together in a fall forest"),
  # --- Couples
  (O("Brittany + Kaleb","IMG_8863.jpg"), "Couples", "Couple laughing together in backlit golden-hour light"),
  (O("Saylor + Ryland","IMG_4085 (1).jpg"), "Couples", "Black-and-white portrait of a man kissing his partner's temple"),
  (O("Brittany + Kaleb","IMG_4431.jpg"), "Couples", "Couple standing in still blue water with their reflections below"),
  (O("Brittany + Kaleb","IMG_4007.jpg"), "Couples", "Couple posing on a sprawling tree root system"),
  (O("Ben + Melissa","IMG_9931.jpg"), "Couples", "Playful Halloween pumpkin-head portrait at dusk"),
  (O("Tashana & John","IMG_0721.jpg"), "Couples", "Couple embracing with a bouquet in the forest"),
  (O("Cassady + Mark","IMG_2725 (1).jpg"), "Couples", "Couple relaxing beneath a tree near a white barn"),
  # --- Weddings
  (O("Alexis + Charlie","IMG_8948.jpg"), "Weddings", "Groom dipping his bride for a kiss against a stone wall"),
  (O("Alexis + Charlie","IMG_8421.jpg"), "Weddings", "Bride with eyes closed, holding her veil against a dark backdrop"),
  (O("Alexis + Charlie","IMG_8809.jpg"), "Weddings", "First kiss under a draped arch with a river bridge behind"),
  (O("Overlook Wedding","IMG_5817 (1).jpg"), "Weddings", "Outdoor wedding ceremony under a floral arch"),
  (O("Alexis + Charlie","IMG_8909.jpg"), "Weddings", "Bride and groom forehead to forehead before a glowing wall of bottles"),
  (O("Riley Wedding","IMG_0368.jpg"), "Weddings", "Bride smiling in her veil and tiara by a window"),
  (O("Overlook Wedding","IMG_5887 (1).jpg"), "Weddings", "Black-and-white photo of a mother straightening her son's tie"),
  (O("Riley Wedding","IMG_9941.jpg"), "Weddings", "Black-and-white still life of the bride's lace boots and veil"),
  # --- Seniors
  (P("23.jpg"), "Seniors", "Senior holding her graduation cap in a gazebo"),
  (P("50.jpg"), "Seniors", "Senior beneath steel bridge trusses"),
  (P("45.jpg"), "Seniors", "Senior on a riverside walkway beneath a bridge"),
  (P("21.jpg"), "Seniors", "Graduation cap and heels still life"),
  (P("41.jpg"), "Seniors", "Senior sitting on a road with a yellow center line"),
  (P("24.jpg"), "Seniors", "Senior walking with her gown over her shoulder"),
  # --- Portraits
  (P("9.jpg"), "Portraits", "Girl in a cowboy hat holding a dandelion"),
  (P("6.jpg"), "Portraits", "Girl in a lace dress standing in a creek"),
  (P("15.jpg"), "Portraits", "Teen posing on a graffiti wall under a blue sky"),
  (P("12.jpg"), "Portraits", "Black-and-white portrait against a stone wall"),
  (O("Zoe","IMG_2053.jpg"), "Portraits", "Woman in a black dress leaning against a tree"),
  (P("4.jpg"), "Portraits", "Close-up portrait of a smiling girl"),
  (P("8.jpg"), "Portraits", "Girl with a cowboy hat behind her back under a bridge"),
]

def save(im, path, edge, q):
    im = im.copy(); im.thumbnail((edge, edge), Image.LANCZOS)
    im.save(path, "JPEG", quality=q, optimize=True, progressive=True)  # no exif= → metadata stripped
    return im.size

counters, entries = {}, []
for src, cat, alt in photos:
    slug = cat.lower().replace(" ", "-")
    counters[slug] = counters.get(slug, 0) + 1
    name = f"{slug}-{counters[slug]:02d}.jpg"
    im = ImageOps.exif_transpose(Image.open(src)).convert("RGB")
    w, h = save(im, os.path.join(OUT, name), 1600, 82)
    save(im, os.path.join(OUT, "thumb", name), 720, 78)
    entries.append({"src": f"gallery/{name}", "thumb": f"gallery/thumb/{name}", "w": w, "h": h, "category": cat, "alt": alt})

lines = ["// Generated from the photo picks — full-size images live in public/gallery, grid thumbnails in public/gallery/thumb.",
         "export const photos = ["]
for e in entries:
    lines.append(f"  {{ src: '{e['src']}', thumb: '{e['thumb']}', w: {e['w']}, h: {e['h']}, category: '{e['category']}', alt: {json.dumps(e['alt'])} }},")
lines.append("]")
os.makedirs(os.path.join(ROOT, "src", "data"), exist_ok=True)
open(os.path.join(ROOT, "src", "data", "gallery.js"), "w", encoding="utf-8").write("\n".join(lines) + "\n")
# Anything no longer picked comes off the site.
keep = {os.path.basename(e["src"]) for e in entries}
for folder in (OUT, os.path.join(OUT, "thumb")):
    for name in os.listdir(folder):
        if name.endswith(".jpg") and name not in keep:
            os.remove(os.path.join(folder, name))
print(len(entries), counters)
