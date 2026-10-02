"""The whole-feed checks from README section 6, before every save.

    python tools/check_feed.py <new feed.json> <previous feed.json>

Exit 0 when every check passes. Any failure: stop, change nothing, say why. Check 1 also needs
tools/render_check.py (run separately because it starts a browser).
"""
import argparse
import json
import re
import sys
from collections import Counter

BANNED = ["Rent Roll", "Activity Log", "Command Center", "package", "report total", "prepay"]
CLIENT_KEYS = ["waiting", "working", "items", "renewals", "arrears", "rent", "concessions", "budget", "workOrders"]
SUITES = {"grove": 82, "f47": 19}


def walk(o, path=""):
    if isinstance(o, dict):
        for k, v in o.items():
            yield from walk(v, f"{path}/{k}")
    elif isinstance(o, list):
        for i, v in enumerate(o):
            yield from walk(v, f"{path}/{i}")
    else:
        yield path, o


def check(new, old):
    fails = []
    text = json.dumps(new)
    for bad in ("NaN", "undefined", "Infinity"):
        if bad in text:
            fails.append(f"1. the feed contains {bad}")
    for p in new["properties"]:
        pid = p["id"]
        if len(p["stack"]) != SUITES.get(pid, len(p["stack"])):
            fails.append(f"2. {pid}: stack has {len(p['stack'])} suites, expected {SUITES[pid]}")
        st = Counter(s[2] for s in p["stack"])
        c = p["counts"]
        for key, status in (("leased", "leased"), ("inProgress", "progress"), ("applications", "applied"), ("available", "available"), ("occupied", "occupied")):
            if key in c and c[key] != st.get(status, 0):
                fails.append(f"2. {pid}: counts.{key} is {c[key]} but the stack has {st.get(status, 0)}")
        a = p["arrears"]
        if a.get("detail") is not None and "owing" in a:
            owing = round(sum(r[4] + r[5] + r[6] for r in a["detail"] if str(r[2]).lower().startswith("current")), 2)
            if abs(owing - a["owing"]) > 0.01:
                fails.append(f"3. {pid}: arrears.owing {a['owing']} but current residents' overdue columns add to {owing}")
        for r in a.get("detail", []) or []:
            if any(isinstance(v, (int, float)) and v < 0 for v in r[3:8]):
                fails.append(f"3. {pid}: arrears detail shows a credit or prepayment ({r[0]} {r[1]})")
        cc = p["concessions"]
        if abs(round(sum(u["total"] for u in cc["units"]), 2) - cc["total"]) > 0.01:
            fails.append(f"4. {pid}: concessions.total {cc['total']} is not the sum of its rows")
        if p["history"][-1]["date"] != new["dataThrough"]:
            fails.append(f"5. {pid}: last history snapshot is {p['history'][-1]['date']}, dataThrough is {new['dataThrough']}")
        before = next((q for q in old["properties"] if q["id"] == pid), None)
        if before:
            for k in ("weeks", "missedWeeks", "planBeds"):
                if before.get(k) != p.get(k):
                    fails.append(f"6. {pid}: {k} changed")
            for prev, cur in zip(before["history"], p["history"]):
                if prev["date"] != new["dataThrough"] and prev != cur:
                    fails.append(f"6. {pid}: an earlier history snapshot ({prev['date']}) changed")
        b = p.get("budget") or {}
        if b.get("noiMonths"):
            this_month = new["asAt"][:7]
            if b["noiMonths"][-1] >= this_month:
                fails.append(f"8. {pid}: budget shows {b['noiMonths'][-1]}, which is not a closed month (run date month {this_month})")
            label = b.get("period", "")
            m = re.match(r"^([A-Z][a-z]{2}) (\d{4})", label)
            if m:
                mon = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"].index(m.group(1)) + 1
                if f"{m.group(2)}-{mon:02d}" != b["noiMonths"][-1]:
                    fails.append(f"8. {pid}: budget period {label!r} does not match its last month {b['noiMonths'][-1]}")
        for k in CLIENT_KEYS:
            for path, v in walk(p.get(k)):
                if path.endswith("/source"):  # source labels are for KEILTY; the page does not show them
                    continue
                if isinstance(v, str):
                    for bad in BANNED:
                        if bad.lower() in v.lower():
                            fails.append(f"7. {pid}.{k}{path}: client text contains {bad!r}: {v[:60]!r}")
        for k in ("checks", "toCapture"):
            if p.get(k):
                fails.append(f"{pid}.{k} must stay empty")
    return fails


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("new")
    ap.add_argument("old")
    a = ap.parse_args()
    f = check(json.load(open(a.new)), json.load(open(a.old)))
    for x in f:
        print("FAIL", x)
    print("feed checks:", "FAILED" if f else "passed")
    sys.exit(1 if f else 0)
