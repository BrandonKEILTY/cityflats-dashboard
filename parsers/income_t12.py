"""Income Statement - Trailing 12, from the Excel text. LAYOUT_CHECKED: yes (Grove and Faculty47 workbooks).
The sheet has no section headings, only accounts and a few subtotals; the run needs the Net Operating Income row."""
import re

from . import xlsxtext as x

LAYOUT_CHECKED = True
KEY = "income statement - trailing 12"
MONTHS = {m: i + 1 for i, m in enumerate(["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"])}


def parse(lines):
    info = x.title_info(lines)
    rows = [x.cells(l) for l in lines]
    h = x.header_index(rows, "Account Name", "Total")
    hdr = rows[h]
    cols = x.columns(hdr)
    first_month = x.col(cols, "total") + 1
    months = []
    for c in hdr[first_month:]:
        m = re.fullmatch(r"([A-Z][a-z]{2}) (\d{4})", c.strip())
        if not m:
            break
        months.append(f"{m.group(2)}-{MONTHS[m.group(1)]:02d}")
    out = {"report": "Income Statement - Trailing 12", **info, "months": months, "rows": []}
    name_i = x.col(cols, "account name")
    for r in rows[h + 1:]:
        name = x.get(r, name_i)
        if not name or x.get(r, x.col(cols, "total")) == "":
            continue
        vals = [x.num(x.get(r, first_month + i)) or 0 for i in range(len(months))]
        out["rows"].append({"code": None, "name": name, "total": x.num(x.get(r, x.col(cols, "total"))), "by_month": dict(zip(months, vals))})
    if not any(r["name"] == "Net Operating Income" for r in out["rows"]):
        raise x.LayoutError("trailing 12: Net Operating Income row not found")
    return out
