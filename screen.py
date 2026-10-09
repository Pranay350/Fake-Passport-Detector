import os
from tamper import screen, expected_mrz
from forensics import find_edited_field
from mrz_read import read_and_resolve
import annotate

MRZ_TO_FIELD = {
    "dob": "dob", "dob_cd": "dob",
    "expiry": "date_of_expiry", "expiry_cd": "date_of_expiry",
    "passport_no": "passport_no", "passport_cd": "passport_no",
    "sex": "sex", "composite_cd": None, "optional_cd": None,
    "nationality": None, "optional": None,
}


def read_document(image_path):
    from extract import extract_all
    fields, mrz_raw, raw = extract_all(image_path)
    l1, l2, verified, note = read_and_resolve("\n".join(mrz_raw), fields.get("passport_no"))
    return fields, [l1, l2], verified, note, raw


def combine(text_report, pixel_field, pixel_ratio):
    text_bad = text_report["verdict"] in ("TAMPERED", "SUSPICIOUS")
    pixel_bad = pixel_field is not None

    if text_report["verdict"] == "TAMPERED" and pixel_bad:
        return "FORGED", "text and pixel evidence agree"
    if text_report["verdict"] == "TAMPERED":
        return "FORGED", "document data is internally inconsistent"
    if pixel_bad:
        return "SUSPICIOUS", "pixel evidence of editing in " + pixel_field
    if text_report["verdict"] == "SUSPICIOUS":
        return "SUSPICIOUS", "document rules violated"
    return "CLEAN", "no inconsistency found"


def screen_document(image_path, printed=None, mrz_lines=None, today=None, write_images=True):
    result = {"image": image_path}

    if printed is None or mrz_lines is None:
        printed, mrz_lines, verified, note, raw = read_document(image_path)
        result["ocr_verified"] = verified
        result["ocr_note"] = note
        result["ocr_raw"] = raw
    result["printed"] = printed
    result["mrz"] = mrz_lines

    if not mrz_lines or len(mrz_lines) < 2 or not mrz_lines[0] or not mrz_lines[1]:
        result["verdict"] = "REFER"
        result["reason"] = "machine-readable zone could not be read"
        result["mrz"] = mrz_lines
        result["mrz_fields"] = []
        return result

    if not printed.get("sex") and mrz_lines and len(mrz_lines) > 1:
        printed = dict(printed)
        printed["sex"] = mrz_lines[1][20]
        result["sex_source"] = "mrz (not printed, cross-check unavailable)"

    needed = ["surname", "given_names", "passport_no", "dob",
              "date_of_issue", "date_of_expiry"]
    missing = [k for k in needed if not printed.get(k)]
    if missing:
        result["verdict"] = "REFER"
        result["reason"] = "could not read fields: " + ", ".join(missing)
        result["missing"] = missing
        return result

    text_report = screen(printed, mrz_lines, today)
    result["text"] = text_report

    pixel_field, ratio, scores, scores_map = find_edited_field(image_path, want_map=True)
    result["pixel"] = {"field": pixel_field, "ratio": ratio, "scores": scores}

    verdict, reason = combine(text_report, pixel_field, ratio)
    result["verdict"] = verdict
    result["reason"] = reason

    mrz_hits = []
    for f in text_report["fields"]:
        mapped = MRZ_TO_FIELD.get(f)
        if mapped and mapped not in mrz_hits:
            mrz_hits.append(mapped)
    result["mrz_fields"] = mrz_hits

    if write_images:
        os.makedirs("output", exist_ok=True)
        base = os.path.basename(image_path).replace(".jpg", "")
        flagged = [pixel_field] if pixel_field else []
        result["annotated"] = annotate.annotate(
            image_path, "output/" + base + "_annotated.jpg",
            flagged, mrz_hits, verdict)
        result["heatmap"] = annotate.heatmap(
            image_path, "output/" + base + "_heatmap.jpg", cached=scores_map)

    return result


def show(r):
    print("")
    print("document :", r["image"])
    print("VERDICT  :", r["verdict"], "-", r["reason"])
    if r.get("missing"):
        print("fields   :", r.get("printed"))
        return
    print("text     :", r["text"]["verdict"], r["text"]["fields"])
    for f in r["text"]["checksum_failures"]:
        print("   check digit:", f["field"], "printed", f["printed"], "computed", f["computed"])
    for f in r["text"]["rule_failures"]:
        print("   rule:", f["rule"], "-", f["detail"])
    print("pixel    :", r["pixel"]["field"], "ratio", r["pixel"]["ratio"])
    if r.get("sex_source"):
        print("note     : sex taken from", r["sex_source"])
    if r.get("annotated"):
        print("images   :", r["annotated"], "|", r["heatmap"])


if __name__ == "__main__":
    import sys
    files = sys.argv[1:] or [
        "specimens/passport_clean.jpg",
        "specimens/forged_dob.jpg",
        "specimens/forged_expiry.jpg",
        "specimens/forged_passportno.jpg",
        "specimens/forged_photo.jpg",
    ]
    for f in files:
        try:
            show(screen_document(f))
        except Exception as e:
            print("")
            print(f, "FAILED:", e)