import os
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from mrz.generator.td3 import TD3CodeGenerator

TEMPLATE = "assets/demo_passport.jpg"
FONT = "assets/OCRB.ttf"
PASTE_FACE = False

INK = (42, 42, 42)
FIELD_SIZE = 15
MRZ_SIZE = 14

FACE_BOX = (38, 60, 175, 235)
GHOST_BOX = (390, 120, 520, 300)

POS = {
    "passport_no": (455, 72),
    "surname": (215, 93),
    "given_names": (215, 130),
    "sex": (375, 170),
    "dob": (455, 170),
    "place_of_birth": (215, 200),
    "place_of_issue": (300, 240),
    "date_of_issue": (270, 280),
    "date_of_expiry": (430, 280),
    "mrz1": (25, 330),
    "mrz2": (25, 358),
}


def to_mrz_date(printed):
    d, m, y = printed.split("/")
    return y[2:] + m + d


def build_mrz(f):
    dob = f.get("dob_mrz") or to_mrz_date(f["dob"])
    exp = f.get("expiry_mrz") or to_mrz_date(f["date_of_expiry"])
    code = TD3CodeGenerator(
        "P", "IND",
        f["surname"], f["given_names"], f["passport_no"], "IND",
        dob, f["sex"], exp, ""
    )
    return str(code).split("\n")


def paste_face(doc, face_path):
    face = Image.open(face_path).convert("RGB")
    w = FACE_BOX[2] - FACE_BOX[0]
    h = FACE_BOX[3] - FACE_BOX[1]
    face = face.resize((w, h))
    doc.paste(face, (FACE_BOX[0], FACE_BOX[1]))


def draw_text(doc, fields, mrz_lines):
    layer = Image.new("RGBA", doc.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    small = ImageFont.truetype(FONT, FIELD_SIZE)
    big = ImageFont.truetype(FONT, MRZ_SIZE)

    for key in POS:
        if key == "mrz1":
            d.text(POS[key], mrz_lines[0], font=big, fill=INK)
        elif key == "mrz2":
            d.text(POS[key], mrz_lines[1], font=big, fill=INK)
        else:
            d.text(POS[key], str(fields[key]).upper(), font=small, fill=INK)

    layer = layer.filter(ImageFilter.GaussianBlur(0.4))
    doc.paste(layer, (0, 0), layer)


def watermark(doc):
    layer = Image.new("RGBA", doc.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    f = ImageFont.truetype(FONT, 46)
    d.text((70, 190), "SPECIMEN", font=f, fill=(120, 120, 120, 90))
    doc.paste(layer, (0, 0), layer)


def crop_data_page(img):
    w, h = img.size
    return img.crop((0, h // 2, w, h))


def generate(face_path, fields, output_path):
    doc = Image.open(TEMPLATE).convert("RGB")
    doc = crop_data_page(doc)
    if PASTE_FACE:
        paste_face(doc, face_path)
    draw_text(doc, fields, build_mrz(fields))
    watermark(doc)
    doc.save(output_path, quality=90)
    return output_path


def calibrate():
    doc = Image.open(TEMPLATE).convert("RGB")
    doc = crop_data_page(doc)
    d = ImageDraw.Draw(doc)
    d.rectangle(FACE_BOX, outline=(255, 0, 0), width=2)
    for key in POS:
        x, y = POS[key]
        d.rectangle([x - 2, y - 2, x + 2, y + 2], fill=(255, 0, 0))
        d.text((x + 6, y), key, fill=(255, 0, 0))
    doc.save("output/calibration.png")
    print("saved output/calibration.png")


for f in [TEMPLATE, FONT]:
    if not os.path.exists(f):
        print("MISSING:", f)
        raise SystemExit

if __name__ == "__main__":
    person = {
        "surname": "SINGH",
        "given_names": "ARJUN",
        "passport_no": "K1234567",
        "sex": "M",
        "dob": "01/03/1998",
        "place_of_birth": "PATIALA",
        "place_of_issue": "CHANDIGARH",
        "date_of_issue": "16/03/2020",
        "date_of_expiry": "15/03/2030",
    }

    calibrate()
    generate("assets/fakepfp.jpg", person, "specimens/passport_clean.jpg")
    print("done")