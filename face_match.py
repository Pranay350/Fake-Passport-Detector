import os
os.environ["TF_USE_LEGACY_KERAS"] = "1"

import cv2
from deepface import DeepFace

DETECTOR = "yunet"
FALLBACK = "opencv"
MODEL = "ArcFace"


def _detect(image_path):
    try:
        return DeepFace.extract_faces(img_path=image_path,
                                      detector_backend=DETECTOR,
                                      enforce_detection=True)
    except Exception:
        return DeepFace.extract_faces(img_path=image_path,
                                      detector_backend=FALLBACK,
                                      enforce_detection=True)


def crop_document_face(image_path, out_path="output/passport_face.jpg"):
    img = cv2.imread(image_path)
    if img is None:
        raise ValueError("image could not be opened")

    faces = _detect(image_path)
    if not faces:
        raise ValueError("no face found")

    faces.sort(key=lambda f: f["facial_area"]["w"] * f["facial_area"]["h"], reverse=True)
    area = faces[0]["facial_area"]
    x, y, w, h = area["x"], area["y"], area["w"], area["h"]

    pad = int(0.12 * max(w, h))
    y1 = max(0, y - pad)
    y2 = min(img.shape[0], y + h + pad)
    x1 = max(0, x - pad)
    x2 = min(img.shape[1], x + w + pad)

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    cv2.imwrite(out_path, img[y1:y2, x1:x2])
    return out_path


def match_faces(passport_face_path, live_face_path):
    result = DeepFace.verify(
        img1_path=passport_face_path,
        img2_path=live_face_path,
        model_name=MODEL,
        detector_backend=DETECTOR,
        enforce_detection=False
    )
    distance = float(result["distance"])
    return distance <= 0.78, distance