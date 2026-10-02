"""Concessions, from the Excel text. LAYOUT_CHECKED: yes (Grove and Faculty47 workbooks).

The Total cell is blank on each lease row, so the lease total is recurring plus one-time."""
from . import xlsxtext as x

LAYOUT_CHECKED = True
KEY = "concessions"


def parse(lines):
    info = x.title_info(lines)
    rows = [x.cells(l) for l in lines]
    h = x.header_index(rows, "Bldg-Unit", "Lease Term", "Recurring", "One-Time")
    cols = x.columns(rows[h])
    out = {"report": "Concessions", **info, "rows": [], "totals": None}
    for r in rows[h + 1:]:
        first = x.get(r, 0)
        if first.startswith("Concessions Burn-off"):
            break
        if first.startswith("Total/Average"):
            nums = [x.num(c) for c in r[2:] if c.strip()]  # count, recurring, one-time, total, remaining, market, lease, effective
            out["totals"] = nums[1:] if len(nums) == 8 else nums
            continue
        if not first:
            continue
        term = x.get(r, x.col(cols, "lease term"))
        rec, one = x.num(x.get(r, x.col(cols, "recurring"))) or 0, x.num(x.get(r, x.col(cols, "one-time"))) or 0
        tot = x.num(x.get(r, x.col(cols, "total")))
        out["rows"].append({"unit": first, "resident": x.get(r, x.col(cols, "resident")), "status": x.get(r, x.col(cols, "lease status")),
                            "term_months": int(term.split()[0]) if term[:1].isdigit() else None, "recurring": rec, "one_time": one,
                            "total": round(rec + one, 2) if tot is None else tot, "remaining": x.num(x.get(r, x.col(cols, "remaining"))),
                            "market_rent": x.num(x.get(r, x.col(cols, "market rent"))), "lease_rent": x.num(x.get(r, x.col(cols, "lease rent"))),
                            "effective_rent": x.num(x.get(r, x.col(cols, "effective rent")))})
    return out
