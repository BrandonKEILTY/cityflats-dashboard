"""Rent Roll (Current Post Month).

Returns every suite, the future residents, and for Faculty47 the current residents.
Status rules (leased vs in progress) live in derive.py, not here.
"""
import re

from .common import NUM, num, read_lines, header_info

SUITE = re.compile(r"^(?P<unit>\d{3}[A-Z]?) (?P<type>.+?) (?P<sqft>[\d,]+\.\d\d) (?P<rest>.+)$")
STATUS = re.compile(r"^(Vacant (?:Rented|Unrented) Ready|Excluded ?-? ?Model Unit|Occupied(?: No Notice| Notice(?: Rented| Unrented)?)?)\s*(?P<tail>.*)$")
NUMS = re.compile(NUM)
DATES = re.compile(r"\d{4}-\d\d-\d\d")


def _split_tail(tail):
    """tail = resident name + amounts + dates. Returns name, amounts, dates."""
    dates = DATES.findall(tail)
    first_amt = re.search(NUM, tail)
    name = tail[: first_amt.start()].strip() if first_amt else tail.strip()
    amounts = [num(a) for a in NUMS.findall(DATES.sub("", tail))]
    return name, amounts, dates


def parse(path):
    lines = read_lines(path)
    out = {"report": "Rent Roll", **header_info(lines), "suites": [], "future": [], "status_summary": {}, "totals": {}}
    section = None
    for ln in lines:
        s = ln.strip()
        if s.startswith("Unit Details"):
            section = "unit"
            continue
        if s.startswith("Status Summary") and section == "unit":
            section = "summary"
            continue
        if s.startswith("Future Resident Details"):
            section = "future"
            continue
        if s.startswith("Rent Roll 4.") or s.startswith("Bldg-Unit") or s.startswith("Rent Roll -"):
            continue
        if section == "unit":
            if s.startswith("Total:"):
                out["totals"]["unit_details"] = [num(a) for a in NUMS.findall(s)]
                continue
            m = SUITE.match(s)
            if not m:
                continue
            sm = STATUS.match(m["rest"])
            if not sm:
                continue
            status = sm.group(1)
            tail = sm["tail"]
            resident = None
            if "-- Vacant --" in tail:
                tail = tail.replace("-- Vacant --", "").strip()
                amounts = [num(a) for a in NUMS.findall(tail)]
                row = {"unit": m["unit"], "type": m["type"], "sqft": num(m["sqft"]), "status": status, "resident": None,
                       "budget_rent": amounts[0] if amounts else None}
            else:
                name, amounts, dates = _split_tail(tail)
                # occupied: budgeted, scheduled, balance, deposit held, then dates
                row = {"unit": m["unit"], "type": m["type"], "sqft": num(m["sqft"]), "status": status, "resident": name,
                       "budget_rent": amounts[0], "scheduled": amounts[1], "balance": amounts[2], "deposit": amounts[3] if len(amounts) > 3 else None,
                       "move_in": dates[0] if dates else None, "lease_start": dates[1] if len(dates) > 1 else None,
                       "lease_end": dates[2] if len(dates) > 2 else None}
            out["suites"].append(row)
        elif section == "summary":
            m = re.match(r"^(Occupied No Notice|Total Occupied Units|Vacant Rented Ready|Vacant Unrented Ready|Total Vacant Units|Total Rentable Units|Excluded - Model Unit|Total Excluded Units|Total Units) (\d+) ", s)
            if m:
                out["status_summary"][m.group(1)] = int(m.group(2))
        elif section == "future":
            if s.startswith("Total:"):
                out["totals"]["future"] = [num(a) for a in NUMS.findall(s)]
                continue
            m = SUITE.match(s)
            if m:
                sm = STATUS.match(m["rest"])
                unit, ptype, sqft, tail = m["unit"], m["type"], num(m["sqft"]), sm["tail"] if sm else m["rest"]
            else:
                if out["future"] and re.match(r"^[^\d(]+?,? .*\d", s):
                    unit, ptype, sqft, tail = out["future"][-1]["unit"], out["future"][-1]["type"], out["future"][-1]["sqft"], s
                else:
                    continue
            name, amounts, dates = _split_tail(tail)
            # market rent, scheduled charges, balance, [deposit held]; dates: move in, lease start, lease end
            if len(amounts) == 2:  # second resident on a suite: no scheduled charge
                amounts = [amounts[0], None, amounts[1], None]
            elif len(amounts) == 3:
                amounts.append(None)
            out["future"].append({"unit": unit, "type": ptype, "sqft": sqft, "resident": name, "market_rent": amounts[0],
                                  "scheduled": amounts[1], "balance": amounts[2], "deposit": amounts[3],
                                  "move_in": dates[0] if dates else None, "lease_start": dates[1] if len(dates) > 1 else None,
                                  "lease_end": dates[2] if len(dates) > 2 else None})
    return out
