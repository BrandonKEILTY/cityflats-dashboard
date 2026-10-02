"""Expiring Leases. The report lists the leases ending in the next four months.

NOTE: both test PDFs say "Selected report filters returned no data", so the row
layout below has not been checked against a report that has rows. Rows are returned
raw (line text plus the dates found) and flagged until a real one is added to fixtures.
"""
import re

from ..common import header_info, read_lines


def parse(path):
    lines = read_lines(path)
    info = header_info(lines)
    out = {"report": "Expiring Leases", **info, "rows": [], "no_data": any("returned no data" in l for l in lines), "row_layout_tested": False}
    for ln in lines:
        if re.match(r"^\d{3}[A-Z]? ", ln.strip()):
            out["rows"].append({"line": ln.strip(), "dates": re.findall(r"\d{4}-\d\d-\d\d", ln)})
    return out
