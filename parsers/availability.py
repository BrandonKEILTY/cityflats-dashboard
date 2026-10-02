"""Availability, from the Excel text. LAYOUT_CHECKED: no. Written from the PDF's column headings;
no Excel export of this report has been seen yet."""
import re

from . import xlsxtext as x

LAYOUT_CHECKED = False
KEY = "availability"
SECTION = re.compile(r"^(?P<name>Vacant Unrented Ready|Vacant Rented Ready|Occupied No Notice|Occupied Notice[A-Za-z ]*|Excluded)(?: \((?P<flag>Available|Unavailable)\))? \(Results: (?P<n>\d+)\)")


def parse(lines):
    info = x.title_info(lines)
    rows = [x.cells(l) for l in lines]
    h = x.header_index(rows, "Bldg-Unit", "Budgeted Rent", "Available On")
    cols = x.columns(rows[h])
    out = {"report": "Availability", **info, "sections": {}, "units": [], "totals": {}}
    cur = None
    for r in rows[h + 1:]:
        first = x.get(r, 0)
        m = SECTION.match(first) or SECTION.match(" ".join(c.strip() for c in r if c.strip()))
        if m:
            cur = m["name"]
            out["sections"][cur] = {"declared": int(m["n"]), "flag": m["flag"], "found": 0}
            continue
        if cur is None:
            continue
        unit = x.get(r, x.col(cols, "bldg-unit"))
        if not re.fullmatch(r"\d{3}[A-Z]?", unit):
            if "totals" in " ".join(r).lower():
                out["totals"][" ".join(c for c in r[:3] if c.strip())] = [x.num(c) for c in r if re.fullmatch(r"-?[\d.]+", c.strip())]
            continue
        cur_rent, fut_rent = x.num(x.get(r, cols.get("current lease rent"))), x.num(x.get(r, cols.get("future lease rent")))
        avail = x.date(x.get(r, x.col(cols, "available on")))
        move_in = x.date(x.get(r, cols.get("scheduled move-in")))
        resident = x.get(r, cols.get("resident")) or None
        out["sections"][cur]["found"] += 1
        out["units"].append({
            "unit": unit, "unit_type": x.get(r, cols.get("unit type")), "plan": x.get(r, x.col(cols, "floor plan")),
            "sqft": x.num(x.get(r, x.col(cols, "sqft"))), "budget_rent": x.num(x.get(r, x.col(cols, "budgeted rent"))),
            "prior_rent": x.num(x.get(r, cols.get("prior lease rent"))), "lease_rent": cur_rent if cur_rent is not None else fut_rent,
            "status": cur, "days_vacant": x.to_number(x.get(r, cols.get("vacant days")), 0), "resident": resident,
            "dates": [d for d in (move_in, avail) if d], "available_on": avail})
    if not out["units"]:
        raise x.LayoutError("availability: no unit rows found")
    return out
