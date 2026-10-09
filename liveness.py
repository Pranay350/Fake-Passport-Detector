import os
import time
import random
import urllib.request
import cv2
import numpy as np
import mediapipe as mp
from mediapipe.tasks import python as mpp
from mediapipe.tasks.python import vision
from deepface import DeepFace

MODEL = "face_landmarker.task"
MODEL_URL = "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task"

LEFT_EYE = [362, 385, 387, 263, 373, 380]
RIGHT_EYE = [33, 160, 158, 133, 153, 144]

EAR_CLOSED = 0.21
LATEST = {"frame": None, "status": "idle"}
FRAMES_TO_CONFIRM = 2
CAMERA = 0


def fetch_model():
    if os.path.exists(MODEL):
        return
    print("downloading landmark model, one time only")
    urllib.request.urlretrieve(MODEL_URL, MODEL)
    print("done")


def make_landmarker():
    fetch_model()
    opts = vision.FaceLandmarkerOptions(
        base_options=mpp.BaseOptions(model_asset_path=MODEL),
        running_mode=vision.RunningMode.VIDEO,
        num_faces=1
    )
    return vision.FaceLandmarker.create_from_options(opts)


def eye_ratio(points):
    a = np.linalg.norm(points[1] - points[5])
    b = np.linalg.norm(points[2] - points[4])
    c = np.linalg.norm(points[0] - points[3])
    if c == 0:
        return 0.0
    return (a + b) / (2.0 * c)


def pick(landmarks, indices, w, h):
    out = []
    for i in indices:
        lm = landmarks[i]
        out.append(np.array([lm.x * w, lm.y * h]))
    return out


def current_ear(landmarks, w, h):
    left = eye_ratio(pick(landmarks, LEFT_EYE, w, h))
    right = eye_ratio(pick(landmarks, RIGHT_EYE, w, h))
    return (left + right) / 2.0


SPOOF_BACKEND = "yunet"


def passive_check(frame):
    try:
        faces = DeepFace.extract_faces(
            img_path=frame,
            detector_backend=SPOOF_BACKEND,
            anti_spoofing=True,
            enforce_detection=True
        )
    except Exception:
        return None, 0
    if not faces:
        return None, 0
    faces.sort(key=lambda f: f["facial_area"]["w"] * f["facial_area"]["h"], reverse=True)
    return bool(faces[0].get("is_real")), len(faces)


def check_liveness(timeout=15, required_blinks=2, save_path="live_face.jpg", show=True, keep_window=False):
    landmarker = make_landmarker()
    cam = cv2.VideoCapture(CAMERA)

    if not cam.isOpened():
        return False, None, {"error": "camera not opened, try CAMERA = 1"}

    target = random.randint(required_blinks, required_blinks + 1)
    blinks = 0
    closed_for = 0
    best_frame = None
    votes = []
    max_faces = 0
    start = time.time()
    last_vote = 0

    while time.time() - start < timeout:
        ok, frame = cam.read()
        if not ok:
            continue

        frame = cv2.flip(frame, 1)
        h, w = frame.shape[:2]
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        stamp = int((time.time() - start) * 1000)
        result = landmarker.detect_for_video(image, stamp)

        ear = None
        if result.face_landmarks:
            marks = result.face_landmarks[0]
            ear = current_ear(marks, w, h)

            if ear < EAR_CLOSED:
                closed_for = closed_for + 1
            else:
                if closed_for >= FRAMES_TO_CONFIRM:
                    blinks = blinks + 1
                closed_for = 0
                best_frame = frame.copy()

            elapsed = time.time() - start
            if len(votes) < 3 and elapsed - last_vote > 3:
                last_vote = elapsed
                v, n = passive_check(frame)
                if n > max_faces:
                    max_faces = n
                if v is not None:
                    votes.append(v)

        left = int(timeout - (time.time() - start))
        if True:
            msg = "BLINK " + str(target) + " TIMES  -  done " + str(blinks) + "  -  " + str(left) + "s"
            cv2.putText(frame, msg, (15, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            if ear is not None:
                cv2.putText(frame, "ear " + str(round(ear, 3)), (15, 70),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)
            LATEST["frame"] = frame.copy()
            LATEST["status"] = "blink " + str(blinks) + "/" + str(target)
            if show:
                cv2.imshow("liveness", frame)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break

        if blinks >= target:
            break

    cam.release()
    if show and not keep_window:
        cv2.destroyAllWindows()
    landmarker.close()

    if best_frame is not None:
        cv2.imwrite("_last_frame.jpg", best_frame)

    if best_frame is None:
        return False, None, {"reason": "no face seen", "blinks": blinks}

    if not votes:
        v, n = passive_check(best_frame)
        if n > max_faces:
            max_faces = n
        if v is not None:
            votes.append(v)

    active_ok = blinks >= target

    if len(votes) == 0:
        passive = "UNVERIFIED"
    elif votes.count(False) > votes.count(True):
        passive = "SPOOF"
    else:
        passive = "REAL"

    if max_faces > 1:
        outcome = "REFER"
        reason = "more than one face in frame"
    elif passive == "SPOOF":
        outcome = "REJECT"
        reason = "spoof detected"
    elif passive == "UNVERIFIED":
        outcome = "REFER"
        reason = "could not run spoof check, face not clearly visible"
    elif not active_ok:
        outcome = "REFER"
        reason = "blink challenge not completed"
    else:
        outcome = "PASS"
        reason = "live person confirmed"

    details = {
        "blinks": blinks,
        "required": target,
        "active_ok": active_ok,
        "passive_votes": votes,
        "passive": passive,
        "faces_seen": max_faces,
        "outcome": outcome,
        "reason": reason
    }

    if outcome != "PASS":
        return False, None, details

    cv2.imwrite(save_path, best_frame)
    return True, save_path, details


if __name__ == "__main__":
    passed, path, info = check_liveness()
    print(info)
    if passed:
        print("LIVENESS PASSED, frame saved:", path)
    else:
        print("LIVENESS FAILED")