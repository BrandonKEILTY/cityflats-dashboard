"""Lease Term Progress Summary, from the Excel text. LAYOUT_CHECKED: no. Written from the PDF's headings;
no Excel export of this report has been seen yet. Average times must arrive as dd:hh:mm text or the report is flagged."""
import re

from . import xlsxtext as x

LAYOUT_CHECKED = False
KEY = "lease term progress"
STAGES = ["Guest card completed", "Application started", "Application partially completed", "Application completed",
          "Application approved", "Lease started", "Lease partially completed", "Lease completed", "Lease approved"]
TIME = re.compile(r"^\d\d:\d\d:\d\d$")


def period_start(lines):
    """The start date of the period the report covers, 'YYYY-MM-DD', or None when the report does not say.
    Reads a date range ('2026-08-01 - 2026-10-02', in any one cell) or a labelled start ('From', 'Since', 'Start
    Date', 'Date Range' followed by a date). An 'As of' date is the end of the period, not its start, so it is not used."""
    for ln in lines:
        for cell in ln.split("\t"):
            c = cell.strip()
            m = re.search(r"(\d{4}-\d\d-\d\d)\s*(?:-|to|through)\s*\d{4}-\d\d-\d\d", c)
            if m:
                return m.group(1)
            m = re.match(r"(?i)^(?:from|since|start(?:\s+date)?|period\s+start|date\s+range)\s*:?\s*(\d{4}-\d\d-\d\d)", c)
            if m:
                return m.group(1)
    return None


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
    out["since"] = period_start(lines[:8])
    out["stages"] = [[n, counts[i], times[i] if times and i < len(times) - 1 else None] for i, n in enumerate(STAGES)]
    out["total"] = counts[-1]
    out["avg_total"] = times[-1] if times else None
    out["times_found"] = len(times or [])
    return out
