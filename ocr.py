import easyocr
import numpy as np
from PIL import Image

MRZ_CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789<"

_reader = None

def reader():
    global _reader
    if _reader is None:
        _reader = easyocr.Reader(["en"], gpu=False)
    return _reader

def read_mrz_region(image_path, top_fraction=0.80, upscale=3):
    im = Image.open(image_path).convert("RGB")
    w, h = im.size
    crop = im.crop((0, int(h * top_fraction), w, h))
    crop = crop.resize((crop.width * upscale, crop.height * upscale), Image.LANCZOS)

    out = reader().readtext(np.array(crop), allowlist=MRZ_CHARS, detail=1, paragraph=False)
    out.sort(key=lambda r: r[0][0][1])

    lines = []
    for box, text, conf in out:
        t = text.strip().replace(" ", "")
        if len(t) > 25:
            lines.append(t)
    return "\n".join(lines)


def read_all_boxes(image_path):
    im = Image.open(image_path).convert("RGB")
    out = reader().readtext(np.array(im), detail=1, paragraph=False)
    items = []
    for box, text, conf in out:
        xs = [p[0] for p in box]
        ys = [p[1] for p in box]
        items.append({
            "text": text.strip(),
            "x1": min(xs), "y1": min(ys), "x2": max(xs), "y2": max(ys),
            "conf": round(float(conf), 2)
        })
    return items


LABELS = {
    "passport_no": "passport",
    "surname": "surname",
    "given_names": "given",
    "dob": "birth",
    "place_of_birth": "place of birth",
    "place_of_issue": "place of issue",
    "date_of_issue": "issue",
    "date_of_expiry": "expiry",
    "sex": "sex",
}


def ascii_only(s):
    out = ""
    for c in s:
        if ord(c) < 128:
            out = out + c
    return out.strip()


def below(items, label_item, max_gap=45):
    best = None
    for it in items:
        if it is label_item:
            continue
        if it["y1"] <= label_item["y2"] - 3:
            continue
        if it["y1"] - label_item["y2"] > max_gap:
            continue
        overlap = min(it["x2"], label_item["x2"]) - max(it["x1"], label_item["x1"])
        if overlap <= 0:
            continue
        if best is None or it["y1"] < best["y1"]:
            best = it
    return best


def looks_like_date(s):
    parts = s.replace("-", "/").split("/")
    if len(parts) != 3:
        return False
    for p in parts:
        if not p.strip().isdigit():
            return False
    return True


def extract_fields(image_path):
    items = read_all_boxes(image_path)
    for it in items:
        it["text"] = ascii_only(it["text"])

    raw = [it["text"] for it in items]
    fields = {}

    for key in LABELS:
        want = LABELS[key]
        label_item = None
        for it in items:
            if want in it["text"].lower():
                label_item = it
                break
        if label_item is None:
            continue
        val = below(items, label_item)
        if val and val["text"]:
            fields[key] = val["text"].upper()

    for key in ["dob", "date_of_issue", "date_of_expiry"]:
        if key in fields and not looks_like_date(fields[key]):
            fields.pop(key)

    have = [k for k in ["dob", "date_of_issue", "date_of_expiry"] if k in fields]
    if len(have) < 3:
        dates = []
        for it in items:
            t = it["text"]
            if looks_like_date(t):
                dates.append(t)
        if len(dates) >= 3:
            def key_of(d):
                p = d.replace("-", "/").split("/")
                return (p[2], p[1], p[0])
            dates.sort(key=key_of)
            fields.setdefault("dob", dates[0])
            fields.setdefault("date_of_issue", dates[1])
            fields.setdefault("date_of_expiry", dates[-1])

    return fields, raw