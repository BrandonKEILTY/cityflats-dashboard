"""Find and read one folder of Command Center PDFs (one property, one day)."""
import glob
import os

from . import (activity_log, availability, concessions, expiring_leases, income_budget, income_t12, lease_term_progress,
               receivables, rent_roll, rentable_items, work_orders)

# report -> (filename prefix, parser). Work Order Details is handled separately: current + prior year.
READERS = {
    "Activity Log": ("Activity Log", activity_log.parse),
    "Availability": ("Availability", availability.parse),
    "Concessions": ("Concessions", concessions.parse),
    "Expiring Leases": ("Expiring Leases", expiring_leases.parse),
    "Income Statement - Budget vs Actual": ("Income Statement - Budget vs Actual", income_budget.parse),
    "Income Statement - Trailing 12": ("Income Statement - Trailing 12", income_t12.parse),
    "Lease Term Progress Summary": ("Lease Term Progress Summary", lease_term_progress.parse),
    "Rent Roll": ("Rent Roll", rent_roll.parse),
    "Rentable Items Availability": ("Rentable Items Availability", rentable_items.parse),
    "Resident Aged Receivables": ("Resident Aged Receivables", receivables.parse),
}
EXPECTED = list(READERS) + ["Work Order Details"]


def load(folder):
    """Returns {report: parsed or None}. A report that is not in the folder is None and
    is listed under 'missing'; the caller keeps the last figures and flags it, never guesses."""
    out, missing = {}, []
    for name, (prefix, fn) in READERS.items():
        hits = sorted(glob.glob(os.path.join(folder, prefix + "*.pdf")))
        if hits:
            out[name] = fn(hits[0])
        else:
            out[name] = None
            missing.append(name)
    wo = [work_orders.parse(p) for p in sorted(glob.glob(os.path.join(folder, "Work Order Details*.pdf")))]
    if wo:
        out["Work Order Details"] = {"files": len(wo), "declared": [p["declared"] for p in wo], "orders": work_orders.combine(*wo)}
    else:
        out["Work Order Details"] = None
        missing.append("Work Order Details")
    out["missing"] = missing
    return out
