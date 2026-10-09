from tamper import check_digit

CODES = set("""IND NPL BTN BGD PAK LKA MMR CHN AFG USA GBR CAN AUS NZL FRA DEU ITA ESP
NLD BEL CHE AUT SWE NOR DNK FIN IRL PRT GRC POL CZE HUN ROU RUS UKR TUR IRN IRQ SAU
ARE QAT KWT OMN BHR JOR LBN ISR EGY ZAF NGA KEN ETH TZA UGA GHA MAR DZA TUN LBY SDN
JPN KOR PRK THA VNM LAO KHM MYS SGP IDN PHL BRN TWN HKG MAC MEX BRA ARG CHL COL PER
VEN ECU BOL PRY URY CUB DOM JAM HTI GTM HND SLV NIC CRI PAN MDV MUS SYC FJI PNG
D<< UTO GBD GBN GBO GBP GBS""".split())

ALPHA_ONLY = "0O1I2Z5S8B"
NUM_FIX = {"O": "0", "Q": "0", "D": "0", "I": "1", "L": "1", "Z": "2",
           "S": "5", "B": "8", "G": "6", "T": "7", "A": "4"}
ALPHA_FIX = {"0": "O", "1": "I", "2": "Z", "5": "S", "8": "B", "6": "G"}

# what each position of line 2 must be: n number, a letter, x either, s sex
LINE2_SHAPE = ("x" * 9) + "n" + ("a" * 3) + ("n" * 6) + "n" + "s" + ("n" * 6) + "n" + ("x" * 14) + "n" + "n"


def strip_noise(s):
    out = ""
    for c in s.upper():
        if c.isalnum() or c == "<":
            out = out + c
    return out


def fix_fillers(line):
    body = line.rstrip("K<")
    tail = len(line) - len(body)
    return body + ("<" * tail)


def coerce(line, shape):
    out = ""
    for i in range(min(len(line), len(shape))):
        c = line[i]
        kind = shape[i]
        if kind == "n" and not c.isdigit():
            c = NUM_FIX.get(c, c)
        elif kind == "a" and c.isdigit():
            c = ALPHA_FIX.get(c, c)
        elif kind == "s" and c not in "MF<":
            c = "<"
        out = out + c
    return out


def fit_length(line, want=44):
    if len(line) == want:
        return [line]
    if len(line) < want:
        return [line.ljust(want, "<")]
    options = []
    for i in range(len(line)):
        options.append(line[0:i] + line[i + 1:])
    return [o for o in options if len(o) == want]


def checks_pass(line2):
    if len(line2) != 44:
        return False
    if str(check_digit(line2[0:9])) != line2[9]:
        return False
    if str(check_digit(line2[13:19])) != line2[19]:
        return False
    if str(check_digit(line2[21:27])) != line2[27]:
        return False
    if str(check_digit(line2[28:42])) != line2[42]:
        return False
    composite = line2[0:10] + line2[13:20] + line2[21:43]
    if str(check_digit(composite)) != line2[43]:
        return False
    if line2[10:13] not in CODES:
        return False
    return True


def repair_line2(raw):
    base = fix_fillers(strip_noise(raw))
    winners = []
    for cand in fit_length(base):
        fixed = coerce(cand, LINE2_SHAPE)
        if checks_pass(fixed) and fixed not in winners:
            winners.append(fixed)
    if len(winners) == 1:
        return winners[0], True
    if len(winners) > 1:
        return winners, "AMBIGUOUS"
    options = fit_length(base)
    if options:
        return coerce(options[0], LINE2_SHAPE), False
    return coerce(base, LINE2_SHAPE), False


def repair_line1(raw):
    s = fix_fillers(strip_noise(raw))
    if len(s) > 44:
        s = s[0:44]
    return s.ljust(44, "<")


def read_mrz(raw_text):
    lines = []
    for l in raw_text.split("\n"):
        l = l.strip()
        if len(l) > 30:
            lines.append(l)
    if len(lines) < 2:
        return None, None, False
    l1 = repair_line1(lines[0])
    l2, verified = repair_line2(lines[1])
    return l1, l2, verified


def resolve(candidates, printed_passport_no):
    want = printed_passport_no.upper().ljust(9, "<")
    for c in candidates:
        if c[0:9] == want:
            return c, True
    return candidates[0], False


def read_and_resolve(raw_text, printed_passport_no=None):
    l1, l2, ok = read_mrz(raw_text)
    if ok == "AMBIGUOUS":
        if printed_passport_no:
            picked, solved = resolve(l2, printed_passport_no)
            return l1, picked, solved, "resolved by printed page" if solved else "unresolved"
        return l1, l2[0], False, "ambiguous OCR, needs printed page"
    return l1, l2, ok, "clean" if ok else "checksum failed"