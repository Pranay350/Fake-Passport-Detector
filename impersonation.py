import os
os.environ["TF_USE_LEGACY_KERAS"] = "1"

import time
import threading
import cv2
import numpy as np
from liveness import check_liveness
from face_match import crop_document_face, match_faces

WINDOW = "liveness"
PASSPORT = "specimens/passport_clean.jpg"

MATCH_BELOW = 0.72
REJECT_ABOVE = 0.85

GREEN = (80, 200, 90)
RED = (60, 60, 220)
AMBER = (40, 175, 235)
WHITE = (245, 245, 245)


def band(distance):
    if distance < MATCH_BELOW:
        return "MATCH"
    if distance > REJECT_ABOVE:
        return "NO MATCH"
    return "REFER"


def dim(frame, amount=0.45):
    dark = np.zeros(frame.shape, dtype=np.uint8)
    return cv2.addWeighted(frame, 1 - amount, dark, amount, 0)


def banner(frame, text, colour, height=90):
    h, w = frame.shape[:2]
    top = int(h / 2) - height
    strip = frame[top:top + height, 0:w].copy()
    solid = np.full(strip.shape, colour, dtype=np.uint8)
    frame[top:top + height, 0:w] = cv2.addWeighted(strip, 0.25, solid, 0.75, 0)

    size = cv2.getTextSize(text, cv2.FONT_HERSHEY_DUPLEX, 1.6, 3)[0]
    x = int((w - size[0]) / 2)
    y = top + int(height / 2) + int(size[1] / 2)
    cv2.putText(frame, text, (x, y), cv2.FONT_HERSHEY_DUPLEX, 1.6, (255, 255, 255), 3)
    return frame


def line(frame, text, row, colour=WHITE, scale=0.65):
    h, w = frame.shape[:2]
    size = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, scale, 2)[0]
    x = int((w - size[0]) / 2)
    y = int(h / 2) + 40 + row * 34
    cv2.putText(frame, text, (x, y), cv2.FONT_HERSHEY_SIMPLEX, scale, colour, 2)


def sweep(frame, phase):
    h, w = frame.shape[:2]
    bar_w = int(w * 0.55)
    x0 = int((w - bar_w) / 2)
    y0 = int(h / 2) + 20
    cv2.rectangle(frame, (x0, y0), (x0 + bar_w, y0 + 6), (70, 70, 70), -1)
    chunk = int(bar_w * 0.25)
    pos = int((phase % 1.0) * (bar_w + chunk)) - chunk
    a = max(x0, x0 + pos)
    b = min(x0 + bar_w, x0 + pos + chunk)
    if b > a:
        cv2.rectangle(frame, (a, y0), (b, y0 + 6), (235, 190, 60), -1)


def run_match(passport_path, live_frame_path, out):
    try:
        doc_face = crop_document_face(passport_path)
    except Exception as e:
        out["decision"] = "REFER"
        out["reason"] = "no face on document"
        out["error"] = str(e)
        out["done"] = True
        return
    try:
        res = match_faces(doc_face, live_frame_path)
        d = float(res[1])
        out["distance"] = round(d, 3)
        out["decision"] = band(d)
        out["reason"] = "distance " + str(round(d, 3))
    except Exception as e:
        out["decision"] = "REFER"
        out["reason"] = "comparison failed"
        out["error"] = str(e)
    out["done"] = True


def main():
    passed, live_path, info = check_liveness(keep_window=True)

    frozen = None
    if os.path.exists("_last_frame.jpg"):
        frozen = cv2.imread("_last_frame.jpg")
    if frozen is None:
        frozen = np.full((480, 640, 3), 30, dtype=np.uint8)

    if not passed:
        screen = dim(frozen, 0.6)
        outcome = info.get("outcome", "REJECTED")
        colour = RED if outcome == "REJECT" else AMBER
        banner(screen, outcome, colour)
        line(screen, str(info.get("reason", "liveness check failed")), 0)
        line(screen, "blinks " + str(info.get("blinks")) + " of " + str(info.get("required")), 1)
        line(screen, "spoof " + str(info.get("passive")) + "  faces " + str(info.get("faces_seen")), 2)
        line(screen, "press any key to close", 4, (170, 170, 170), 0.5)
        cv2.imshow(WINDOW, screen)
        cv2.waitKey(0)
        cv2.destroyAllWindows()
        print(info)
        return

    out = {"done": False, "decision": None, "distance": None, "reason": ""}
    worker = threading.Thread(target=run_match, args=(PASSPORT, live_path, out))
    worker.start()

    start = time.time()
    while not out["done"]:
        screen = dim(frozen, 0.55)
        banner(screen, "VERIFYING", AMBER)
        dots = "." * (int((time.time() - start) * 2) % 4)
        line(screen, "comparing against document" + dots, 2)
        sweep(screen, (time.time() - start) * 0.6)
        cv2.imshow(WINDOW, screen)
        if cv2.waitKey(30) & 0xFF == ord("q"):
            break
    worker.join()

    decision = out["decision"]
    colour = GREEN
    if decision == "NO MATCH":
        colour = RED
    if decision == "REFER":
        colour = AMBER

    screen = dim(frozen, 0.55)
    banner(screen, decision, colour)
    line(screen, "liveness passed  -  blinks " + str(info.get("blinks")) +
         "  -  spoof " + str(info.get("passive_votes")), 0)
    line(screen, out["reason"], 1)
    line(screen, "press any key to close", 3, (170, 170, 170), 0.5)

    cv2.imshow(WINDOW, screen)
    cv2.waitKey(0)
    cv2.destroyAllWindows()

    print("")
    print("liveness :", info)
    print("distance :", out["distance"])
    print("DECISION :", decision)
    if out.get("error"):
        print("error    :", out["error"])


if __name__ == "__main__":
    main()