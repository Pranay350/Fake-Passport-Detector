from PIL import Image, ImageDraw, ImageFont

CLEAN = "specimens/passport_clean.jpg"
FONT = "assets/OCRB.ttf"
FACE = "assets/fakepfp.jpg"
QUALITY = 90

EDITS = {
    "dob": {"box": (452, 168, 584, 189), "text": "01/03/2010"},
    "expiry": {"box": (422, 281, 584, 300), "text": "15/03/2035"},
    "passportno": {"box": (430, 70, 570, 92), "text": "K9999999"},
    "photo": {"box": (48, 60, 190, 230), "image": FACE},
}


def paper_colour(im, box):
    x1, y1 = box[0], box[1]
    return im.getpixel((max(0, x1 - 3), max(0, y1 - 3)))


def make_one(name, spec):
    im = Image.open(CLEAN).convert("RGB")
    box = spec["box"]

    if "image" in spec:
        patch = Image.open(spec["image"]).convert("RGB")
        patch = patch.resize((box[2] - box[0], box[3] - box[1]))
        im.paste(patch, (box[0], box[1]))
    else:
        d = ImageDraw.Draw(im)
        d.rectangle(box, fill=paper_colour(im, box))
        f = ImageFont.truetype(FONT, 15)
        d.text((box[0], box[1]), spec["text"], font=f, fill=(45, 45, 45))

    out = "specimens/forged_" + name + ".jpg"
    im.save(out, quality=QUALITY)

    mask = Image.new("L", im.size, 0)
    ImageDraw.Draw(mask).rectangle(box, fill=255)
    mask.save("specimens/mask_" + name + ".png")
    return out


def make_control():
    im = Image.open(CLEAN).convert("RGB")
    im.save("specimens/resaved_clean.jpg", quality=QUALITY)
    Image.new("L", im.size, 0).save("specimens/mask_clean.png")
    return "specimens/resaved_clean.jpg"


if __name__ == "__main__":
    for name in EDITS:
        print("made", make_one(name, EDITS[name]))
    print("made", make_control())