"""Resident Aged Receivables, from the Excel text. LAYOUT_CHECKED: yes (Grove and Faculty47 workbooks)."""
from . import xlsxtext as x

LAYOUT_CHECKED = True
KEY = "resident aged receivables"
NUM_COLS = [("charges", "unallocated charges / credits"), ("d0_30", "0-30 days"), ("d31_60", "31-60 days"), ("d61_90", "61-90 days"),
            ("d90_plus", "90+ days"), ("prepayments", "pre-payments"), ("balance", "balance")]


def _kind(status):
    s = status.lower()
    return "current" if s.startswith("current") else "future" if s.startswith("future") else "former" if s.startswith("past") else "other"


def parse(lines):
    info = x.title_info(lines)
    rows = [x.cells(l) for l in lines]
    h = x.header_index(rows, "Bldg-Unit", "Resident", "Lease Status", "Balance")
    cols = x.columns(rows[h])
    ncol = x.col(cols, "last delinquency note")
    body = x.merge_by_start(lines[h + 1:], lambda ln: ln.count("\t") >= 8)
    out = {"report": "Resident Aged Receivables", **info, "rows": [], "totals": None}
    for ln in body:
        r = ln.split("\t")
        if not any(c.strip() for c in r):
            continue
        vals = {k: x.num(x.get(r, x.col(cols, name))) or 0 for k, name in NUM_COLS}
        if "total" in x.get(r, x.col(cols, "lease status")).lower() or "total" in x.get(r, 2).lower() and not x.get(r, 0):
            out["totals"] = vals
            continue
        status = x.get(r, x.col(cols, "lease status"))
        out["rows"].append({"unit": x.get(r, 0), "resident": x.get(r, x.col(cols, "resident")), "status": status, "kind": _kind(status),
                            "note": x.one_line("\t".join(r[ncol:]).replace("\t", " ")) if len(r) > ncol else "", **vals})
    return out
