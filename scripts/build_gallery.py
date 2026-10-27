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
  (O("Aspyne and Havyne","IMG_1083 (1).jpg"), "Little Ones", "Black-and-white portrait of a baby lying on a knit blanket"),
  (O("Aspyne and Havyne","IMG_1114.jpg"), "Little Ones", "Mother cradling her baby in a red gingham dress"),
  (O("Aspyne and Havyne","IMG_1171 (1).jpg"), "Little Ones", "Toddler taking steps across the grass at golden hour"),
  (O("Aspyne and Havyne","IMG_1407.jpg"), "Little Ones", "Toddler with a rainbow number-one balloon in an open field"),
  (O("Aspyne and Havyne","IMG_1681.jpg"), "Little Ones", "Baby enjoying a first-birthday cake smash in a meadow"),
  (O("Chamari Willis","IMG_5184.jpg"), "Little Ones", "Mother laughing with her baby in a pink floral dress"),
  (O("Chamari Willis","IMG_5550 (1).jpg"), "Little Ones", "Baby with a pink bow looking over a parent's shoulder"),
  (O("Milly","IMG_3482 (1).jpg"), "Little Ones", "Black-and-white portrait of parents holding their baby girl"),
  (O("Milly","IMG_3641 (2).jpg"), "Little Ones", "Smiling baby in a lace headband held by her mother"),
  (O("Milly","IMG_3655.jpg"), "Little Ones", "Mother lifting her baby girl into the sunlight"),
  # --- Family
  (O("Aspyne and Havyne","IMG_1234.jpg"), "Family", "Family of four standing in a creek at sunset"),
  (O("Aspyne and Havyne","IMG_1371 (1).jpg"), "Family", "Black-and-white family portrait on a picnic blanket"),
  (O("Chamari Willis","IMG_6036.jpg"), "Family", "Parents holding their baby beneath a willow tree"),
  (O("Chamari Willis","IMG_6870.jpg"), "Family", "Parents smiling with their baby girl outdoors"),
  (O("Knox Family","IMG_3087.jpg"), "Family", "Young boy in a plaid shirt standing in a grassy field"),
  (O("Knox Family","IMG_3170 (1).jpg"), "Family", "Sepia portrait of a young boy beside a tree"),
  (O("Knox Family","IMG_3259 (1).jpg"), "Family", "Parents sharing a kiss in an open field"),
  (O("Knox Family","IMG_3294.jpg"), "Family", "Boy standing on a large rock in the woods"),
  (O("Regina","1786111200278.jpg"), "Family", "Mother and son hugging by the river with a bridge behind them"),
  (O("SanTarrah","_MG_1336 (1).jpg"), "Family", "Boy balancing on a fallen log in the woods"),
  (O("SanTarrah","_MG_1379.jpg"), "Family", "Maternity photo of a son touching his mother's painted belly"),
  (O("SanTarrah","_MG_1380(2).jpg"), "Family", "Maternity portrait of a family with two boys"),
  (O("Zander & Denver","IMG_8521.jpg"), "Family", "Toddler and his dad laughing together in the woods"),
  (O("Zander & Denver","IMG_8548.jpg"), "Family", "Toddler running through autumn leaves"),
  (O("Zander & Denver","IMG_8605 (1).jpg"), "Family", "Black-and-white close-up of a toddler's excited face"),
  (O("Zander & Denver","IMG_8619.jpg"), "Family", "Mother lifting her toddler toward the trees"),
  (P("13.jpg"), "Family", "Brother and sister walking through a golden field"),
  (P("grass2.jpg"), "Family", "Two sisters sharing a secret in tall grass"),
  # --- Couples
  (O("Ben + Melissa","IMG_9872.jpg"), "Couples", "Couple leaning on a boardwalk railing by a river bridge"),
  (O("Brittany + Kaleb","IMG_4002.jpg"), "Couples", "Couple embracing among tangled tree roots"),
  (O("Brittany + Kaleb","IMG_4007.jpg"), "Couples", "Couple posing on a sprawling tree root system"),
  (O("Brittany + Kaleb","IMG_4132 (1).jpg"), "Couples", "Black-and-white portrait of a couple in a field"),
  (O("Brittany + Kaleb","IMG_8818.jpg"), "Couples", "Engagement ring detail with the couple blurred behind"),
  (O("Brittany + Kaleb","IMG_8863.jpg"), "Couples", "Couple laughing together in backlit golden-hour light"),
  (O("Cassady + Mark","IMG_2648.jpg"), "Couples", "Couple holding hands while crossing a shallow creek"),
  (O("Cassady + Mark","IMG_2725 (1).jpg"), "Couples", "Couple relaxing beneath a tree near a white barn"),
  (O("Cassady + Mark","IMG_2767.jpg"), "Couples", "Close-up of a couple kissing with the engagement ring visible"),
  (O("Saylor + Ryland","IMG_3897.jpg"), "Couples", "Couple wrapped in a plaid blanket beside a willow tree"),
  (O("Saylor + Ryland","IMG_4085 (1).jpg"), "Couples", "Black-and-white portrait of a man kissing his partner's temple"),
  (O("Saylor + Ryland","IMG_4100.jpg"), "Couples", "Couple sitting on a blanket by a pond"),
  (O("Saylor + Ryland","IMG_4115.jpg"), "Couples", "Engagement ring shown off during a kiss"),
  (O("Tashana & John","IMG_0690.jpg"), "Couples", "Couple smiling together among green leaves"),
  (O("Tashana & John","IMG_0721.jpg"), "Couples", "Couple embracing with a bouquet in the forest"),
  (O("Ben + Melissa","IMG_9931.jpg"), "Couples", "Playful Halloween pumpkin-head portrait at dusk"),
  (O("Ben + Melissa","IMG_9976.jpg"), "Couples", "Halloween pumpkin-head couple portrait at twilight"),
  # --- Weddings
  (O("Overlook Wedding","IMG_5523.jpg"), "Weddings", "Bride holding her bouquet on a deck overlooking the river"),
  (O("Overlook Wedding","IMG_5817 (1).jpg"), "Weddings", "Outdoor wedding ceremony under a floral arch"),
  (O("Overlook Wedding","IMG_6417.jpg"), "Weddings", "Wedding party walking down the aisle"),
  (O("Overlook Wedding","IMG_7316.jpg"), "Weddings", "Wedding guest in profile beside a floral centerpiece at sunset"),
  (O("Riley Wedding","IMG_0329 (1).jpg"), "Weddings", "Black-and-white photo of a bride having her veil placed"),
  (O("Riley Wedding","IMG_0368.jpg"), "Weddings", "Bride smiling in her veil and tiara by a window"),
  (O("Riley Wedding","IMG_2285 (1).jpg"), "Weddings", "Black-and-white portrait of bride and groom resting under a tree"),
  (O("Riley Wedding","IMG_2604.jpg"), "Weddings", "Engraved wedding cake knife detail"),
  (O("Riley Wedding","IMG_9941.jpg"), "Weddings", "Black-and-white still life of the bride's lace boots and veil"),
  # --- Seniors
  (P("20.jpg"), "Seniors", "Senior in a white dress holding her graduation gown"),
  (P("21.jpg"), "Seniors", "Graduation cap and heels still life"),
  (P("22.jpg"), "Seniors", "Senior sitting in a wooden gazebo"),
  (P("23.jpg"), "Seniors", "Senior holding her graduation cap in a gazebo"),
  (P("24.jpg"), "Seniors", "Senior walking with her gown over her shoulder"),
  (P("25.jpg"), "Seniors", "Senior on a park path beside her cap and heels"),
  (P("41.jpg"), "Seniors", "Senior sitting on a road with a yellow center line"),
  (P("42.jpg"), "Seniors", "Senior against a graffiti wall"),
  (P("43.jpg"), "Seniors", "Senior leaning against a concrete wall"),
  (P("44.jpg"), "Seniors", "Senior beneath a bridge at dusk"),
  (P("45.jpg"), "Seniors", "Senior on a riverside walkway beneath a bridge"),
  (P("46.jpg"), "Seniors", "Senior sitting on stairs at sunset"),
  (P("47.jpg"), "Seniors", "Senior by the river with a bridge behind him"),
  (P("48.jpg"), "Seniors", "Senior sitting beneath an old iron bridge"),
  (P("49.jpg"), "Seniors", "Senior in cap and gown on a boardwalk"),
  (P("50.jpg"), "Seniors", "Senior beneath steel bridge trusses"),
  # --- Portraits
  (P("1.jpg"), "Portraits", "Girl in a lace dress leaning on a lamppost"),
  (P("2.jpg"), "Portraits", "Girl in a lace dress sitting on a rock in the woods"),
  (P("3.jpg"), "Portraits", "Girl in a lace dress sitting on a log looking up"),
  (P("4.jpg"), "Portraits", "Close-up portrait of a smiling girl"),
  (P("5.jpg"), "Portraits", "Girl in a lace dress standing by a creek"),
  (P("6.jpg"), "Portraits", "Girl in a lace dress standing in a creek"),
  (P("7.jpg"), "Portraits", "Girl in a denim jacket walking through tall grass"),
  (P("8.jpg"), "Portraits", "Girl with a cowboy hat behind her back under a bridge"),
  (P("9.jpg"), "Portraits", "Girl in a cowboy hat holding a dandelion"),
  (P("10.jpg"), "Portraits", "Girl in a cowboy hat blowing a dandelion"),
  (P("11.jpg"), "Portraits", "Silhouette under a bridge by the creek"),
  (P("12.jpg"), "Portraits", "Black-and-white portrait against a stone wall"),
  (P("14.jpg"), "Portraits", "Teen in sunglasses against dramatic clouds"),
  (P("15.jpg"), "Portraits", "Teen posing on a graffiti wall under a blue sky"),
  (P("16.jpg"), "Portraits", "Teen reclining on a graffiti wall"),
  (P("17.jpg"), "Portraits", "Teen in sunglasses against a deep blue sky"),
  (P("18.jpg"), "Portraits", "Teen posing on a painted ramp under dramatic clouds"),
  (O("Zoe","IMG_1795.jpg"), "Portraits", "Woman standing beneath an iron bridge"),
  (O("Zoe","IMG_1960 (1).jpg"), "Portraits", "Woman in a black dress smiling in the woods"),
  (O("Zoe","IMG_2053.jpg"), "Portraits", "Woman in a black dress leaning against a tree"),
  (O("Zoe","IMG_2333.jpg"), "Portraits", "Woman in a pink top standing in a creek"),
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
print(len(entries), counters)
