"""Work Order Details, from the Excel text. LAYOUT_CHECKED: yes (Grove and Faculty47 workbooks).

Cells with line breaks (descriptions, notes) are joined back into one row before splitting on tabs.
Parse the current-year and prior-year sheets separately and join them with combine()."""
import re

from . import xlsxtext as x

LAYOUT_CHECKED = True
KEY = "work order details"
START = re.compile(r"^\d{7,9}\t")


def _dt(s):
    m = re.match(r"(\d{4}-\d\d-\d\d) (\d\d:\d\d:\d\d)", s or "")
    return (m.group(1), m.group(2)) if m else (x.date(s), None)


def parse(lines):
    info = x.title_info(lines)
    declared = None
    for ln in lines:
        m = re.search(r"\(Results: (\d+)\)", ln)
        if m:
            declared = int(m.group(1))
    m = re.match(r"^(\d{4}-\d\d-\d\d) - (\d{4}-\d\d-\d\d)$", info["period"])
    if m:
        info["range"] = [m.group(1), m.group(2)]
    rows = [x.cells(l) for l in lines]
    h = x.header_index(rows, "Reference", "Status", "Assigned Vendor", "Internal Note")
    cols = x.columns(rows[h])
    out = []
    for ln in x.merge_by_start([l for l in lines[h + 1:] if START.match(l) or not out_is_summary(l)], lambda l: bool(START.match(l))):
        if not START.match(ln):
            continue
        r = ln.split("\t")
        created, ctime = _dt(x.get(r, x.col(cols, "created")))
        due, _ = _dt(x.get(r, x.col(cols, "due date")))
        unit = x.get(r, x.col(cols, "bldg-unit"))
        emp = x.get(r, x.col(cols, "assigned employee"))
        out.append({
            "ref": x.get(r, x.col(cols, "reference")), "unit": "" if unit in ("-", "") else unit, "created": created, "created_time": ctime,
            "status": x.get(r, x.col(cols, "status")), "priority": x.get(r, x.col(cols, "priority")),
            "type": x.get(r, x.col(cols, "work order type")), "problem": x.get(r, x.col(cols, "problem")),
            "location": x.get(r, x.col(cols, "location")), "description": x.one_line(x.get(r, x.col(cols, "description"))),
            "employee": None if emp in ("", "-") else emp, "days_open": x.to_number(x.get(r, x.col(cols, "days open"))),
            "due": due, "vendor": x.get(r, x.col(cols, "assigned vendor")), "note": x.one_line(x.get(r, x.col(cols, "internal note"))),
            "needs_review": [k for k, v in (("status", x.get(r, x.col(cols, "status"))), ("created", created)) if not v]})
    return {"report": "Work Order Details", **info, "declared": declared, "orders": out}


def out_is_summary(line):
    """The trailing 'Average:' rows are not work orders."""
    return line.startswith("Average:") or line.startswith("Report Average:")


def combine(*parsed):
    seen, orders = set(), []
    for p in parsed:
        for o in p["orders"]:
            if o["ref"] not in seen:
                seen.add(o["ref"])
                orders.append(o)
    return orders
