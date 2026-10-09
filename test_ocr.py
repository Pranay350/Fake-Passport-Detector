import sys
from ocr import extract_fields, read_mrz_region, read_all_boxes

path = sys.argv[1] if len(sys.argv) > 1 else "specimens/passport_clean.jpg"

print("=== every text box EasyOCR found ===")
for it in read_all_boxes(path):
    print(round(it["y1"]), round(it["x1"]), repr(it["text"]), it["conf"])

print("")
print("=== parsed fields ===")
fields, raw = extract_fields(path)
for k in fields:
    print(k.ljust(18), repr(fields[k]))

print("")
print("=== MRZ region raw ===")
print(read_mrz_region(path))