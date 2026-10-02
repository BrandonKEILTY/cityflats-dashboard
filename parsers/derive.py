"""Figures the dashboard shows, worked out from the parsed reports with the rules in
daily-job-rules.md. Numbers only; client wording is not written here."""
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


def deals(rr):
    out = []
    for f in rr["future"]:
        if f["scheduled"] is not None:
            out.append({"unit": f["unit"], "plan": f["type"], "rent": f["scheduled"], "movein": f["move_in"], "leased": _leased(f)})
    return out


def rent(rr, av):
    fut = [f for f in rr["future"] if f["scheduled"] is not None]
    leased = [f for f in fut if _leased(f)]
    occ = [s for s in rr["suites"] if s["status"].startswith("Occupied")]
    non_ex = [s for s in rr["suites"] if not s["status"].startswith("Excluded")]
    out = {
        "committed": sum(f["scheduled"] for f in fut), "committedCount": len(fut),
        "signed": sum(f["scheduled"] for f in leased), "signedCount": len(leased),
        "inPlace": sum(s["scheduled"] for s in occ), "occupiedCount": len(occ),
        "futureRent": sum(f["scheduled"] for f in leased),
        "fullBudget": sum(s["budget_rent"] for s in non_ex), "fullCount": len(non_ex),
    }
    if occ:  # stabilised building: average rent in place
        out["avgSuite"] = round(out["inPlace"] / len(occ))
    elif leased:  # lease-up: average of signed leases
        out["avgSuite"] = round(out["signed"] / len(leased))
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


def renewals(rr, ex):
    cur = [s for s in rr["suites"] if s["status"].startswith("Occupied")]
    pool = cur or rr["future"]
    ends = sorted(x["lease_end"] for x in pool if x.get("lease_end"))
    by = Counter(ends)
    return {"expiring120": len(ex["rows"]) if ex else None, "firstEnd": ends[0] if ends else None, "byEnd": sorted(by.items())}


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


def budget(bva, t12):
    g = {x["name"]: x for x in bva["groups"]}
    noi = g["Net Operating Income"]
    months = [m for m in t12["months"]]
    row = next(r for r in t12["rows"] if r["name"] == "Net Operating Income")
    as_of = (t12.get("as_of") or t12.get("data_as_of") or "")[:7]
    closed = sorted(m for m in months if m < as_of)
    series = [(m, row["by_month"][m]) for m in closed]
    while series and series[0][1] == 0:  # leading months before the property had activity
        series.pop(0)
    return {"noi": [noi["actual"], noi["budget"], noi["ytd_actual"], noi["ytd_budget"]], "annualNoi": noi["annual_budget"],
            "noiMonths": [m for m, _ in series], "noiTrend": [v for _, v in series],
            "lines": sorted(((x["actual"], x["budget"], x["ytd_actual"], x["ytd_budget"]) for x in bva["groups"]))}


def funnel(lt):
    return {"stages": lt["stages"], "total": lt["total"], "avgTotal": lt["avg_total"],
            "leads": lt["stages"][0][1], "apps": sum(s[1] for s in lt["stages"][1:5])}


CLOSED = ("completed", "cancelled", "canceled", "closed")


def open_work_orders(wo):
    """Orders still open. The report also lists finished ones; those are dropped."""
    return [o for o in wo["orders"] if (o["status"] or "").lower() not in CLOSED]
