"""Find and read one property's reports from a folder of saved Excel-attachment text (or, as a flagged last
resort for tests, a folder of PDFs).

The routine saves each .xlsx attachment's text exactly as the Outlook connector returns it, one .txt file per
attachment, then points this at the folder. Sheets are matched by the report title on the sheet's first line
and the property name on its second line, so one workbook can hold many reports and properties.
"""
import glob
import os

from . import (activity_log, availability, concessions, expiring_leases, income_budget, income_t12, lease_term_progress,
               receivables, rent_roll, rentable_items, work_orders, xlsxtext)

PROPERTY = {"grove": "The Cedar at the Grove", "f47": "Faculty47"}
MODULES = {
    "Activity Log": activity_log, "Availability": availability, "Concessions": concessions, "Expiring Leases": expiring_leases,
    "Income Statement - Budget vs Actual": income_budget, "Income Statement - Trailing 12": income_t12,
    "Lease Term Progress Summary": lease_term_progress, "Rent Roll": rent_roll, "Rentable Items Availability": rentable_items,
    "Resident Aged Receivables": receivables, "Work Order Details": work_orders,
}
EXPECTED = list(MODULES)


def _sheets(folder):
    out = []
    for path in sorted(glob.glob(os.path.join(folder, "*.txt"))):
        with open(path, encoding="utf-8") as f:
            for name, lines in xlsxtext.split_sheets(f.read()):
                out.append((os.path.basename(path), name, lines))
    return out


def _match(report, title):
    return title.lower().startswith(MODULES[report].KEY)


def load(folder, prop_id, property_name=None):
    """{report: parsed or None} plus 'missing', 'unreadable' and 'warnings' lists.
    missing: no sheet for that report and property. unreadable: a sheet was there but could not be read;
    in both cases the run keeps the report's last figures and raises a flag."""
    prop = property_name or PROPERTY[prop_id]
    sheets = _sheets(folder)
    out, missing, unreadable, warnings = {}, [], [], []
    for report, mod in MODULES.items():
        found = [(f, n, l) for f, n, l in sheets if _match(report, xlsxtext.title_info(l)["title"])
                 and xlsxtext.title_info(l)["property"].lower() == prop.lower()]
        if not found:
            out[report] = None
            missing.append(report)
            continue
        try:
            if report == "Work Order Details":
                parsed = [work_orders.parse(l) for _, _, l in found]
                out[report] = {"files": len(parsed), "declared": [p["declared"] for p in parsed], "orders": work_orders.combine(*parsed)}
            else:
                out[report] = mod.parse(found[0][2])
        except xlsxtext.LayoutError as e:
            out[report] = None
            unreadable.append({"report": report, "why": str(e)})
            continue
        if not mod.LAYOUT_CHECKED:
            warnings.append(f"{report}: read from an Excel layout that has not been checked against a real export; check it against the PDF this time")
    ex = out.get("Expiring Leases")
    if ex and ex["rows"]:
        warnings.append("Expiring Leases has rows for the first time: its row layout is untested, so check the rows against the report and say so in the summary")
    out["missing"], out["unreadable"], out["warnings"] = missing, unreadable, warnings
    return out
