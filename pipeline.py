import os
os.environ["TF_USE_LEGACY_KERAS"] = "1"

from screen import screen_document

MATCH_BELOW = 0.72
REJECT_ABOVE = 0.85


def band(distance):
    if distance < MATCH_BELOW:
        return "MATCH"
    if distance > REJECT_ABOVE:
        return "NO_MATCH"
    return "REFER"


def check_person(image_path):
    from liveness import check_liveness
    from face_match import crop_document_face, match_faces

    out = {"liveness": None, "distance": None, "face": None, "reason": None}

    passed, live_frame, info = check_liveness()
    out["liveness"] = info
    if not passed:
        out["face"] = "REJECT"
        out["reason"] = info.get("reason", "liveness failed")
        return out

    try:
        doc_face = crop_document_face(image_path)
    except Exception as e:
        out["face"] = "REFER"
        out["reason"] = "no face found on document"
        return out

    try:
        res = match_faces(doc_face, live_frame)
        d = float(res[1])
    except Exception as e:
        out["face"] = "REFER"
        out["reason"] = "face comparison failed"
        return out

    out["distance"] = round(d, 3)
    out["face"] = band(d)
    out["reason"] = "distance " + str(round(d, 3))
    return out


def decide(doc_verdict, person):
    if doc_verdict == "FORGED":
        return "REJECT", "document is forged"
    if person is None:
        if doc_verdict == "SUSPICIOUS":
            return "REFER", "document inconsistencies found"
        if doc_verdict == "REFER":
            return "REFER", "document could not be read"
        return "CLEAR", "document passed all checks"

    if person["face"] == "REJECT":
        return "REJECT", "presentation attack detected"
    if person["face"] == "NO_MATCH":
        return "REJECT", "traveller does not match document"
    if doc_verdict == "SUSPICIOUS":
        return "REFER", "document inconsistencies found"
    if doc_verdict == "REFER":
        return "REFER", "document could not be read"
    if person["face"] == "REFER":
        return "REFER", "face verification inconclusive"
    return "CLEAR", "document and traveller verified"


def run_screening(image_path, verify_person=True, today=None):
    result = {"image": image_path}

    doc = screen_document(image_path, today=today)
    result["document"] = doc

    person = None
    if verify_person and doc["verdict"] != "FORGED":
        person = check_person(image_path)
    result["person"] = person

    decision, reason = decide(doc["verdict"], person)
    result["decision"] = decision
    result["reason"] = reason
    return result


def show(r):
    doc = r["document"]
    print("")
    print("=" * 52)
    print("DOCUMENT :", r["image"])
    print("=" * 52)
    print("document verdict :", doc["verdict"], "-", doc["reason"])
    if doc.get("text"):
        t = doc["text"]
        if t["fields"]:
            print("  MRZ mismatch  :", ", ".join(t["fields"]))
        for f in t["checksum_failures"]:
            print("  check digit   :", f["field"], "printed", f["printed"], "computed", f["computed"])
        for f in t["rule_failures"]:
            print("  rule broken   :", f["rule"])
    if doc.get("pixel") and doc["pixel"]["field"]:
        print("  pixel anomaly :", doc["pixel"]["field"], "ratio", doc["pixel"]["ratio"])

    p = r["person"]
    if p is None:
        print("traveller        : not checked")
    else:
        lv = p["liveness"] or {}
        print("traveller        :", p["face"], "-", p["reason"])
        print("  liveness      : blinks", lv.get("blinks"), "of", lv.get("required"),
              "| spoof", lv.get("passive"), "| faces", lv.get("faces_seen"))

    print("-" * 52)
    print("DECISION :", r["decision"])
    print("REASON   :", r["reason"])
    if doc.get("annotated"):
        print("evidence :", doc["annotated"])
    print("")


if __name__ == "__main__":
    import sys
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    no_cam = "--no-camera" in sys.argv

    files = args or ["specimens/passport_clean.jpg"]
    for f in files:
        try:
            show(run_screening(f, verify_person=not no_cam))
        except Exception as e:
            print(f, "FAILED:", e)