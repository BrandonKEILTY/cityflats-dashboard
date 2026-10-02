"""Rentable Items Availability (parking stalls)."""
import re

from ..common import header_info, read_lines

ROW = re.compile(r"^(?P<name>P\d+(?: - [A-Za-z +]+?)?) (?P<status>Vacant Rented Ready|Vacant Unrented Ready|Occupied(?: No Notice| Notice)?|Reserved|Unavailable)"
                 r"(?: Other Income)? Monthly Parking, Residents (?P<amount>[\d,]+\.\d\d)(?P<rest>.*)$")
LABEL = {"Vacant Rented Ready": "Reserved", "Reserved": "Reserved", "Vacant Unrented Ready": "Available"}


def parse(path):
    lines = read_lines(path)
    out = {"report": "Rentable Items Availability", **header_info(lines), "items": [], "declared": None}
    for ln in lines:
        s = ln.strip()
        m = re.search(r"\(Results: (\d+)\)", s)
        if m and out["declared"] is None:
            out["declared"] = int(m.group(1))
        m = ROW.match(s)
        if not m:
            continue
        name = m["name"]
        sm = re.match(r"^(P\d+) - (.+)$", name)
        label = f"{sm.group(1)} ({sm.group(2).lower()})" if sm else name
        um = re.search(r"\((\w+)\)", m["rest"])
        out["items"].append({"stall": label, "status": LABEL.get(m["status"], "Occupied" if m["status"].startswith("Occupied") else m["status"]),
                             "raw_status": m["status"], "unit": um.group(1) if um else "", "amount": float(m["amount"].replace(",", ""))})
    return out
