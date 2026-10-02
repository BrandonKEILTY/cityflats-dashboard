"""All the figures for one property on one day, as JSON, using the parsers and the rules.

    python -m parsers.figures <folder> grove|f47 --data-through 2026-10-01 > figures.json

Keys follow the feed. Client wording (notes, problem text, prospect note text) is not
written here; the run writes it under the writing rules.
"""
import argparse
import json

from . import activity_log, derive, registry

MODES = {"grove": "leaseup", "f47": "stabilised"}


def build(folder, prop_id, data_through, property_name=None, previous_feed=None, as_at=None):
    r = registry.load(folder, prop_id, property_name)
    mode = MODES[prop_id]
    out = {"id": prop_id, "dataThrough": data_through, "missing": r["missing"], "unreadable": r["unreadable"], "warnings": r["warnings"]}
    rr, av = r["Rent Roll"], r["Availability"]
    al = activity_log.dedupe(r["Activity Log"]["entries"]) if r["Activity Log"] else None
    if rr and av:
        out["residents"] = derive.resident_names(rr)  # for the "no resident names in notes" check
        out["counts"] = derive.counts(rr, av, al)
        out["stack"] = derive.stack(rr, av)
        out["deals"] = derive.deals(rr, mode)
        out["rent"] = derive.rent(rr, av, mode)
        out["renewals"] = derive.renewals(rr, r["Expiring Leases"], data_through)
        out["increases"] = derive.increases(rr, as_at or derive.add_days(data_through, 1))
        out["inventory"] = {"units": [[u["unit"], u["plan"], u["sqft"], u["budget_rent"], u["available_on"] or "", u["status"]] for u in av["units"]],
                            "unleasedMonthly": sum(u["budget_rent"] for u in av["units"] if u["status"] == "Vacant Unrented Ready")}
    if r["Resident Aged Receivables"]:
        out["arrears"] = derive.arrears(r["Resident Aged Receivables"])
    if r["Lease Term Progress Summary"]:
        out["funnel"] = derive.funnel(r["Lease Term Progress Summary"])
    if r["Concessions"] and rr:
        out["concessions"] = derive.concessions(r["Concessions"], rr)
    if r["Rentable Items Availability"]:
        out["items"] = derive.parking(r["Rentable Items Availability"])
    if r["Income Statement - Budget vs Actual"] and r["Income Statement - Trailing 12"]:
        out["budget"] = derive.budget(r["Income Statement - Budget vs Actual"], r["Income Statement - Trailing 12"])
        if previous_feed:
            prev = next((p for p in previous_feed["properties"] if p["id"] == prop_id), {})
            out["budgetStatus"] = derive.budget_status(out["budget"], prev.get("budget"))
    if r["Work Order Details"]:
        out["workOrders"] = derive.open_work_orders(r["Work Order Details"])
    if al is not None:
        out["activity"] = {"date": r["Activity Log"].get("activity_date"), "entries": al}
    out["snapshot"] = derive.snapshot(r, data_through)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("folder")
    ap.add_argument("prop", choices=sorted(MODES))
    ap.add_argument("--data-through", required=True)
    ap.add_argument("--as-at", help="the run date (default: the day after --data-through); rent increases look six months ahead from it")
    ap.add_argument("--previous", help="the feed already saved (previous.json); adds budgetStatus: keep, restated, behind")
    a = ap.parse_args()
    prev = json.load(open(a.previous)) if a.previous else None
    print(json.dumps(build(a.folder, a.prop, a.data_through, previous_feed=prev, as_at=a.as_at), indent=1, default=str))


if __name__ == "__main__":
    main()
