"""Rentable Items Availability (parking), from the Excel text. LAYOUT_CHECKED: no. Written from the PDF's
headings (Inventory Name, Status, ... Reserved By); no Excel export seen yet."""
import re

from . import xlsxtext as x

LAYOUT_CHECKED = False
KEY = "rentable items"
LABEL = {"Vacant Rented Ready": "Reserved", "Reserved": "Reserved", "Vacant Unrented Ready": "Available"}


def parse(lines):
    info = x.title_info(lines)
    rows = [x.cells(l) for l in lines]
    h = x.header_index(rows, "Inventory Name", "Status", "Reserved By")
    cols = x.columns(rows[h])
    out = {"report": "Rentable Items Availability", **info, "items": [], "declared": None}
    for r in rows[h + 1:]:
        first = x.get(r, 0)
        m = re.search(r"\(Results: (\d+)\)", first)
        if m and out["declared"] is None:
            out["declared"] = int(m.group(1))
            continue
        if not re.match(r"^P\d+", first):
            continue
        status = x.get(r, x.col(cols, "status"))
        sm = re.match(r"^(P\d+) - (.+)$", first)
        label = f"{sm.group(1)} ({sm.group(2).lower()})" if sm else first
        um = re.search(r"\((\w+)\)", x.get(r, x.col(cols, "reserved by")))
        out["items"].append({"stall": label, "status": LABEL.get(status, "Occupied" if status.startswith("Occupied") else status),
                             "raw_status": status, "unit": um.group(1) if um else "", "amount": x.num(x.get(r, x.col(cols, "amount")))})
    if not out["items"]:
        raise x.LayoutError("rentable items: no stalls found")
    return out
