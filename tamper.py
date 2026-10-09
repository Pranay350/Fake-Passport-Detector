from mrz.generator.td3 import TD3CodeGenerator
from rules import check_rules

WEIGHTS = [7, 3, 1]

FIELDS = {
    "passport_no": (0, 9),
    "passport_cd": (9, 10),
    "nationality": (10, 13),
    "dob": (13, 19),
    "dob_cd": (19, 20),
    "sex": (20, 21),
    "expiry": (21, 27),
    "expiry_cd": (27, 28),
    "optional": (28, 42),
    "optional_cd": (42, 43),
    "composite_cd": (43, 44),
}


def char_value(c):
    if c == "<":
        return 0
    if c.isdigit():
        return int(c)
    return ord(c.upper()) - 55


def check_digit(field):
    total = 0
    i = 0
    for c in field:
        total = total + char_value(c) * WEIGHTS[i % 3]
        i = i + 1
    return total % 10


def parse_line2(line):
    out = {}
    for name in FIELDS:
        a, b = FIELDS[name]
        out[name] = line[a:b]
    return out


def verify_check_digits(line2):
    p = parse_line2(line2)
    composite = line2[0:10] + line2[13:20] + line2[21:43]
    checks = [
        ("passport number", p["passport_no"], p["passport_cd"]),
        ("date of birth", p["dob"], p["dob_cd"]),
        ("date of expiry", p["expiry"], p["expiry_cd"]),
        ("composite", composite, p["composite_cd"]),
    ]
    failures = []
    for label, field, printed in checks:
        got = str(check_digit(field))
        if got != printed:
            failures.append({"field": label, "printed": printed, "computed": got})
    return failures


def to_mrz_date(ddmmyyyy):
    d, m, y = ddmmyyyy.split("/")
    return y[2:] + m + d


def normalise(s):
    out = ""
    for c in s.upper():
        if c.isalpha():
            out = out + c
        elif c in " -'":
            out = out + "<"
    return out


def name_field(surname, given):
    a = normalise(surname)
    b = normalise(given)
    if a:
        full = a + "<<" + b
    else:
        full = "<<" + b
    if len(full) > 39:
        full = full[0:39]
    return full.ljust(39, "<")


def expected_mrz(printed):
    line1 = "P<IND" + name_field(printed["surname"], printed["given_names"])

    num = printed["passport_no"].upper().ljust(9, "<")
    dob = to_mrz_date(printed["dob"])
    exp = to_mrz_date(printed["date_of_expiry"])
    optional = "<" * 14

    line2 = (num + str(check_digit(num)) + "IND"
             + dob + str(check_digit(dob))
             + printed["sex"].upper()
             + exp + str(check_digit(exp))
             + optional + str(check_digit(optional)))
    composite = line2[0:10] + line2[13:20] + line2[21:43]
    line2 = line2 + str(check_digit(composite))
    return [line1, line2]


def name_truncated(line1):
    return line1[43] != "<"


def compare_names(expected, actual):
    if name_truncated(actual):
        n = len(actual.rstrip("<"))
        return expected[0:n] != actual[0:n], "truncated"
    return expected != actual, "full"


def diff(a, b):
    spots = []
    for i in range(min(len(a), len(b))):
        if a[i] != b[i]:
            spots.append(i)
    return spots


def which_field(positions):
    hit = set()
    for pos in positions:
        for name in FIELDS:
            a, b = FIELDS[name]
            if a <= pos < b:
                hit.add(name)
    return sorted(hit)


def screen(printed, mrz_lines, today=None):
    report = {"checksum_failures": [], "mismatch_positions": [], "fields": [],
              "rule_failures": [], "verdict": None}

    report["rule_failures"] = check_rules(printed, today)

    report["checksum_failures"] = verify_check_digits(mrz_lines[1])

    exp = expected_mrz(printed)
    name_bad, name_mode = compare_names(exp[0], mrz_lines[0])
    report["name_mode"] = name_mode
    d1 = diff(exp[0], mrz_lines[0]) if name_bad else []
    d2 = diff(exp[1], mrz_lines[1])
    report["mismatch_positions"] = {"line1": d1, "line2": d2}
    report["fields"] = which_field(d2)
    report["expected"] = exp

    if d1 or d2 or report["checksum_failures"]:
        report["verdict"] = "TAMPERED"
    elif report["rule_failures"]:
        report["verdict"] = "SUSPICIOUS"
    else:
        report["verdict"] = "CONSISTENT"
    return report


def show(report, mrz_lines):
    print("verdict:", report["verdict"])
    if report["checksum_failures"]:
        print("check digit failures:")
        for f in report["checksum_failures"]:
            print("  ", f["field"], "printed", f["printed"], "computed", f["computed"])
    for r in report["rule_failures"]:
        print("rule failed:", r["rule"], "-", r["detail"])
    d2 = report["mismatch_positions"]["line2"]
    if d2:
        print("MRZ disagrees with printed page at positions", d2)
        print("fields affected:", report["fields"])
        print("  on document :", mrz_lines[1])
        print("  expected    :", report["expected"][1])
        marker = ""
        for i in range(44):
            marker = marker + ("^" if i in d2 else " ")
        print("               ", marker)


if __name__ == "__main__":
    genuine = {
        "surname": "SINGH", "given_names": "ARJUN", "passport_no": "K1234567",
        "dob": "01/03/1998", "sex": "M", "date_of_expiry": "15/03/2030"
    }
    mrz = ["P<INDSINGH<<ARJUN<<<<<<<<<<<<<<<<<<<<<<<<<<<",
           "K1234567<6IND9803019M3003150<<<<<<<<<<<<<<04"]

    print("--- genuine ---")
    show(screen(genuine, mrz), mrz)

    print("")
    print("--- printed dob altered, mrz untouched ---")
    bad = dict(genuine)
    bad["dob"] = "01/03/2010"
    show(screen(bad, mrz), mrz)