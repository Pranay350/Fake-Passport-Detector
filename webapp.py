import os
os.environ["TF_USE_LEGACY_KERAS"] = "1"

import time
import shutil
try:
    import cv2
except ImportError:
    cv2 = None

from fastapi import FastAPI, UploadFile, File
from fastapi.responses import HTMLResponse, StreamingResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

try:
    from screen import screen_document
except ImportError:
    screen_document = None

try:
    from pipeline import band
except ImportError:
    band = None

app = FastAPI()
os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

STATE = {"doc": None, "person": None, "busy": False}
AUTH_STATE = {
    "current_officer": {
        "id": "OFFICER-742",
        "name": "Insp. R. Sharma",
        "role": "Border Control Officer",
        "station": "ICP-IN-RXL-04 (Raxaul)",
        "clearance": "Level 2 (Standard)",
        "logged_in": True,
        "shift_start": time.strftime("%H:%M:%S UTC")
    }
}
AUDIT_LOG = []
os.makedirs("output", exist_ok=True)
os.makedirs("uploads", exist_ok=True)


@app.on_event("startup")
def warmup():
    def load():
        try:
            from ocr import reader
            import numpy as np
            r = reader()
            r.readtext(np.zeros((80, 240, 3), dtype="uint8"))
            print("OCR ready")
        except Exception as e:
            print("OCR warmup failed:", e)
        try:
            from deepface import DeepFace
            import numpy as np, cv2
            warm = np.random.randint(80, 180, (200, 200, 3)).astype("uint8")
            cv2.imwrite("output/_warm.jpg", warm)
            try:
                DeepFace.extract_faces(img_path=warm, detector_backend="yunet",
                                       anti_spoofing=True, enforce_detection=False)
            except Exception:
                DeepFace.extract_faces(img_path=warm, detector_backend="opencv",
                                       anti_spoofing=True, enforce_detection=False)
            DeepFace.verify(img1_path="output/_warm.jpg", img2_path="output/_warm.jpg",
                            model_name="ArcFace", detector_backend="skip",
                            enforce_detection=False)
            print("face models ready")
        except Exception as e:
            print("face warmup partial:", e)
    threading.Thread(target=load, daemon=True).start()


@app.get("/", response_class=HTMLResponse)
def index():
    html = open("static/index.html", encoding="utf-8").read()
    return HTMLResponse(html, media_type="text/html; charset=utf-8")


@app.get("/api/auth/session")
def auth_session():
    off = AUTH_STATE.get("current_officer")
    if not off or not off.get("logged_in"):
        return JSONResponse({"authenticated": False}, status_code=401)
    return {"authenticated": True, "officer": off}


@app.post("/api/auth/login")
def auth_login(payload: dict):
    username = (payload.get("username") or "").strip()
    password = (payload.get("password") or "").strip()
    station = payload.get("station") or "ICP-IN-RXL-04 (Raxaul Outpost)"

    if username.lower() in ["admin", "supervisor"] and password in ["sih2026", "admin", "admin123"]:
        officer = {
            "id": "ADMIN-001",
            "name": "Supt. V. K. Nair",
            "role": "Forensics Administrator",
            "station": station,
            "clearance": "Level 3 (Supervisor / Forensic Oversight)",
            "logged_in": True,
            "shift_start": time.strftime("%H:%M:%S UTC")
        }
    elif username.lower() in ["officer", "officer-742", "ssb"] and password in ["ssb26188", "officer", "1234"]:
        officer = {
            "id": "OFFICER-742",
            "name": "Insp. R. Sharma",
            "role": "Border Control Officer",
            "station": station,
            "clearance": "Level 2 (Border Document Clearance)",
            "logged_in": True,
            "shift_start": time.strftime("%H:%M:%S UTC")
        }
    elif username:
        officer = {
            "id": username.upper(),
            "name": f"Officer {username.capitalize()}",
            "role": "Border Control Officer",
            "station": station,
            "clearance": "Level 2 (Field Officer)",
            "logged_in": True,
            "shift_start": time.strftime("%H:%M:%S UTC")
        }
    else:
        return JSONResponse({"error": "Invalid officer credentials"}, status_code=401)

    AUTH_STATE["current_officer"] = officer
    return {"authenticated": True, "officer": officer}


@app.post("/api/auth/logout")
def auth_logout():
    if AUTH_STATE.get("current_officer"):
        AUTH_STATE["current_officer"]["logged_in"] = False
    return {"authenticated": False}


@app.get("/api/admin/audit-log")
def get_audit_log():
    return {"logs": AUDIT_LOG}


@app.get("/api/specimens")
def list_specimens():
    manifest = [
        {
            "id": "passport_clean.jpg",
            "title": "Genuine Passport",
            "type": "clean",
            "tag": "ICAO 9303 Valid",
            "desc": "Genuine specimen. MRZ matches upper printed text; check digits 100% valid."
        },
        {
            "id": "forged_dob.jpg",
            "title": "DOB Tampered",
            "type": "tamper",
            "tag": "MRZ + Check Digit Mismatch",
            "desc": "Upper printed DOB altered; contradicts machine-readable zone arithmetic."
        },
        {
            "id": "forged_expiry.jpg",
            "title": "Expiry Date Extended",
            "type": "tamper",
            "tag": "Checksum & Validity Rule Failure",
            "desc": "Printed expiry year altered to extend validity; triggers ICAO mod-10 alert."
        },
        {
            "id": "forged_passportno.jpg",
            "title": "Passport No Altered",
            "type": "tamper",
            "tag": "Watchlist Forgery",
            "desc": "Passport number painted over; fails line-2 MRZ checksum check."
        },
        {
            "id": "forged_photo.jpg",
            "title": "Photo Substitution",
            "type": "tamper",
            "tag": "Biometric Impersonation",
            "desc": "Portrait replaced; fails live camera ArcFace biometric face matching."
        },
        {
            "id": "passport_tampered_dob.jpg",
            "title": "Tampered DOB Specimen",
            "type": "tamper",
            "tag": "Pixel Resampling Anomaly",
            "desc": "Tampered date of birth exhibiting localized JPEG ghost compression anomaly."
        }
    ]
    available = []
    for item in manifest:
        if os.path.exists(os.path.join("specimens", item["id"])):
            available.append(item)
    return {"specimens": available}


@app.post("/api/specimens/load")
def load_specimen(payload: dict):
    filename = payload.get("filename")
    if not filename:
        return JSONResponse({"error": "filename parameter missing"}, status_code=400)
    src = os.path.join("specimens", filename)
    if not os.path.exists(src):
        return JSONResponse({"error": f"Specimen {filename} not found"}, status_code=404)

    os.makedirs("uploads", exist_ok=True)
    dest = os.path.join("uploads", filename)
    shutil.copyfile(src, dest)
    STATE["doc"] = None
    STATE["person"] = None
    return {"path": dest, "filename": filename}


@app.post("/api/upload")
async def upload(file: UploadFile = File(...)):
    path = "uploads/" + file.filename
    with open(path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    STATE["doc"] = None
    STATE["person"] = None
    return {"path": path}


@app.post("/api/screen")
def api_screen(payload: dict):
    path = payload.get("path")
    if not path or not os.path.exists(path):
        return JSONResponse({"error": "file not found"}, status_code=400)

    if screen_document is None:
        return JSONResponse({"error": "Document screening engine requires CV/ML packages. Please install requirements.txt."}, status_code=500)

    r = screen_document(path)
    STATE["doc"] = r

    out = {
        "verdict": r["verdict"],
        "reason": r["reason"],
        "mrz_fields": r.get("mrz_fields", []),
        "printed": r.get("printed", {}),
        "mrz": r.get("mrz", []),
    }
    if r.get("text"):
        out["checksums"] = r["text"]["checksum_failures"]
        out["rules"] = r["text"]["rule_failures"]
    if r.get("pixel"):
        out["pixel_field"] = r["pixel"]["field"]
        out["pixel_ratio"] = r["pixel"]["ratio"]
    t = r.get("text") or {}
    out["expected_mrz"] = t.get("expected", [])
    out["mismatch"] = t.get("mismatch_positions", {"line1": [], "line2": []})
    out["ocr_note"] = r.get("ocr_note")
    out["sex_source"] = r.get("sex_source")
    if r.get("annotated"):
        out["annotated"] = "/file/" + os.path.basename(r["annotated"])
    if r.get("heatmap"):
        out["heatmap"] = "/file/" + os.path.basename(r["heatmap"])

    # Log to audit history
    officer_id = "OFFICER-742"
    if AUTH_STATE.get("current_officer"):
        officer_id = AUTH_STATE["current_officer"].get("id", "OFFICER-742")
    AUDIT_LOG.insert(0, {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "document": os.path.basename(path),
        "verdict": r["verdict"],
        "reason": r["reason"],
        "officer": officer_id
    })
    if len(AUDIT_LOG) > 60:
        AUDIT_LOG.pop()

    return out


@app.get("/font")
def font():
    for p in ["assets/OCRB.ttf", "OCRB.ttf"]:
        if os.path.exists(p):
            return FileResponse(p, media_type="font/ttf")
    return JSONResponse({"error": "font missing"}, status_code=404)


@app.get("/assets/OCRB.ttf")
def ocrb():
    for p in ["assets/OCRB.ttf", "OCRB.ttf"]:
        if os.path.exists(p):
            return FileResponse(p, media_type="font/ttf")
    return JSONResponse({"error": "font not found"}, status_code=404)


@app.get("/file/{name}")
def get_file(name: str):
    p = "output/" + name
    if os.path.exists(p):
        return FileResponse(p)
    return JSONResponse({"error": "not found"}, status_code=404)


def gen_frames():
    if cv2 is None:
        return
    try:
        from liveness import LATEST
    except ImportError:
        return
    blank = None
    while True:
        f = LATEST.get("frame")
        if f is None:
            time.sleep(0.05)
            continue
        ok, buf = cv2.imencode(".jpg", f)
        if ok:
            yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + buf.tobytes() + b"\r\n"
        time.sleep(0.03)


@app.get("/video")
def video():
    return StreamingResponse(gen_frames(),
                             media_type="multipart/x-mixed-replace; boundary=frame")


def run_person(path, store):
    try:
        from liveness import check_liveness, LATEST
        from face_match import crop_document_face, match_faces
    except Exception as e:
        store["stage"] = "done"
        store["face"] = "REFER"
        store["reason"] = f"Face model unavailable ({e})"
        store["done"] = True
        return

    store["stage"] = "liveness"
    passed, live_frame, info = check_liveness(show=False)
    store["liveness"] = info

    if not passed:
        store["stage"] = "done"
        store["face"] = "REJECT"
        store["reason"] = info.get("reason", "liveness failed")
        store["done"] = True
        return

    store["stage"] = "matching"
    try:
        doc_face = crop_document_face(path)
        res = match_faces(doc_face, live_frame)
        d = float(res[1])
        store["distance"] = round(d, 3)
        store["face"] = band(d)
        store["reason"] = "distance " + str(round(d, 3))
    except Exception as e:
        store["face"] = "REFER"
        store["reason"] = "face check failed"
    store["stage"] = "done"
    store["done"] = True


@app.post("/api/person")
def api_person(payload: dict):
    path = payload.get("path")
    if STATE["busy"]:
        return JSONResponse({"error": "already running"}, status_code=409)
    store = {"done": False, "stage": "starting"}
    STATE["person"] = store
    STATE["busy"] = True

    def worker():
        run_person(path, store)
        STATE["busy"] = False

    threading.Thread(target=worker, daemon=True).start()
    return {"started": True}


@app.get("/api/person/status")
def person_status():
    s = STATE["person"]
    if s is None:
        return {"done": False}
    return s


@app.get("/api/decision")
def decision():
    doc = STATE["doc"]
    person = STATE["person"]
    if doc is None:
        return {"decision": "REFER", "reason": "no document screened"}

    dv = doc["verdict"]
    if dv == "FORGED":
        return {"decision": "REJECT", "reason": "document is forged"}
    if person is None or not person.get("done"):
        return {"decision": "PENDING", "reason": "traveller not verified"}
    if person.get("face") == "REJECT":
        return {"decision": "REJECT", "reason": "presentation attack detected"}
    if person.get("face") == "NO_MATCH":
        return {"decision": "REJECT", "reason": "traveller does not match document"}
    if dv == "SUSPICIOUS":
        return {"decision": "REFER", "reason": "document inconsistencies found"}
    if dv == "REFER":
        return {"decision": "REFER", "reason": "document could not be read"}
    if person.get("face") == "REFER":
        return {"decision": "REFER", "reason": "face verification inconclusive"}
    return {"decision": "CLEAR", "reason": "document and traveller verified"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)