"""Expiring Leases, from the Excel text. LAYOUT_CHECKED: no. No export with rows has been seen: the empty
case ('Selected report filters returned no data') is read; any rows are returned raw by header name and flagged.
Email addresses and phone numbers in the report are never copied."""
from . import xlsxtext as x

LAYOUT_CHECKED = False
KEY = "expiring leases"
KEEP = ["bldg-unit", "unit type", "resident", "lease interval status", "lease status", "lease start", "lease end", "move-out", "scheduled charges"]


def parse(lines):
    info = x.title_info(lines)
    rows = [x.cells(l) for l in lines]
    out = {"report": "Expiring Leases", **info, "rows": [], "no_data": any("returned no data" in l for l in lines), "row_layout_tested": False}
    try:
        h = x.header_index(rows, "Bldg-Unit", "Lease End")
    except x.LayoutError:
        if out["no_data"]:
            return out
        raise
    cols = x.columns(rows[h])
    for r in rows[h + 1:]:
        if "returned no data" in " ".join(r) or not x.get(r, 0):
            continue
        row = {k: x.get(r, cols[k]) for k in KEEP if k in cols}
        for k in ("lease start", "lease end", "move-out"):
            if k in row:
                row[k] = x.date(row[k]) or row[k]
        out["rows"].append(row)
    return out
