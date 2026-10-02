"""Rent Roll, from the Excel text. LAYOUT_CHECKED: yes (Grove and Faculty47 workbooks)."""
from . import xlsxtext as x

LAYOUT_CHECKED = True
KEY = "rent roll"


def _status(s):
    return s.strip()


def parse(lines):
    info = x.title_info(lines)
    rows = [x.cells(l) for l in lines]
    out = {"report": "Rent Roll", **info, "suites": [], "future": [], "status_summary": {}, "totals": {}, "charge_codes": []}
    section, cols, cc_cols = None, None, None
    last_future = None
    for r in rows:
        first = r[0].strip() if r else ""
        if first == "Unit Details":
            section, cols = "unit", None
            continue
        if first == "Status Summary":
            section = "summary"
            continue
        if section == "summary" and first == "Description":
            cc_cols = x.columns(r)  # the Charge Code Summary sits to the right of the status counts
            continue
        if first.startswith("Average Charges by Unit Type"):
            section = "avg"
            continue
        if first == "Future Resident Details":
            section, cols = "future", None
            continue
        if section in ("unit", "future") and first == "Bldg-Unit":
            cols = x.columns(r)
            continue
        if section == "unit" and cols:
            if "total" in x.get(r, 1).lower():
                out["totals"]["unit_details"] = [x.num(c) for c in r[2:] if c.strip()]
                continue
            if not first:
                continue
            resident = x.get(r, x.col(cols, "resident"))
            status = _status(x.get(r, x.col(cols, "unit status")))
            row = {"unit": first, "type": x.get(r, x.col(cols, "unit type")), "sqft": x.num(x.get(r, x.col(cols, "sqft"))),
                   "status": status, "resident": None if resident.startswith("-- Vacant") else resident,
                   "budget_rent": x.num(x.get(r, x.col(cols, "budgeted rent")))}
            if row["resident"]:
                row.update({"scheduled": x.num(x.get(r, x.col(cols, "scheduled charges"))), "balance": x.num(x.get(r, x.col(cols, "balance"))),
                            "deposit": x.num(x.get(r, x.col(cols, "deposit held"))), "move_in": x.date(x.get(r, x.col(cols, "move-in"))),
                            "lease_start": x.date(x.get(r, x.col(cols, "lease start"))), "lease_end": x.date(x.get(r, x.col(cols, "lease end")))})
            out["suites"].append(row)
        elif section == "summary":
            if cc_cols and "charge code" in cc_cols and "scheduled" in cc_cols:
                name = x.get(r, cc_cols["charge code"])
                if name and "returned no data" not in name:
                    out["charge_codes"].append({"name": name, "scheduled": x.num(x.get(r, cc_cols["scheduled"])),
                                                "type": x.get(r, cc_cols.get("charge code type"))})
            if first and first != "Description" and len(r) > 1 and r[1].strip():
                try:
                    out["status_summary"][first] = int(float(r[1]))
                except ValueError:
                    pass
        elif section == "future" and cols:
            if "total" in x.get(r, 1).lower():
                out["totals"]["future"] = [x.num(c) for c in r[2:] if c.strip()]
                continue
            unit = first or (last_future["unit"] if last_future else "")
            resident = x.get(r, x.col(cols, "resident"))
            if not resident:
                continue
            base = last_future if not first and last_future else {}
            f = {"unit": unit, "type": x.get(r, x.col(cols, "unit type")) or base.get("type"),
                 "sqft": x.num(x.get(r, x.col(cols, "sqft"))) if x.get(r, x.col(cols, "sqft")) else base.get("sqft"),
                 "resident": resident, "market_rent": x.num(x.get(r, x.col(cols, "market rent"))),
                 "scheduled": x.num(x.get(r, x.col(cols, "scheduled charges"))), "balance": x.num(x.get(r, x.col(cols, "balance"))),
                 "deposit": x.num(x.get(r, x.col(cols, "deposit held"))), "move_in": x.date(x.get(r, x.col(cols, "move-in"))),
                 "lease_start": x.date(x.get(r, x.col(cols, "lease start"))), "lease_end": x.date(x.get(r, x.col(cols, "lease end")))}
            out["future"].append(f)
            last_future = f
    if not out["suites"]:
        raise x.LayoutError("rent roll: no suites found")
    return out
