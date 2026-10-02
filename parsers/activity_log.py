"""Activity Log - Leasing.

One row per activity. The report repeats entries two or three times, so parse()
returns every row it sees and dedupe() keeps one per name, date, time and type.
"""
import re
from datetime import datetime

import pdfplumber

from .common import header_info, nearest_rows, join_words, runs_by_anchor

STATE = re.compile(r"^(?P<kind>Application|Guest Card|Lease)\s*:\s*(?P<state>.+)$")


def parse(path):
    rows, lines = [], []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            words = page.extract_words()
            lines.extend((page.extract_text(use_text_flow=True) or "").split("\n"))
            hdr = {w["text"]: w for w in words if w["text"] in ("Name", "Bldg-Unit", "Status", "Date", "Activity", "Description", "Leasing", "Tag") and w["top"] < 120}
            if "Name" not in hdr:
                continue
            x_unit, x_status, x_date, x_type, x_desc, x_agent, x_tag = (hdr[k]["x0"] - 3 for k in ("Bldg-Unit", "Status", "Date", "Activity", "Description", "Leasing", "Tag"))
            top_hdr = hdr["Name"]["top"]
            label_tops = [w["top"] for w in words if w["text"] in ("Property", "Property:") and w["top"] > top_hdr]
            body = [w for w in words if top_hdr + 8 < w["top"] < 755 and not any(abs(w["top"] - t) < 2 for t in label_tops)]
            anchors = sorted({round(w["top"], 1) for w in body if x_type <= w["x0"] < x_desc and w["text"] in ("Tour", "Notes", "Email", "Call", "Text", "Appointment", "Task")})
            if not anchors:
                continue
            side = [w for w in body if w["x0"] < x_desc or w["x0"] >= x_agent]
            desc_runs = runs_by_anchor([w for w in body if x_desc <= w["x0"] < x_agent], anchors)
            for grp, dgrp in zip(nearest_rows(side, anchors), desc_runs):
                grp = grp + dgrp
                name = join_words(grp, 0, x_unit)
                unit = join_words(grp, x_unit, x_status)
                status = join_words(grp, x_status, x_date)
                date = join_words(grp, x_date, x_type)
                atype = join_words(grp, x_type, x_desc)
                desc = join_words(grp, x_desc, x_agent)
                agent = join_words(grp, x_agent, x_tag)
                dm = re.match(r"^([A-Z][a-z]+ \d{1,2}, \d{4}) (\d\d:\d\d [ap]\.m\.)$", date)
                when = datetime.strptime(dm.group(1) + " " + dm.group(2).replace(".", ""), "%B %d, %Y %I:%M %p") if dm else None
                sm = STATE.match(status)
                rows.append({"name": name, "unit": "" if unit == "Unknown" else unit, "status": status,
                             "status_kind": sm["kind"] if sm else None, "status_state": sm["state"] if sm else None,
                             "when": when.strftime("%Y-%m-%d %H:%M") if when else None, "type": atype,
                             "description": desc, "agent": agent})
    info = header_info(lines)
    for ln in lines[:4]:
        if re.fullmatch(r"\d{4}-\d\d-\d\d", ln.strip()):
            info["activity_date"] = ln.strip()
    return {"report": "Activity Log - Leasing", **info, "entries": rows}


def dedupe(entries):
    seen, out = set(), []
    for e in entries:
        key = (e["name"], e["when"], e["type"])
        if key not in seen:
            seen.add(key)
            out.append(e)
    return out
