<<<<<<< HEAD
# AI-Based Fake Identity & Document Screening System

Smart India Hackathon 2026 — Problem Statement **26188**, SSB Police-II Division.

An officer scans a passport, the traveller looks into a camera, and a few seconds later
the console says **Cleared**, **Refer to officer**, or **Rejected** — with the evidence
on screen.

Runs offline on a laptop CPU. No GPU, no cloud, no network at inference time.

---

## The fraud we're catching

| Attack | What the forger does | Caught by |
|---|---|---|
| Impersonation | Carries someone else's genuine passport | Face match against live camera |
| Presentation attack | Holds up a photo or phone showing the real owner | Blink challenge + anti-spoofing model |
| Date-of-birth edit | Repaints DOB so an adult passes as a minor | MRZ cross-check, validity rule, pixel analysis |
| Expiry edit | Extends an expired document | MRZ cross-check, validity rule, pixel analysis |
| Passport-number edit | Changes a number that sits on a watchlist | MRZ cross-check |
| Photo substitution | Pastes a different portrait onto a real passport | Face match against live camera |

An officer has ~30 seconds per traveller. Nobody does modular arithmetic at 2 a.m., and
nobody sees JPEG compression artefacts. This clears the obvious cases fast so human
attention lands on the rest. It does not replace the officer.

---

## How a passport defends itself

Those two lines at the bottom of the data page are the **machine-readable zone**,
defined by ICAO Doc 9303 and identical on every passport on earth, Indian included.

```
K1234567<6IND9803019M3003150<<<<<<<<<<<<<<04
```

| Position | Content | Means |
|---|---|---|
| 0–8 | `K1234567<` | passport number, padded to 9 with `<` |
| 9 | `6` | check digit over the passport number |
| 10–12 | `IND` | nationality |
| 13–18 | `980301` | date of birth, `YYMMDD` |
| 19 | `9` | check digit over the date of birth |
| 20 | `M` | sex |
| 21–26 | `300315` | expiry date, `YYMMDD` |
| 27 | `0` | check digit over the expiry date |
| 28–41 | `<<<<<<<<<<<<<<` | optional data, empty here |
| 42 | `0` | check digit over the optional field |
| 43 | `4` | composite check digit over the whole line |

Two facts carry this entire project.

**The data appears twice.** Name, number, DOB, sex and expiry are printed for humans in
the upper half and encoded again for machines at the bottom.

**The machine zone checks its own arithmetic.** Multiply each character by a repeating
7-3-1 pattern, sum, take mod 10. That digit is printed right after the field.

```
K 1 2 3 4 5 6 7 <     ← passport number field
7 3 1 7 3 1 7 3 1     ← weights
```
`(20×7)+(1×3)+(2×1)+(3×7)+(4×3)+(5×1)+(6×7)+(7×3)+0 = 246` → `246 mod 10` = **6**

Edit the printed DOB and leave the bottom alone, and the document contradicts itself.
Edit both without knowing the formula, and the arithmetic breaks. No model required —
just code that can do the sum. Works identically on an Indian passport and a Portuguese
one.

---

## Four layers

No single check stops a determined forger. Each raises the cost.

| Layer | Question | Method | Beaten by |
|---|---|---|---|
| 1 · Person | Is this the right human? | Blink challenge + MiniFASNet anti-spoofing + ArcFace | Nothing practical at a desk |
| 2 · Data | Does the document agree with itself? | ICAO check digits, MRZ ↔ printed diff, validity rules | Forger who edits both sides correctly |
| 3 · Pixels | Was the image edited? | JPEG ghost analysis per field | Forger who never touches a file |
| — · Chip | Is it cryptographically genuine? | **Not built** — needs NFC hardware | Nothing; it's unforgeable |

### Layer 1 — liveness, two ways

Face matching alone is beaten by holding up a photo. So liveness runs first, twice over:

- **Challenge-response.** Screen asks for a random number of blinks. Eye aspect ratio —
  eyelid height over eye width — collapses when the eye shuts. A printed photo can't blink.
- **Trained model.** MiniFASNet sees print texture, phone pixel grids, screen flatness in
  a single frame. Needs no cooperation.

These fail differently, which is the point. **Measured:** a phone playing a video of a
real person passed 3/3 blinks and was rejected by the spoof model every time.

There's also a **single-subject rule**. We found this attack ourselves: hold a phone
showing the victim's face *beside* your own real face, and the spoof model validates
yours while the matcher compares theirs. More than one face in frame now refers.

### Layer 2 — reconstruct and diff

The pipeline reads the printed fields, reads the machine zone, **rebuilds what the machine
zone should say** from the printed values, and diffs character by character:

```
on document  K1234567<6IND9803019M3003150<<<<<<<<<<<<<<04
expected     K1234567<6IND1003019M3003150<<<<<<<<<<<<<<02
                          ↑↑                            ↑
```

Positions 13, 14 and 43 — the year digits and the composite check digit. Those positions
become the red box on the image.

Rules the forger doesn't know sit alongside: an Indian passport runs **10 years for
adults, 5 for minors**. Fake a DOB to look like a minor and the ten-year validity
contradicts it. Expiry after issue. DOB before issue.

### Layer 3 — compression history

Layers 1 and 2 read what the document *says*. This ignores content and asks what happened
to the file.

Open a JPEG, paint over one field, save again — that region is now compressed twice while
everything around it is compressed once. Measurable, and it survives however good the text
edit was.

**JPEG ghost analysis**: re-save at a range of qualities and watch each region respond.
Untouched areas bottom out at the original quality; a twice-compressed region bottoms out
elsewhere.

We tried **Error Level Analysis** first — the technique every tutorial reaches for — and
it failed outright. The forged image scored *lower* than the clean one, hotspots landed
on the image border. ELA re-saves once at a guessed quality; if that guess matches the
original, everything flattens. It's a visualiser, not a detector. Dropped.

### The layer we don't have

Modern e-passports carry a chip whose contents are signed by the issuing government.
Passive Authentication detects any alteration mathematically — unforgeable without the
state's private key. It needs NFC hardware we don't have.

This system sits **in front of** that, not instead of it. Chip reading covers e-passports
at equipped desks and nothing else — not visas, national ID cards, permits, older or
damaged passports — and it never catches a genuine document presented by an impostor.

---

## What it catches, measured

Tested against five specimen documents, all generated by the scripts in this repo. Each
forgery was produced the way a real forger works: open the saved clean JPEG, edit one
region, save again.

| Specimen | Result | Caught by |
|---|---|---|
| `passport_clean.jpg` | CLEAN | — |
| `resaved_clean.jpg` (control, re-saved untouched) | CLEAN | — |
| `forged_dob.jpg` | FORGED | machine zone + validity rule + pixels |
| `forged_expiry.jpg` | FORGED | machine zone + validity rule + pixels |
| `forged_passportno.jpg` | FORGED | machine zone |
| `forged_photo.jpg` | not caught here | Layer 1 face match |

Four of the five text forgeries are caught by the document layers. The photo swap is
invisible to them by design — no text changed — and is caught by comparing the document
portrait against the live traveller.

**Pixel-level scores.** The date-field outlier ratio comes out at 1.09 on clean documents
and 1.33–1.42 on tampered ones. The threshold sits at 1.2. Passport-number tampering
barely registers at the pixel level (a small edit in a dense region) but the machine-zone
check catches it cleanly — that is the layering doing its job rather than a claim about it.

**Face distances.** Calibrated on ten pairs from a single identity: genuine matches
0.61–0.72, different people 0.85–0.93, no overlap. Cross-checked against a live webcam
comparison to a different person's passport: 0.954 and 1.073, both correctly rejected.
The band between 0.72 and 0.85 returns *refer*, not a guess.

`test_tamper.py` runs eleven cases covering every tamper type plus long-name truncation,
single-name travellers, and expired documents. All eleven pass.

### Two findings worth reading

**Check digits are weaker than they look.** A check digit is one digit mod 10, so roughly
one in ten random tampers passes it by coincidence. We measured this: of 40 fake years
tested against a fixed check digit, 4 passed. That is why the check digit is the
*supporting* evidence and the cross-field comparison against the printed page is the
primary detector.

**Cross-domain forensics is hard, and published numbers say so.** State-of-the-art
pixel-level localisation on unseen document tampering sits around 0.3 F1. Any team
reporting 0.95 on this task has tested in-domain or leaked their split. Our pixel layer
is a *localiser* that highlights a suspicious region, not a classifier that returns a
verdict on its own.

---

## Known limits

Stated here rather than left to be discovered.

- **A forger who edits both the printed page and the machine zone, recomputing the check
  digits, produces a document this system reports as internally consistent.** The
  validity-period rule may still catch them. Nothing text-based can do better; that is
  what the chip is for.
- **Ghost portrait verification is not implemented.** The faint secondary portrait on a
  real passport is a genuine anti-fraud feature, and comparing it against the main photo
  is the correct defence against an impostor pasting their own photograph into someone
  else's document. We could not reproduce the security printing faithfully enough on a
  specimen to test the check honestly, so it is documented rather than demonstrated.
- **Client-side liveness would not be security.** In the current desktop build the check
  runs on the same machine as the server, so this is moot. In a browser deployment the
  blink challenge must stay user experience and the anti-spoofing model must run
  server-side on submitted frames, because anything running in the browser can be
  bypassed by posting a still image directly to the endpoint.
- **The anti-spoofing model occasionally rejects a real face.** Observed roughly once in
  ten runs during testing. At a checkpoint that is an innocent traveller referred to an
  officer, not refused entry — which is what the REFER path exists for.
- **Field coordinates are template-specific.** Extraction uses known field positions for
  the Indian passport data page. A different document type needs its own coordinate set.
  Real commercial readers work the same way: identify the document type, then apply its
  layout.
- **The specimens are not real passports.** Privacy law rules out real citizen documents,
  so everything here is a marked specimen built on a blank Wikimedia template with
  fictional data and an AI-generated face. Every generated document carries a SPECIMEN
  watermark.

---

## Running it

Python 3.10 or newer.

```bash
pip install -r requirements.txt
pip install fastapi uvicorn python-multipart
```

The web interface needs those three; they are not yet in `requirements.txt`.

```bash
python webapp.py
```

Open `http://127.0.0.1:8000`.

Wait for `OCR ready` and `face models ready` in the terminal before uploading anything.
The first run downloads model weights — EasyOCR detection and recognition, ArcFace
(137 MB), the MiniFASNet anti-spoofing model, and the MediaPipe face landmarker. After
that they are cached and startup is quick.

Upload a file from `specimens/`, then press **Verify traveller** to run the camera check.
The camera opens on whatever machine runs the server.

### Without the browser

```bash
# document + camera
python pipeline.py specimens/forged_dob.jpg

# document only
python pipeline.py --no-camera specimens/forged_dob.jpg

# every specimen, document layers only
python screen.py

# the eleven logic cases
python test_tamper.py

# raw OCR diagnostic
python test_ocr.py specimens/passport_clean.jpg
```

`test_ocr.py` is the one to reach for when extraction misbehaves. It prints every text
box EasyOCR found with its position and confidence, then what the extractor made of it.
If a field is missing from the second list but its value appears in the first, the
coordinate anchors need adjusting.

### Regenerating the specimens

```bash
# clean specimen + output/calibration.png
python generate_passport.py

# four forgeries, four masks, one control
python make_forgeries.py
```

Order matters — the forgeries are cut from the clean image, so regenerating one without
the other leaves them out of sync.

`generate_passport.py` also writes `output/calibration.png`, which marks every field
position on the blank template. Use it whenever a field lands in the wrong place.

---

## The code

```
webapp.py       FastAPI server, camera stream, endpoints
static/         the console UI
pipeline.py     command-line entry point
screen.py       document screening, returns a verdict

extract.py      OCR boxes to field values
ocr.py          EasyOCR wrapper
mrz_read.py     machine-zone repair, checksum-guided
tamper.py       check digits, expected MRZ, char diff
rules.py        validity period, date ordering
forensics.py    JPEG ghost, per-field scoring
annotate.py     red boxes, banner, heatmap

liveness.py     blink challenge, anti-spoofing
face_match.py   face crop, ArcFace comparison
impersonation.py  desktop-only Layer 1

generate_passport.py   builds the clean specimen
make_forgeries.py      builds forgeries + masks
test_tamper.py         eleven logic cases
test_ocr.py            OCR diagnostic
```

`assets/` holds the blank template, the OCR-B font, the MediaPipe landmarker and the
generated face. `specimens/` holds the clean and forged documents with their masks.
`output/` and `uploads/` are working directories and are gitignored.

### Data flow

```
image
  |
  +-- EasyOCR --+-> printed fields --+
  |             +-> machine zone ----+--> tamper.py
  |                    rules.py -----+       |
  |                                          v
  +-- forensics.py --> suspicious field   verdict +
                              |          positions
                              v
                    screen.py combines
                    annotate.py draws
                              |
  camera -> liveness -> face -+
                              v
                CLEAR | REFER | REJECT
```

### Things you may need to change

| Where | Constant | Meaning |
|---|---|---|
| `liveness.py` | `EAR_CLOSED = 0.21` | eye ratio below which the eye counts as shut — tune per face |
| `liveness.py` | `CAMERA = 0` | change to 1 or 2 if the feed is black |
| `pipeline.py` | `MATCH_BELOW = 0.72` / `REJECT_ABOVE = 0.85` | face distance bands; between them is REFER |
| `forensics.py` | `OUTLIER_THRESHOLD = 1.2` | pixel outlier ratio that flags a field |
| `forensics.py` | `FIELD_BOXES` | field regions for pixel scoring |
| `extract.py` | `ANCHORS` | field positions for OCR extraction |
| `generate_passport.py` | `POS` | field positions for generation |

The last three must agree. If a field moves in `POS`, change `ANCHORS` and `FIELD_BOXES`
to match, or extraction silently misses the field rather than raising an error.

---

## Not yet built

- **Risk score.** The problem statement asks for a numeric risk score; the system
  currently returns categorical verdicts. All the inputs are computed already.
- **Audit log.** "A digital trail for investigations" is in the problem statement.
  Nothing currently persists between screenings.
- **Browser-based camera.** The webcam is captured server-side by OpenCV. A deployed web
  version needs MediaPipe's JavaScript build for the blink challenge, with the
  anti-spoofing model still enforced server-side.
- **Visas, national ID cards, permits.** Passport only for now. The document layers
  generalise; the coordinate sets do not.
- **`face_landmarker.task` exists twice**, at the root and in `assets/`. `liveness.py`
  loads the root copy. Harmless, worth tidying.

---

## Credits and licensing

Built on: DeepFace (MIT) for face detection and ArcFace matching; MiniFASNet /
Silent-Face-Anti-Spoofing (Apache 2.0) for presentation-attack detection; MediaPipe
(Apache 2.0) for facial landmarks; EasyOCR (Apache 2.0); OpenCV; Pillow; the `mrz`
package for generating specimen machine-readable zones.

All model weights used here are permissively licensed and free for commercial use, which
matters for a system intended for government deployment. The MRZ implementation follows
ICAO Doc 9303.

The passport template is a blank specimen from Wikimedia Commons. No real identity
document, and no real person's biometric data, is used anywhere in this repository.
=======
# Fake-Passport-Detector
>>>>>>> 542738e80d9df68d72cc82d3f927c541ff1d9bde
