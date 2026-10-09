from datetime import date


def parse_date(s):
    d, m, y = s.split("/")
    return date(int(y), int(m), int(d))


def age_at(dob, when):
    years = when.year - dob.year
    if (when.month, when.day) < (dob.month, dob.day):
        years = years - 1
    return years


def check_rules(printed, today=None):
    if today is None:
        today = date.today()

    issues = []

    try:
        dob = parse_date(printed["dob"])
        issue = parse_date(printed["date_of_issue"])
        expiry = parse_date(printed["date_of_expiry"])
    except Exception as e:
        issues.append({"rule": "date format", "detail": str(e)})
        return issues

    if expiry <= issue:
        issues.append({"rule": "expiry before issue",
                       "detail": printed["date_of_expiry"] + " not after " + printed["date_of_issue"]})

    if dob >= issue:
        issues.append({"rule": "born after issue",
                       "detail": printed["dob"] + " not before " + printed["date_of_issue"]})

    if expiry < today:
        issues.append({"rule": "document expired",
                       "detail": "expired " + printed["date_of_expiry"]})

    from datetime import timedelta
    anniversary = expiry + timedelta(days=1)
    span = anniversary.year - issue.year
    if (anniversary.month, anniversary.day) < (issue.month, issue.day):
        span = span - 1

    age = age_at(dob, issue)
    if age < 18:
        expected = 5
    else:
        expected = 10

    if span != expected:
        issues.append({"rule": "validity period",
                       "detail": "age at issue " + str(age) + " expects " + str(expected)
                                 + " year validity, document shows " + str(span)})

    return issues