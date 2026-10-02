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

LEGAL = re.compile(r"\b(evict\w*|LTB|N(?:4|5|6|7|8|12|13)|L[12]|tribunal|hearing|sheriff|bailiff|lawyer|paralegal|court|legal|lien)\b|\bfile\s*(?:no\.?|number|#)|\b[A-Z]{3}-\d{4,}", re.I)
ISO = re.compile(r"^\d{4}-\d\d-\d\d$")
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


def add_months(iso, n):
    y, m, d = int(iso[:4]), int(iso[5:7]), int(iso[8:10])
    m0 = m - 1 + n
    return f"{y + m0 // 12:04d}-{m0 % 12 + 1:02d}-{d:02d}"


def name_patterns(name):
    """Patterns for one person written 'Last, First Middle' (as Entrata does) or 'First Last' (as the feed does).
    The full spelling comes first, so a replacement takes the middle names with it; then the first word of the first
    name with the last name. Last name alone is not matched: plan names and ordinary words share them."""
    name = " ".join(name.split())
    if "," in name:
        last, first = [x.strip() for x in name.split(",", 1)]
    else:
        parts = name.split()
        if len(parts) < 2:
            return []
        first, last = parts[0], " ".join(parts[1:])
    ft = first.split()[0] if first else ""
    if not ft or not last or len(ft) < 2 or len(last) < 3:
        return []
    pats = []
    if len(first.split()) > 1:
        pats += [re.compile(rf"\b{re.escape(first)}\s+{re.escape(last)}\b", re.I), re.compile(rf"\b{re.escape(last)},\s*{re.escape(first)}\b", re.I)]
    pats += [re.compile(rf"\b{re.escape(ft)}\s+(?:[\w.'-]+\s+){{0,2}}{re.escape(last)}\b", re.I),
             re.compile(rf"\b{re.escape(last)},\s*{re.escape(ft)}\b", re.I)]
    return pats


def known_names(prop, rent_roll_names):
    """Rent Roll residents plus everyone already named in the arrears table and the prospects list."""
    names = list(rent_roll_names)
    names += [r[1] for r in (prop.get("arrears") or {}).get("detail", []) or [] if len(r) > 1 and r[1]]
    names += [p["name"] for p in prop.get("prospects", []) or [] if p.get("name")]
    return names


def name_hits(prop, rent_roll_names):
    """Strings outside the arrears table and the prospects list that contain a resident's name."""
    pats = [(n, pt) for n in known_names(prop, rent_roll_names) for pt in name_patterns(n)]
    hits = []
    for k, v in prop.items():
        if k == "prospects":
            continue
        for path, text in walk(v, f"/{k}"):
            if not isinstance(text, str) or path.startswith("/arrears/detail"):
                continue
            for n, pt in pats:
                if pt.search(text):
                    hits.append((path, n, text))
                    break
    return hits


def week_start(iso):
    """The Thursday on or before iso (the week runs Thursday to Wednesday)."""
    from datetime import date, timedelta
    d = date.fromisoformat(iso)
    return (d - timedelta(days=(d.weekday() - 3) % 7)).isoformat()


def check(new, old, names=None, renewed=None):
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
        # rent increases: a list of {num, rent, earliest, noticeBy}; the page shows when an increase is due, not the amount (no newRent)
        inc = p.get("increases")
        if not isinstance(inc, list):
            fails.append(f"9. {pid}: increases must be present and a list (use [] when there are none)")
        else:
            for r in inc:
                if set(r) != {"num", "rent", "earliest", "noticeBy"}:
                    fails.append(f"9. {pid}: increases row has the wrong fields: {sorted(r)}")
                    continue
                if not (ISO.match(str(r["earliest"])) and ISO.match(str(r["noticeBy"]))):
                    fails.append(f"9. {pid}: increases row {r['num']} has a date that is not YYYY-MM-DD")
                    continue
                from datetime import date, timedelta
                e = date.fromisoformat(r["earliest"])
                if date.fromisoformat(r["noticeBy"]) != e - timedelta(days=90):
                    fails.append(f"9. {pid}: increases {r['num']}: noticeBy is not earliest minus 90 days")
                if r["noticeBy"] > add_months(new["asAt"], 6):
                    fails.append(f"9. {pid}: increases {r['num']}: notice date {r['noticeBy']} is more than 6 months out")
            keys = [(r["noticeBy"], r["num"]) for r in inc if isinstance(r, dict) and "noticeBy" in r]
            if keys != sorted(keys):
                fails.append(f"9. {pid}: increases are not sorted by notice date")
        # a suite with a renewal is left off the rent increases list (the renewal sets the new rent)
        for u in (renewed or {}).get(pid, []):
            if any(isinstance(r, dict) and r.get("num") == u for r in (inc if isinstance(inc, list) else [])):
                fails.append(f"13. {pid}: suite {u} has a renewal, so it must not be on the rent increases list")
        # renewals: lease ends [date, count] for the next 12 months only
        by = (p.get("renewals") or {}).get("byEnd")
        if by is not None:
            lo, hi = new["dataThrough"], add_months(new["dataThrough"], 12)
            for pair in by:
                if not (isinstance(pair, list) and len(pair) == 2 and ISO.match(str(pair[0])) and isinstance(pair[1], int)):
                    fails.append(f"10. {pid}: renewals.byEnd entry {pair!r} is not [date, count]")
                elif not lo <= pair[0] <= hi:
                    fails.append(f"10. {pid}: renewals.byEnd has {pair[0]}, outside {lo} to {hi}")
        # the four fields added with template 2026-10-02.12. renewals.mtm is always written; the other three are written
        # only when a report carries them (never estimated), so they are checked when present and noted when not.
        mtm = (p.get("renewals") or {}).get("mtm")
        if not (isinstance(mtm, int) and not isinstance(mtm, bool) and mtm >= 0):
            fails.append(f"14. {pid}: renewals.mtm must be a count of month-to-month leases, 0 if none (got {mtm!r})")
        # New leads this week = the sum of the stored daily counts (history[].newCards, counts only) from Thursday
        # through dataThrough. Left out of the feed while no day has a count.
        for s in p.get("history", []):
            if "newCards" in s and not (isinstance(s["newCards"], int) and not isinstance(s["newCards"], bool) and s["newCards"] >= 0):
                fails.append(f"15. {pid}: history {s.get('date')} newCards must be a whole number, 0 or more, with no names (got {s['newCards']!r})")
        wk_start = week_start(new["dataThrough"])
        counts_in_week = [s["newCards"] for s in p.get("history", []) if "newCards" in s and wk_start <= s.get("date", "") <= new["dataThrough"]
                          and isinstance(s["newCards"], int)]
        if "leadsWeek" in p:
            lw = p["leadsWeek"]
            if not (isinstance(lw, int) and not isinstance(lw, bool) and lw >= 0):
                fails.append(f"15. {pid}: leadsWeek must be a whole number of guest cards, 0 or more (got {lw!r})")
            elif lw != sum(counts_in_week):
                fails.append(f"15. {pid}: leadsWeek is {lw} but the daily counts from {wk_start} to {new['dataThrough']} add to {sum(counts_in_week)}")
        elif counts_in_week:
            fails.append(f"15. {pid}: leadsWeek is missing although daily counts exist for the week from {wk_start}")
        since = (p.get("funnel") or {}).get("since")
        if since is not None and not (ISO.match(str(since)) and str(since) <= new["dataThrough"]):
            fails.append(f"16. {pid}: funnel.since must be a YYYY-MM-DD date on or before dataThrough (got {since!r})")
        income = (p.get("items") or {}).get("income")
        if "income" in (p.get("items") or {}) and not (isinstance(income, (int, float)) and not isinstance(income, bool) and income >= 0):
            fails.append(f"17. {pid}: items.income must be a number of dollars a month, 0 or more (got {income!r})")
        # arrears wording: never write legal steps or file numbers in a status, comment or note
        for path, v in walk(p.get("arrears")):
            if isinstance(v, str) and LEGAL.search(v):
                fails.append(f"11. {pid}.arrears{path}: legal wording in {v[:70]!r}")
        for r in (p.get("arrears") or {}).get("detail", []) or []:
            if str(r[2]).lower().startswith("former") and "collections" in " ".join(map(str, r[8:])).lower() and "collections" not in str(r[2]).lower():
                fails.append(f"11. {pid}: arrears {r[0]} {r[1]}: a former resident in collections must read 'Former resident, with collections'")
        for path, who, text in name_hits(p, (names or {}).get(pid, [])):
            fails.append(f"12. {pid}{path}: names a resident ({who}); names belong only in the arrears table and prospects: {text[:70]!r}")
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


def gaps(new):
    """Optional fields the feed does not carry. Not failures: the page shows a dash or leaves the line out."""
    out = []
    for p in new["properties"]:
        if "leadsWeek" not in p:
            out.append(f"{p['id']}: leadsWeek not in the feed (the page shows a dash for New leads)")
        if (p.get("funnel") or {}).get("since") is None:
            out.append(f"{p['id']}: funnel.since not in the feed")
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("new")
    ap.add_argument("old")
    ap.add_argument("--figures", action="append", default=[], help="a parsers.figures output (grove.json / f47.json); gives the Rent Roll names. Repeat for each property.")
    a = ap.parse_args()
    names, renewed = {}, {}
    for path in a.figures:
        fg = json.load(open(path))
        names[fg["id"]] = fg.get("residents", [])
        renewed[fg["id"]] = fg.get("renewedSuites", [])
    if not names:
        print("note: no --figures given, so only names already in the arrears table and prospects are checked, not the Rent Roll")
    f = check(json.load(open(a.new)), json.load(open(a.old)), names, renewed)
    for g in gaps(json.load(open(a.new))):
        print("note:", g)
    for x in f:
        print("FAIL", x)
    print("feed checks:", "FAILED" if f else "passed")
    sys.exit(1 if f else 0)
