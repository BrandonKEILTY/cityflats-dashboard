"""Activity Log - Leasing, from the Excel text. LAYOUT_CHECKED: no. Written from the PDF's headings
(Name, Bldg-Unit, Status, Date, Activity, Description, Leasing Agent (Activity)); no Excel export seen yet.

The report repeats entries two or three times; dedupe() keeps one per name, date and time, and type."""
import re

from . import xlsxtext as x

LAYOUT_CHECKED = False
KEY = "activity log"
ACTIVITY_TYPES = ("Tour", "Notes", "Email", "Call", "Text", "Appointment", "Task")
STATE = re.compile(r"^(?P<kind>Application|Guest Card|Lease)\s*:\s*(?P<state>.+)$")


def _when(v):
    """Date cell -> 'YYYY-MM-DD HH:MM'. Excel serial with a time fraction, or text such as 'September 30, 2026 12:03 p.m.'."""
    v = (v or "").strip()
    if re.fullmatch(r"\d{4,6}(\.\d+)?", v):
        return x.serial_to_datetime(v).strftime("%Y-%m-%d %H:%M")
    from datetime import datetime
    for fmt in ("%B %d, %Y %I:%M %p", "%B %d, %Y\n%I:%M %p", "%Y-%m-%d %I:%M:%S %p", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(v.replace("a.m.", "AM").replace("p.m.", "PM"), fmt).strftime("%Y-%m-%d %H:%M")
        except ValueError:
            continue
    raise x.LayoutError(f"activity log: cannot read date {v!r}")


def parse(lines):
    info = x.title_info(lines)
    rows = [x.cells(l) for l in lines]
    h = x.header_index(rows, "Name", "Bldg-Unit", "Date", "Activity", "Description")
    cols = x.columns(rows[h])
    agent_i = next((i for k, i in cols.items() if k.startswith("leasing agent")), None)
    ncol = x.col(cols, "name")
    body = x.merge_by_start(lines[h + 1:], lambda ln: ln.count("\t") >= 4 and bool(ln.split("\t")[ncol].strip()))
    entries = []
    for ln in body:
        r = ln.split("\t")
        if not x.get(r, ncol) or x.get(r, ncol).startswith("Property"):
            continue
        status = x.get(r, cols.get("status"))
        sm = STATE.match(status)
        unit = x.get(r, x.col(cols, "bldg-unit"))
        entries.append({"name": x.one_line(x.get(r, ncol)), "unit": "" if unit in ("Unknown", "-") else unit, "status": status,
                        "status_kind": sm["kind"] if sm else None, "status_state": sm["state"] if sm else None,
                        "when": _when(x.get(r, x.col(cols, "date"))), "type": x.get(r, x.col(cols, "activity")),
                        "description": x.one_line(x.get(r, x.col(cols, "description"))), "agent": x.get(r, agent_i)})
    if re.fullmatch(r"\d{4}-\d\d-\d\d", info["period"]):
        info["activity_date"] = info["period"]
    return {"report": "Activity Log - Leasing", **info, "entries": entries}


def dedupe(entries):
    seen, out = set(), []
    for e in entries:
        key = (e["name"], e["when"], e["type"])
        if key not in seen:
            seen.add(key)
            out.append(e)
    return out
