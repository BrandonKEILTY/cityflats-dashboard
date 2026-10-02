"""Lease Term Progress Summary, from the Excel text. LAYOUT_CHECKED: no. Written from the PDF's headings;
no Excel export of this report has been seen yet. Average times must arrive as dd:hh:mm text or the report is flagged."""
import re

from . import xlsxtext as x

LAYOUT_CHECKED = False
KEY = "lease term progress"
STAGES = ["Guest card completed", "Application started", "Application partially completed", "Application completed",
          "Application approved", "Lease started", "Lease partially completed", "Lease completed", "Lease approved"]
TIME = re.compile(r"^\d\d:\d\d:\d\d$")


def parse(lines):
    info = x.title_info(lines)
    rows = [x.cells(l) for l in lines]
    prop = info["property"]
    counts = times = None
    for r in rows:
        if x.get(r, 0) != prop:
            continue
        vals = [c.strip() for c in r[1:] if c.strip()]
        if vals and all(re.fullmatch(r"\d+", v) for v in vals):
            counts = [int(v) for v in vals]
        elif vals and all(TIME.match(v) for v in vals):
            times = vals
        elif vals and counts is not None:
            raise x.LayoutError("lease term progress: average times are not in dd:hh:mm text")
    if counts is None or len(counts) != len(STAGES) + 1:
        raise x.LayoutError(f"lease term progress: expected {len(STAGES) + 1} counts, got {counts}")
    out = {"report": "Lease Term Progress Summary", **info}
    out["stages"] = [[n, counts[i], times[i] if times and i < len(times) - 1 else None] for i, n in enumerate(STAGES)]
    out["total"] = counts[-1]
    out["avg_total"] = times[-1] if times else None
    out["times_found"] = len(times or [])
    return out
