"""Compare what the parsers read from one folder of PDFs with the figures in a feed.

    python -m parsers.compare <folder> grove|f47 [--feed feeds/2026-10-02.json] [--snapshot 2026-09-30]

Prints every difference. It never decides which side is right.
"""
import argparse
import json

import glob
import os

from . import activity_log, derive, registry
from .pdf import registry as pdf_registry


def _approx(a, b):
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(a - b) < 0.01
    return a == b


def run(folder, prop_id, feed_path, snapshot=None):
    feed = json.load(open(feed_path))
    p = next(x for x in feed["properties"] if x["id"] == prop_id)
    r = registry.load(folder, prop_id) if glob.glob(os.path.join(folder, '*.txt')) else pdf_registry.load(folder)
    diffs, notes = [], []

    def d(section, key, parsed, feed_val):
        if not _approx(parsed, feed_val):
            diffs.append((section, key, parsed, feed_val))

    for m in r["missing"]:
        notes.append(f"{m}: not in this folder (keep last figures, flag as missing)")
    rr, av = r["Rent Roll"], r["Availability"]
    al = activity_log.dedupe(r["Activity Log"]["entries"]) if r["Activity Log"] else None
    if rr and av:
        st = derive.stack(rr, av)
        d("stack", "suites", len(st), len(p["stack"]))
        feed_stack = {x[0]: (x[1], x[2]) for x in p["stack"]}
        for u, plan, s in st:
            if u in feed_stack and feed_stack[u] != (plan, s):
                diffs.append(("stack", u, [plan, s], list(feed_stack[u])))
        c = derive.counts(rr, av, al)
        for k in ("leased", "inProgress", "applications", "available"):
            d("counts", k, c[k], p["counts"].get(k))
        if "occupied" in p["counts"]:
            d("counts", "occupied", c["occupied"], p["counts"]["occupied"])
        mine = {x["unit"]: x for x in derive.deals(rr, p["mode"])}
        fd = {x["unit"]: x for x in p["deals"]}
        for u in sorted(set(mine) | set(fd)):
            if u not in fd:
                diffs.append(("deals", u, mine[u]["rent"], None))
            elif u not in mine:
                diffs.append(("deals", u, None, fd[u]["rent"]))
            else:
                d("deals", u + " rent", mine[u]["rent"], fd[u]["rent"])
                d("deals", u + " move-in", mine[u]["movein"][:10], str(fd[u]["movein"])[:10])
        rt, fr = derive.rent(rr, av, p["mode"]), p["rent"]
        for k in ("committed", "committedCount", "signed", "signedCount", "signedBudget", "lossToLease", "inPlace", "occupiedCount", "futureRent", "fullBudget", "fullCount", "avgSuite", "avgSqft"):
            if k in fr:
                d("rent", k, rt.get(k), fr[k])
        rn = derive.renewals(rr, r["Expiring Leases"])
        d("renewals", "firstEnd", rn["firstEnd"], p["renewals"].get("firstEnd"))
        if "byEnd" in p["renewals"]:
            d("renewals", "byEnd", [list(x) for x in rn["byEnd"]], p["renewals"]["byEnd"])
        inv = {x[0]: x for x in p["inventory"]["units"]}
        for s in av["units"]:
            f = inv.get(s["unit"])
            if f:
                for i, (k, v) in enumerate((("plan", s["plan"]), ("sqft", s["sqft"]), ("budget rent", s["budget_rent"]), ("available on", s["available_on"] or ""))):
                    d("inventory", f'{s["unit"]} {k}', v, f[i + 1] if i < 3 else f[4])
    if r["Resident Aged Receivables"]:
        a, fa = derive.arrears(r["Resident Aged Receivables"]), p["arrears"]
        d("arrears", "owing", a["owing"], fa.get("owing"))
        if "due" in fa:
            d("arrears", "due (0-30 days, current residents)", a["due"], fa["due"])
        if fa.get("detail"):
            mine = {(x[0], x[1].split(",")[0].strip().lower()): x for x in a["owing_rows"]}
            for row in fa["detail"]:
                key = (row[0], row[1].split()[-1].lower())
                hit = next((v for k, v in mine.items() if k[0] == key[0] and k[1] == key[1]), None)
                if hit is None:
                    diffs.append(("arrears detail", f"{row[0]} {row[1]}", None, row[7]))
                else:
                    d("arrears detail", f"{row[0]} {row[1]} balance", hit[6], row[7])
            have = {(r[0], r[1].split()[-1].lower()) for r in fa["detail"]}
            for k, v in mine.items():
                if k not in have:
                    diffs.append(("arrears detail", f"{v[0]} {v[1]}", v[6], None))
        if "former" in fa:
            d("arrears", "former", a["former"], fa["former"])
            d("arrears", "formerCount", a["formerCount"], fa["formerCount"])
        if "unallocated" in fa:
            d("arrears", "unallocated vs future-resident charges", a["future_charges"], fa["unallocated"])
    if r["Lease Term Progress Summary"]:
        f = derive.funnel(r["Lease Term Progress Summary"])
        fn = p["funnel"]
        d("funnel", "total", f["total"], fn["total"])
        d("funnel", "avgTotal", f["avgTotal"], fn["avgTotal"])
        for (n, cnt, t), (fn_n, fn_cnt, fn_t) in zip(f["stages"], fn["stages"]):
            d("funnel", n + " count", cnt, fn_cnt)
            d("funnel", n + " time", t, fn_t)
    if r["Concessions"] and rr:
        c = derive.concessions(r["Concessions"], rr)
        fc = {u["unit"]: u for u in p["concessions"]["units"]}
        d("concessions", "total", c["total"], p["concessions"]["total"])
        for u in c["units"]:
            if u["unit"] not in fc:
                diffs.append(("concessions", u["unit"], u["total"], None))
            else:
                d("concessions", u["unit"], u["total"], fc[u["unit"]]["total"])
        for u in fc:
            if u not in {x["unit"] for x in c["units"]}:
                diffs.append(("concessions", u, None, fc[u]["total"]))
    if r["Rentable Items Availability"]:
        pk, fi = derive.parking(r["Rentable Items Availability"]), p["items"]
        d("parking", "stalls", pk["total"], len(fi["list"]))
        d("parking", "occupied+reserved", pk["occupied"], fi.get("occupied"))
        ff = {x[0]: x for x in fi["list"]}
        for x in pk["list"]:
            if x[0] not in ff:
                diffs.append(("parking", x[0], x, None))
            elif ff[x[0]] != x:
                diffs.append(("parking", x[0], x, ff[x[0]]))
    if r["Income Statement - Budget vs Actual"] and r["Income Statement - Trailing 12"]:
        b, fb = derive.budget(r["Income Statement - Budget vs Actual"], r["Income Statement - Trailing 12"]), p["budget"]
        d("budget", "noi", b["noi"], fb["noi"])
        d("budget", "annualNoi", b["annualNoi"], fb["annualNoi"])
        d("budget", "noiMonths", b["noiMonths"], fb["noiMonths"])
        d("budget", "noiTrend", b["noiTrend"], fb["noiTrend"])
        mine = {l[0]: l[1:] for l in b["lines"]}
        for lab, *vals in fb["lines"]:
            if lab not in mine:
                diffs.append(("budget lines", lab, None, vals))
            elif not all(_approx(a, c) for a, c in zip(vals, mine[lab])):
                diffs.append(("budget lines", lab, mine[lab], vals))
        for lab in mine:
            if lab not in {l[0] for l in fb["lines"]}:
                diffs.append(("budget lines", lab, mine[lab], None))
        if b["unknownHeadings"]:
            notes.append(f"budget headings with no label in the table: {b['unknownHeadings']}")
    if r["Work Order Details"]:
        all_wo = r["Work Order Details"]["orders"]
        wo = {o["ref"]: o for o in derive.open_work_orders(r["Work Order Details"])}
        fw = {o["ref"]: o for o in p["workOrders"]}
        for ref, o in wo.items():
            if ref not in fw:
                diffs.append(("workOrders", ref, f'{o["status"]} {o["problem"]}', None))
                continue
            f = fw[ref]
            d("workOrders", ref + " status", (o["status"] or "").lower(), f["status"].lower())
            d("workOrders", ref + " created", o["created"], f["created"])
            d("workOrders", ref + " due", o["due"], f["due"])
            d("workOrders", ref + " age (days open)", o["days_open"], f["age"])
            d("workOrders", ref + " vendor", o["vendor"], f.get("vendor", ""))
            d("workOrders", ref + " unit", o["unit"], f["unit"])
        for ref in fw:
            if ref not in wo:
                diffs.append(("workOrders", ref, None, f'{fw[ref]["status"]} {fw[ref]["problem"]}'))
        notes.append(f'work orders read: {len(all_wo)} (report says {r["Work Order Details"]["declared"]}), {len(wo)} open')
    if al is not None:
        fe = {(e[0], e[1]) for pr in p["prospects"] for e in pr["entries"]}
        for e in al:
            if (e["when"], e["type"]) not in fe:
                diffs.append(("prospects", f'{e["name"]} {e["when"]} {e["type"]}', "in report", "not in feed"))
    if snapshot:
        h = next((x for x in p["history"] if x["date"] == snapshot), None)
        mine = derive.snapshot(r, snapshot)
        if h:
            for k, v in mine.items():
                if k != "date":
                    d(f"history {snapshot}", k, v, h.get(k))
        else:
            notes.append(f"no history snapshot dated {snapshot} in the feed")
    return diffs, notes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("folder")
    ap.add_argument("prop")
    ap.add_argument("--feed", default="feeds/2026-10-02.json")
    ap.add_argument("--snapshot")
    a = ap.parse_args()
    diffs, notes = run(a.folder, a.prop, a.feed, a.snapshot)
    for n in notes:
        print("NOTE", n)
    for s, k, parsed, feed in diffs:
        print(f"DIFF [{s}] {k}: parsed={parsed!r} feed={feed!r}")
    print(f"{len(diffs)} differences")


if __name__ == "__main__":
    main()
