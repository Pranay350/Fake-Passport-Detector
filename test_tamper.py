from datetime import date
from tamper import screen, expected_mrz

TODAY = date(2026, 9, 5)

base = {
    "surname": "SINGH", "given_names": "ARJUN", "passport_no": "K1234567",
    "dob": "01/03/1998", "sex": "M",
    "date_of_issue": "16/03/2020", "date_of_expiry": "15/03/2030",
    "place_of_birth": "PATIALA", "place_of_issue": "CHANDIGARH"
}
clean_mrz = expected_mrz(base)


def run(name, printed, mrz, want):
    r = screen(printed, mrz, TODAY)
    got = r["verdict"]
    mark = "ok " if got == want else "FAIL"
    print(mark, name, "->", got, r["fields"] if r["fields"] else "")
    return got == want


results = []

results.append(run("genuine", base, clean_mrz, "CONSISTENT"))

d = dict(base); d["dob"] = "01/03/2010"
results.append(run("dob altered on page", d, clean_mrz, "TAMPERED"))

d = dict(base); d["date_of_expiry"] = "15/03/2035"
results.append(run("expiry altered on page", d, clean_mrz, "TAMPERED"))

d = dict(base); d["passport_no"] = "K9999999"
results.append(run("passport no altered", d, clean_mrz, "TAMPERED"))

d = dict(base); d["sex"] = "F"
results.append(run("sex altered", d, clean_mrz, "TAMPERED"))

d = dict(base); d["surname"] = "SHARMA"
results.append(run("surname altered", d, clean_mrz, "TAMPERED"))

# the 10 percent case: tampered dob whose check digit collides
d = dict(base); d["dob"] = "01/03/2010"
collide = list(clean_mrz)
results.append(run("dob collision (checksum passes)", d, clean_mrz, "TAMPERED"))

# careful forger: edits both sides consistently
d = dict(base); d["dob"] = "01/03/2010"
results.append(run("both sides edited (undetectable here)", d, expected_mrz(d), "SUSPICIOUS"))

# long name, genuine, truncated in MRZ
d = dict(base)
d["surname"] = "VENKATASUBRAMANIAN"; d["given_names"] = "RAJAGOPALACHARI SUBRAHMANYAM"
results.append(run("long name genuine", d, expected_mrz(d), "CONSISTENT"))

# mononym
d = dict(base); d["surname"] = ""; d["given_names"] = "LAKSHMI"
results.append(run("mononym genuine", d, expected_mrz(d), "CONSISTENT"))

# expired document
d = dict(base); d["date_of_issue"] = "16/03/2010"; d["date_of_expiry"] = "15/03/2020"
results.append(run("expired document", d, expected_mrz(d), "SUSPICIOUS"))

print("")
print("passed", results.count(True), "of", len(results))