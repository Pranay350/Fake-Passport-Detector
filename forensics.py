import numpy as np
from PIL import Image, ImageChops


def ela(path, quality=90):
    orig = Image.open(path).convert("RGB")
    orig.save("_tmp_ela.jpg", quality=quality)
    resaved = Image.open("_tmp_ela.jpg")
    diff = ImageChops.difference(orig, resaved)
    return np.array(diff).sum(axis=2).astype(float)


def jpeg_ghost(path, quality):
    orig = Image.open(path).convert("RGB")
    orig.save("_tmp_ghost.jpg", quality=quality)
    re = Image.open("_tmp_ghost.jpg").convert("RGB")
    a = np.array(orig).astype(float)
    b = np.array(re).astype(float)
    return ((a - b) ** 2).mean(axis=2)


def block_energy(diffmap, block=8):
    h, w = diffmap.shape
    hh = (h // block) * block
    ww = (w // block) * block
    m = diffmap[0:hh, 0:ww]
    m = m.reshape(hh // block, block, ww // block, block)
    return m.mean(axis=(1, 3))


def hotspot(scores, top=6):
    flat = scores.flatten()
    idx = np.argsort(flat)[-top:]
    out = []
    for i in idx:
        r = i // scores.shape[1]
        c = i % scores.shape[1]
        out.append((int(c * 8), int(r * 8), round(float(flat[i]), 2)))
    return out


FIELD_BOXES = {
    "passport_no": (452, 60, 584, 82),
    "surname": (215, 88, 420, 110),
    "given_names": (215, 125, 420, 147),
    "dob": (452, 168, 584, 189),
    "place_of_birth": (215, 198, 420, 220),
    "place_of_issue": (300, 238, 470, 260),
    "date_of_issue": (240, 275, 380, 297),
    "date_of_expiry": (430, 275, 570, 297),
    "photo": (48, 60, 190, 230),
}

DATE_FIELDS = ["dob", "date_of_issue", "date_of_expiry"]
OUTLIER_THRESHOLD = 1.2


def field_scores(path, quality=70):
    b = energy_map(path, quality)
    med = np.median(b[b > 0])
    out = {}
    for key in FIELD_BOXES:
        x1, y1, x2, y2 = FIELD_BOXES[key]
        r = b[y1 // 8:y2 // 8 + 1, x1 // 8:x2 // 8 + 1]
        if r.size:
            out[key] = round(float(r.mean() / (med + 1e-6)), 2)
    return out


_CACHE = {}


def energy_map(path, quality=70):
    key = (path, quality)
    if key not in _CACHE:
        _CACHE.clear()
        _CACHE[key] = block_energy(jpeg_ghost(path, quality))
    return _CACHE[key]


def find_edited_field(path, quality=70, want_map=False):
    scores = field_scores(path, quality)
    group = {}
    for k in DATE_FIELDS:
        if k in scores:
            group[k] = scores[k]
    if len(group) < 2:
        if want_map:
            return None, 0.0, scores, energy_map(path, quality)
        return None, 0.0, scores

    vals = sorted(group.values())
    baseline = vals[len(vals) // 2]
    worst = max(group, key=lambda k: group[k])
    ratio = round(group[worst] / (baseline + 1e-9), 2)

    hit = worst if ratio >= OUTLIER_THRESHOLD else None
    if want_map:
        return hit, ratio, scores, energy_map(path, quality)
    return hit, ratio, scores