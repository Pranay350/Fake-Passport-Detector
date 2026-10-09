import cv2
import numpy as np
from forensics import jpeg_ghost, block_energy, FIELD_BOXES

RED = (60, 60, 220)
AMBER = (40, 175, 235)
GREEN = (80, 200, 90)


def heatmap(image_path, out_path, quality=70, alpha=0.4, cached=None):
    b = cached if cached is not None else block_energy(jpeg_ghost(image_path, quality))
    b = cv2.GaussianBlur(b.astype("float32"), (5, 5), 0)
    b = b / (b.max() + 1e-9)

    img = cv2.imread(image_path)
    h, w = img.shape[:2]
    heat = np.clip(b * 255, 0, 255).astype("uint8")
    heat = cv2.resize(heat, (w, h), interpolation=cv2.INTER_LINEAR)
    colour = cv2.applyColorMap(heat, cv2.COLORMAP_JET)
    out = cv2.addWeighted(img, 1 - alpha, colour, alpha, 0)
    cv2.imwrite(out_path, out)
    return out_path


def box_field(img, field, colour, label):
    if field not in FIELD_BOXES:
        return
    x1, y1, x2, y2 = FIELD_BOXES[field]
    cv2.rectangle(img, (x1 - 4, y1 - 4), (x2 + 4, y2 + 4), colour, 2)
    cv2.putText(img, label, (x1 - 4, y1 - 9), cv2.FONT_HERSHEY_SIMPLEX, 0.45, colour, 1)


def annotate(image_path, out_path, flagged_fields, mrz_fields=None, verdict=None):
    img = cv2.imread(image_path)
    if img is None:
        return None

    for f in flagged_fields:
        box_field(img, f, AMBER, "pixel anomaly")

    if mrz_fields:
        for f in mrz_fields:
            box_field(img, f, RED, "MRZ mismatch")

    if verdict:
        colour = RED
        if verdict in ("CLEAN", "CONSISTENT", "CLEAR"):
            colour = GREEN
        elif verdict in ("SUSPICIOUS", "REFER"):
            colour = AMBER
        h, w = img.shape[:2]
        cv2.rectangle(img, (0, 0), (w, 30), colour, -1)
        cv2.putText(img, verdict, (10, 22), cv2.FONT_HERSHEY_DUPLEX, 0.7, (255, 255, 255), 2)

    cv2.imwrite(out_path, img)
    return out_path