"""Figures the dashboard shows, worked out from the parsed reports with the rules in
daily-job-rules.md. Numbers only; client wording is not written here."""
import re
from collections import Counter


def _leased(row):
    """Deposit held > 0, or a negative balance."""
    return bool((row.get("deposit") or 0) > 0 or (row.get("balance") or 0) < 0)


def stack(rr, av):
    """[suite, plan, status] for every suite. status: occupied, leased, progress, applied, available, model."""
    future = {}
    for f in rr["future"]:
        future.setdefault(f["unit"], []).append(f)
    rented_in_av = {u["unit"] for u in (av or {"units": []})["units"] if u["status"] == "Vacant Rented Ready"}
    out = []
    for s in rr["suites"]:
        u = s["unit"]
        if s["status"].startswith("Excluded"):
            st = "model"
        elif s["status"].startswith("Occupied"):
            st = "occupied"
        elif u in future:
            st = "leased" if _leased(future[u][0]) else "progress"
        elif u in rented_in_av:
            st = "applied"
        else:
            st = "available"
        out.append([u, s["type"], st])
    return out


def counts(rr, av, al=None):
    st = Counter(x[2] for x in stack(rr, av))
    c = {"leased": st["leased"], "inProgress": st["progress"], "applications": st["applied"],
         "available": st["available"], "occupied": st["occupied"]}
    if al is not None:
        c["toursToday"] = sum(1 for e in al if e["type"] == "Tour")
    return c


def deals(rr, mode):
    """Future residents shown on the dashboard, one row per suite.
    leaseup (The Grove): only leases in progress, i.e. no last month's rent yet ("Leases in progress").
    stabilised (Faculty47): every future resident, leased or in progress ("Moving in")."""
    out, seen = [], set()
    for f in rr["future"]:
        if f["scheduled"] is None or f["unit"] in seen:
            continue
        leased = _leased(f)
        if mode == "leaseup" and leased:
            continue
        seen.add(f["unit"])
        out.append({"unit": f["unit"], "plan": f["type"], "rent": f["scheduled"], "movein": f["move_in"], "leased": leased})
    return out


def _half_up(v):
    return int(v + 0.5)


def rent(rr, av, mode):
    """Rent figures. leaseup (Grove): signed leases, budget on the same suites, loss to lease, committed, full budget.
    stabilised (Faculty47): rent in place on occupied suites and rent of leased move-ins."""
    budget_av = {u["unit"]: u["budget_rent"] for u in (av or {"units": []})["units"]}
    first = {}
    for f in rr["future"]:
        first.setdefault(f["unit"], f)  # one lease per suite: the first future resident
    sqft = {s["unit"]: s["sqft"] for s in rr["suites"]}
    budget = {s["unit"]: budget_av.get(s["unit"], s["budget_rent"]) for s in rr["suites"]}
    fut = {u: f for u, f in first.items() if f["scheduled"] is not None}
    leased = {u: f for u, f in fut.items() if _leased(f)}
    occ = [s for s in rr["suites"] if s["status"].startswith("Occupied")]
    rentable = [s for s in rr["suites"] if not s["status"].startswith("Excluded")]
    out = {"fullBudget": round(sum(budget[s["unit"]] for s in rentable), 2), "fullCount": len(rentable)}
    if mode == "leaseup":
        signed = round(sum(f["scheduled"] for f in leased.values()), 2)
        signed_budget = round(sum(budget[u] for u in leased), 2)
        out.update({"signed": signed, "signedCount": len(leased), "signedBudget": signed_budget, "lossToLease": round(signed_budget - signed, 2),
                    "committed": round(sum(f["scheduled"] for f in fut.values()), 2), "committedCount": len(fut)})
        if leased:
            out["avgSuite"] = _half_up(signed / len(leased))
            out["avgSqft"] = round(signed / sum(sqft[u] for u in leased), 2)
    else:
        in_place = round(sum(s["scheduled"] for s in occ), 2)
        out.update({"inPlace": in_place, "occupiedCount": len(occ), "futureRent": round(sum(f["scheduled"] for f in leased.values()), 2)})
        if occ:
            out["avgSuite"] = _half_up(in_place / len(occ))
            out["avgSqft"] = round(in_place / sum(s["sqft"] for s in occ), 2)
    return out


def arrears(ar):
    rows = ar["rows"]
    cur = [r for r in rows if r["kind"] == "current"]
    former = [r for r in rows if r["kind"] == "former" and r["balance"] > 0]
    return {
        "owing": round(sum(r["d31_60"] + r["d61_90"] + r["d90_plus"] for r in cur), 2),
        "due": round(sum(r["d0_30"] for r in cur), 2),
        "former": round(sum(r["balance"] for r in former), 2), "formerCount": len(former),
        "future_charges": round(sum(r["charges"] for r in rows if r["kind"] == "future"), 2),
        "owing_rows": [[r["unit"] or "Parking", r["resident"], r["d0_30"], r["d31_60"], r["d61_90"], r["d90_plus"], r["balance"]]
                       for r in rows if r["balance"] > 0],
    }


def add_months(iso, n):
    """'2026-10-01' + 12 months -> '2027-10-01'. A day that does not exist in the new month moves to its last day."""
    y, m, d = int(iso[:4]), int(iso[5:7]), int(iso[8:10])
    m0 = m - 1 + n
    y, m = y + m0 // 12, m0 % 12 + 1
    last = [31, 29 if y % 4 == 0 and (y % 100 != 0 or y % 400 == 0) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][m - 1]
    return f"{y:04d}-{m:02d}-{min(d, last):02d}"


def add_days(iso, n):
    from datetime import date, timedelta
    d = date(int(iso[:4]), int(iso[5:7]), int(iso[8:10])) + timedelta(days=n)
    return d.isoformat()


def resident_names(rr):
    """Every resident named on the Rent Roll (current and future), as the report writes them."""
    names = [s["resident"] for s in rr["suites"] if s.get("resident")] + [f["resident"] for f in rr["future"] if f.get("resident")]
    return sorted(set(n.strip() for n in names if n and n.strip()))


def leases(rr):
    """Every lease on the Rent Roll: current residents and future residents. One row per lease."""
    out = []
    for s in rr["suites"]:
        if s["status"].startswith("Occupied") and s.get("resident"):
            out.append({"num": s["unit"], "rent": s.get("scheduled"), "start": s.get("lease_start"), "end": s.get("lease_end")})
    for f in rr["future"]:
        out.append({"num": f["unit"], "rent": f.get("scheduled"), "start": f.get("lease_start"), "end": f.get("lease_end")})
    return out


def renewals(rr, ex, today):
    """Lease ends from the Rent Roll. byEnd is [date, count] pairs for the next 12 months only (from today,
    which is dataThrough). firstEnd is the earliest lease end overall. expiring120 is the Expiring Leases count."""
    ends = sorted(l["end"] for l in leases(rr) if l["end"])
    horizon = add_months(today, 12)
    by = Counter(e for e in ends if today <= e <= horizon)
    return {"expiring120": len(ex["rows"]) if ex else None, "firstEnd": ends[0] if ends else None,
            "byEnd": [[d, c] for d, c in sorted(by.items())]}


def increases(rr, today, window_months=6):
    """Rent increases due, one row per lease: {num, rent, earliest, noticeBy}. The dashboard shows when an increase is
    due, not the amount, so there is no new rent. The earliest date a new rent can take effect is 12 months after the
    rent last changed (the lease start on the Rent Roll), and notice is due 90 days before that. Only leases whose
    notice date falls by today + 6 months are listed (notices already due included). today is the run date."""
    horizon = add_months(today, window_months)
    rows = []
    for l in leases(rr):
        if not l["start"] or not l["rent"]:
            continue
        earliest = add_months(l["start"], 12)
        notice = add_days(earliest, -90)
        if notice <= horizon:
            rows.append({"num": l["num"], "rent": l["rent"], "earliest": earliest, "noticeBy": notice})
    return sorted(rows, key=lambda r: (r["noticeBy"], r["num"]))


def concessions(cn, rr):
    """One row per lease: recurring plus one-time together, cancelled leases excluded."""
    plan = {s["unit"]: s["type"] for s in rr["suites"]}
    by = {}
    for r in cn["rows"]:
        if r["status"] == "Cancelled":
            continue
        d = by.setdefault(r["unit"], {"unit": r["unit"], "plan": plan.get(r["unit"], ""), "term": f'{r["term_months"]} months', "total": 0.0})
        d["total"] = round(d["total"] - r["total"], 2)  # the report shows concessions as negatives
    units = list(by.values())
    return {"units": units, "total": round(sum(u["total"] for u in units), 2)}


def parking(ri):
    items = ri["items"]
    return {"list": [[i["stall"], i["status"], i["unit"]] for i in items],
            "occupied": sum(1 for i in items if i["status"] in ("Occupied", "Reserved")), "total": len(items)}


MONTHS = {m: i + 1 for i, m in enumerate(["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"])}


def period_month(bva):
    """'Sep 2026' on the Budget vs Actual header -> '2026-09'. Falls back to the month before the export date."""
    m = re.match(r"^([A-Z][a-z]{2}) (\d{4})$", (bva.get("period") or "").strip())
    if m and m.group(1) in MONTHS:
        return f"{m.group(2)}-{MONTHS[m.group(1)]:02d}"
    d = bva.get("as_of") or bva.get("data_as_of") or ""
    y, mo = int(d[:4]), int(d[5:7])
    return f"{y - 1}-12" if mo == 1 else f"{y}-{mo - 1:02d}"


def budget(bva, t12):
    g = {x["name"]: x for x in bva["groups"]}
    noi = g["Net Operating Income"]
    row = next(r for r in t12["rows"] if r["name"] == "Net Operating Income")
    last = period_month(bva)  # only the post month the statements report and earlier; never a partial current month
    series = [(m, row["by_month"][m]) for m in sorted(t12["months"]) if m <= last]
    while series and series[0][1] == 0:  # leading months before the property had activity
        series.pop(0)
    return {"noi": [noi["actual"], noi["budget"], noi["ytd_actual"], noi["ytd_budget"]], "annualNoi": noi["annual_budget"],
            "period": last, "noiMonths": [m for m, _ in series], "noiTrend": [v for _, v in series],
            "lines": budget_lines(bva)[0], "unknownHeadings": budget_lines(bva)[1]}


def month_of_label(label):
    """'Sep 2026' (or 'Sep 2026, run 2026-10-01') -> '2026-09'; None when it does not start with a month."""
    m = re.match(r"^([A-Z][a-z]{2}) (\d{4})", (label or "").strip())
    return f"{m.group(2)}-{MONTHS[m.group(1)]:02d}" if m and m.group(1) in MONTHS else None


def budget_status(new, old):
    """How today's income statements compare with the budget section already in the feed.
    Only the post month the statements report is used (never a partial current month).
      keep      - same post month and nothing changed: leave the section exactly as it is
      restated  - closed months whose figures changed since the last run (update them and say "restated")
      behind    - the report's month is earlier than the feed's: keep the feed's figures and flag it"""
    old = old or {}
    prev = month_of_label(old.get("period"))
    out = {"period": new["period"], "previousPeriod": prev, "periodChanged": prev != new["period"], "restated": [], "behind": False}
    if prev and new["period"] < prev:
        out.update(behind=True, keep=True)
        return out
    changed = set()
    for m, v in zip(old.get("noiMonths", []), old.get("noiTrend", [])):
        if m in new["noiMonths"] and abs(new["noiTrend"][new["noiMonths"].index(m)] - v) > 0.01:
            changed.add(m)
    if prev == new["period"]:
        same = len(old.get("noi", [])) == len(new["noi"]) and all(abs(a - b) <= 0.01 for a, b in zip(old["noi"], new["noi"]))
        old_lines = {l[0]: l[1:] for l in old.get("lines", [])}
        new_lines = {l[0]: l[1:] for l in new["lines"]}
        if not same or old.get("annualNoi") is None or abs(old["annualNoi"] - new["annualNoi"]) > 0.01 or old_lines.keys() != new_lines.keys() or \
                any(abs(a - b) > 0.01 for k in new_lines for a, b in zip(old_lines[k], new_lines[k])):
            changed.add(new["period"])
    out["restated"] = sorted(changed)
    out["keep"] = prev == new["period"] and not changed
    return out


# Budget vs Actual heading -> plain label shown to the owner. Headings that are subtotals are ignored.
BUDGET_LABELS = {
    "Net Rental Income": "Rental income", "Other Income": "Other income", "Administrative Expense": "Administration", "Payroll": "Payroll",
    "Management Fees": "Management fees", "Advertising & Promotion": "Advertising and promotion",
    "Telecommunication Services": "Telecommunications", "Utility Expense": "Utilities", "Outside Services": "Outside services",
    "Contract Services": "Contract services", "Repairs & Maintenance": "Repairs and maintenance",
    "Turnover & Recoverable Costs": "Turnover costs", "Taxes & Insurance": "Taxes and insurance",
}
BUDGET_SUBTOTALS = {"Potential Gross Income", "Effective Gross Income", "Net Operating Income", "Non-operating Expenses", "Net Income"}
INTEREST_ONLY = "Interest on LMR Bank"


def budget_lines(bva):
    """[[label, month actual, month budget, ytd actual, ytd budget], ...] and the headings the table does not know.
    A group whose only account is the deposit interest is labelled for what it is."""
    lines, unknown = [], []
    for g in bva["groups"]:
        name = g["name"]
        if name in BUDGET_SUBTOTALS:
            continue
        label = BUDGET_LABELS.get(name)
        if label is None:
            unknown.append(name)
            continue
        accts = [a["name"] for a in bva["accounts"] if a["group"] == name]
        if name == "Other Income" and accts == [INTEREST_ONLY]:
            label = "Interest on last month's rent deposits"
        lines.append([label, g["actual"], g["budget"], g["ytd_actual"], g["ytd_budget"]])
    return lines, unknown


def funnel(lt):
    return {"stages": lt["stages"], "total": lt["total"], "avgTotal": lt["avg_total"],
            "leads": lt["stages"][0][1], "apps": sum(s[1] for s in lt["stages"][1:5])}


CLOSED = ("completed", "cancelled", "canceled", "closed")


def open_work_orders(wo):
    """Orders still open. The report also lists finished ones; those are dropped."""
    return [o for o in wo["orders"] if (o["status"] or "").lower() not in CLOSED]


def snapshot(reports, date):
    """The day's history entry, dated with dataThrough. A field is None when its report is missing.
    holds = suites Availability shows as rented with no one on the Rent Roll (counts.applications)."""
    rr, av = reports.get("Rent Roll"), reports.get("Availability")
    al = reports.get("Activity Log")
    c = counts(rr, av) if rr and av else None
    lt = funnel(reports["Lease Term Progress Summary"]) if reports.get("Lease Term Progress Summary") else None
    ri = reports.get("Rentable Items Availability")
    ar = reports.get("Resident Aged Receivables")
    wo = reports.get("Work Order Details")
    from .activity_log import dedupe
    return {
        "date": date,
        "leads": lt["leads"] if lt else None, "apps": lt["apps"] if lt else None,
        "leased": (c["leased"] + c["occupied"]) if c else None,  # Faculty47 counts occupied suites as leased; the Grove has none
        "inProgress": c["inProgress"] if c else None, "holds": c["applications"] if c else None,
        "available": c["available"] if c else None,
        "parking": parking(ri)["occupied"] if ri else None,
        "wo": len(open_work_orders(wo)) if wo else None,
        "owing": arrears(ar)["owing"] if ar else None,
        "tours": sum(1 for e in dedupe(al["entries"]) if e["type"] == "Tour") if al else None,
    }
