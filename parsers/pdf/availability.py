"""Availability: one row per suite, grouped by unit status."""
import re

from ..common import num, read_lines, header_info

SECTION = re.compile(r"^(?P<name>Vacant Unrented Ready|Vacant Rented Ready|Occupied No Notice|Occupied Notice[A-Za-z ]*|Excluded)(?: \((?P<flag>Available|Unavailable)\))? \(Results: (?P<n>\d+)\)")
ROW = re.compile(
    r"^(?P<unit>\d{3}[A-Z]?) (?P<utype>.+?) \d+\.\d\d(?P<plan>[A-Za-z][A-Za-z' ]*?) (?P<sqft>[\d,]+\.\d\d) "
    r"(?P<budget>[\d,]+\.\d\d) (?P<prior>[\d,]+\.\d\d)(?: (?P<lease>[\d,]+\.\d\d))?(?: ?(?P<moveout>\d{4}-\d\d-\d\d))? "
    r"(?P<mo>\d+) (?P<days>\d+) (?P<cost>[\d,]+\.\d\d)(?P<tail>.*)$")
DATES = re.compile(r"\d{4}-\d\d-\d\d")


def parse(path):
    lines = read_lines(path)
    out = {"report": "Availability", **header_info(lines), "sections": {}, "units": [], "totals": {}}
    cur = None
    for ln in lines:
        s = ln.strip()
        m = SECTION.match(s)
        if m:
            cur = m["name"]
            out["sections"][cur] = {"declared": int(m["n"]), "flag": m["flag"], "found": 0}
            continue
        if cur is None:
            continue
        if s.startswith("Non-Excluded Units Totals:"):
            out["totals"]["non_excluded"] = [num(x) for x in re.findall(r"[\d,]+\.\d\d", s)]
            continue
        m = ROW.match(s)
        if not m:
            continue
        tail = m["tail"]
        dates = DATES.findall(tail)
        resident = DATES.split(tail)[0].strip() if dates else tail.strip()
        resident = resident or None
        out["sections"][cur]["found"] += 1
        out["units"].append({
            "unit": m["unit"], "unit_type": m["utype"], "plan": m["plan"].strip(), "sqft": num(m["sqft"]),
            "budget_rent": num(m["budget"]), "prior_rent": num(m["prior"]), "lease_rent": num(m["lease"]),
            "status": cur, "days_vacant": int(m["days"]), "resident": resident,
            "dates": dates, "available_on": dates[-1] if dates else None,
        })
    return out
