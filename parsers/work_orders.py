"""Work Order Details.

Cells wrap and overlap, so fields are read from the text flow with fixed patterns, and
the vendor is split from the internal note using the vendor column's x position.
Parse the current-year and prior-year reports separately and combine with combine().
"""
import re

import pdfplumber

from .common import header_info

START = re.compile(r"^(?P<ref>\d{7,9}) (?P<unit>\S+) (?P<created>\d{4}-\d\d-\d\d) (?P<ctime>\d\d:\d\d:\d\d) [ap]\.m\. E[SD]T (?P<rest>.*)$")
DUE = re.compile(r"(?:^| )(?P<days>\d+|-) (?P<due>\d{4}-\d\d-\d\d) \d\d:\d\d:\d\d [ap]\.m\. E[SD]T(?: |$)")
STATUSES = ["Awaiting Parts", "Scheduling Trade", "In Progress", "Suspended", "Open", "Completed", "Scheduled", "On Hold", "Dispatched", "Waiting"]
PRIORITIES = ["Low", "Medium", "High", "Emergency", "Urgent"]
TYPES = ["Service Request", "Recurring", "Preventive", "Make Ready", "Inspection"]
LOCATIONS = ["Unit Wide", "Common Areas", "Bathroom", "Laundry Room", "Exterior", "Kitchen", "Bedroom", "Living Room", "Hallway", "Parking Lot", "Roof", "Lobby", "Basement", "Mechanical Room"]
EMPLOYEE = re.compile(r"(?:^|(?<=\s))(?P<emp>- |[A-Z][a-z]+ [A-Z][a-z]+ )$")


def _vendor_fragments(path):
    """Text in the Assigned Vendor column, line by line, in page order. Read from
    characters because the words are split letter by letter in this report."""
    frags = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            words = page.extract_words()
            hv = [w for w in words if w["text"] == "Assigned" and w["x0"] > 400]
            hn = [w for w in words if w["text"] == "Internal"]
            if not hv or not hn:
                continue
            x_lo, x_hi, top0 = hv[0]["x0"] - 2, hn[0]["x0"] - 1, hv[0]["top"]
            lines = {}
            for c in page.chars:
                if c["top"] > top0 + 8 and x_lo <= c["x0"] < x_hi and c["top"] < 755:
                    lines.setdefault(round(c["top"] / 3), []).append(c)
            for k in sorted(lines):
                cs = sorted(lines[k], key=lambda c: c["x0"])
                text = ""
                for i, c in enumerate(cs):
                    if i and c["x0"] - cs[i - 1]["x1"] > 0.3 * c["size"]:
                        text += " "
                    text += c["text"]
                frags.append(text.strip())
    return frags


def parse(path):
    with pdfplumber.open(path) as pdf:
        text = []
        for page in pdf.pages:
            text.extend((page.extract_text(use_text_flow=True) or "").split("\n"))
    info = header_info(text)
    for ln in text:
        m = re.match(r"^(\d{4}-\d\d-\d\d) - (\d{4}-\d\d-\d\d)$", ln.strip())
        if m:
            info["range"] = [m.group(1), m.group(2)]
    declared = None
    recs, cur = [], None
    for ln in text:
        s = ln.strip()
        m = re.match(r"^\(Results: (\d+)\)", s)
        if m:
            declared = int(m.group(1))
            continue
        if s.startswith("Average:") or s.startswith("Report Average:"):
            cur = None
            continue
        if s.startswith("Reference BLDG-Unit") or s.startswith("Work Order Details") or s.startswith("Property:") or s.startswith("'") and info.get("range") is None:
            continue
        m = START.match(s)
        if m:
            cur = {"head": m.groupdict(), "body": [m["rest"]]}
            recs.append(cur)
        elif cur is not None and s:
            cur["body"].append(s)
    frags = _vendor_fragments(path)
    ptr = 0
    out = []
    for r in recs:
        h = r["head"]
        body = " ".join(r["body"])
        rest = body
        status = next((x for x in STATUSES if rest.startswith(x + " ")), None)
        rest = rest[len(status) + 1:] if status else rest
        prio = next((x for x in PRIORITIES if rest.startswith(x + " ")), None)
        rest = rest[len(prio) + 1:] if prio else rest
        wtype = next((x for x in TYPES if rest.startswith(x + " ")), None)
        rest = rest[len(wtype) + 1:] if wtype else rest
        dm = DUE.search(rest)
        before, tail = (rest[: dm.start()], rest[dm.end():].strip()) if dm else (rest, "")
        emp = EMPLOYEE.search(before + " ")
        employee = emp["emp"].strip() if emp else None
        before = before[: emp.start()].strip() if emp else before.strip()
        loc = next((l for l in LOCATIONS if f" {l} " in f" {before} " or before.endswith(" " + l)), None)
        if loc:
            i = before.index(loc)
            problem, description = before[:i].strip(), before[i + len(loc):].strip()
        else:
            problem, description = None, before
        vendor = ""
        while ptr < len(frags):
            cand = (vendor + " " + frags[ptr]).strip()
            if tail.startswith(cand):
                vendor, ptr = cand, ptr + 1
            else:
                break
        note = tail[len(vendor):].strip() if vendor else tail
        out.append({
            "ref": h["ref"], "unit": "" if h["unit"] == "-" else h["unit"], "created": h["created"], "created_time": h["ctime"],
            "status": status, "priority": prio, "type": wtype, "problem": problem, "location": loc, "description": description,
            "employee": None if employee in (None, "-") else employee, "days_open": None if not dm or dm["days"] == "-" else int(dm["days"]),
            "due": dm["due"] if dm else None, "vendor": vendor, "note": note,
            "needs_review": [k for k, v in (("status", status), ("priority", prio), ("type", wtype), ("location", loc), ("due", dm)) if not v],
        })
    return {"report": "Work Order Details", **info, "declared": declared, "orders": out}


def combine(*parsed):
    """Combine current and prior-year parses, dropping duplicates by reference."""
    seen, orders = set(), []
    for p in parsed:
        for o in p["orders"]:
            if o["ref"] not in seen:
                seen.add(o["ref"])
                orders.append(o)
    return orders
