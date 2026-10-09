ANCHORS = {
    "passport_no": (455, 72),
    "surname": (215, 93),
    "given_names": (215, 130),
    "sex": (375, 170),
    "dob": (455, 170),
    "place_of_birth": (215, 200),
    "place_of_issue": (300, 240),
    "date_of_issue": (270, 280),
    "date_of_expiry": (430, 280),
}

X_TOL = 60
Y_TOL = 18
MERGE_GAP = 50
MIN_CONF = 0.30


def clean(s):
    out = ""
    for c in s:
        if ord(c) < 128:
            out = out + c
    return out.replace(" ", "").upper().strip()


def digits(s):
    n = 0
    for c in s:
        if c.isdigit():
            n = n + 1
    return n


def merge_row(items):
    items = sorted(items, key=lambda i: (round(i["y1"] / 10), i["x1"]))
    merged = []
    for it in items:
        placed = False
        for m in merged:
            same_row = abs(m["y1"] - it["y1"]) <= 8
            gap = it["x1"] - m["x2"]
            left_done = digits(m["text"]) >= 8 or len(m["text"]) >= 8
            if same_row and 0 <= gap <= MERGE_GAP and not left_done:
                m["text"] = m["text"] + it["text"]
                m["x2"] = it["x2"]
                m["conf"] = min(m["conf"], it["conf"])
                placed = True
                break
        if not placed:
            merged.append(dict(it))
    return merged


def assign(items):
    items = [i for i in items if i["conf"] >= MIN_CONF]
    for it in items:
        it["text"] = clean(it["text"])
    items = [i for i in items if i["text"]]
    items = merge_row(items)

    fields = {}
    for key in ANCHORS:
        ax, ay = ANCHORS[key]
        best = None
        best_d = None
        for it in items:
            dx = abs(it["x1"] - ax)
            dy = abs(it["y1"] - ay)
            if dx <= X_TOL and dy <= Y_TOL:
                d = dx + dy * 2
                if best_d is None or d < best_d:
                    best_d = d
                    best = it
        if best:
            fields[key] = best["text"]
    for k in ["dob", "date_of_issue", "date_of_expiry"]:
        if k in fields:
            fields[k] = fix_date(fields[k])
    return fields


def fix_date(s):
    digits = ""
    for c in s:
        if c.isdigit():
            digits = digits + c
    if len(digits) == 8:
        return digits[0:2] + "/" + digits[2:4] + "/" + digits[4:8]
    return s


def find_mrz(items):
    lines = []
    for it in items:
        t = it["text"].upper().replace(" ", "")
        if len(t) >= 30 and t.count("<") >= 5:
            lines.append((it["y1"], t))
    lines.sort()
    return [l[1] for l in lines[:2]]


def extract_all(image_path):
    from ocr import read_all_boxes
    items = read_all_boxes(image_path)
    raw = [(round(i["y1"]), round(i["x1"]), i["text"], i["conf"]) for i in items]
    mrz = find_mrz(items)
    return assign(items), mrz, raw


def extract_fields(image_path):
    fields, mrz, raw = extract_all(image_path)
    return fields, raw