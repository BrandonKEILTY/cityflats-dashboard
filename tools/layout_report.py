"""Show what the five not-yet-checked parsers read from a folder of saved Excel text, so it can be compared
with the same report's PDF by eye.

    python tools/layout_report.py work/YYYY-MM-DD grove|f47

Prints, per report: found or not, the sheet's header cells, what was read (counts, totals, first rows) and
any error. A parser is ready to have LAYOUT_CHECKED set to True only when these match the PDF and a test has
been added from the real export.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from parsers import derive, registry, xlsxtext as x  # noqa: E402

UNCHECKED = ["Availability", "Lease Term Progress Summary", "Activity Log", "Rentable Items Availability", "Expiring Leases"]


def summary(report, r):
    if report == "Availability":
        return {"sections": r["sections"], "units": len(r["units"]), "totals": r["totals"], "first": r["units"][:2]}
    if report == "Lease Term Progress Summary":
        return {"stages": r["stages"], "total": r["total"], "avg_total": r["avg_total"], "apps": derive.funnel(r)["apps"]}
    if report == "Activity Log":
        from parsers.activity_log import dedupe
        d = dedupe(r["entries"])
        return {"rows": len(r["entries"]), "after_dedupe": len(d), "tours": sum(1 for e in d if e["type"] == "Tour"),
                "activity_date": r.get("activity_date"), "first": d[:2]}
    if report == "Rentable Items Availability":
        p = derive.parking(r)
        return {"declared": r["declared"], "stalls": p["total"], "occupied+reserved": p["occupied"], "first": p["list"][:3]}
    return {"no_data": r["no_data"], "rows": r["rows"][:3], "row_count": len(r["rows"])}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("folder")
    ap.add_argument("prop", choices=sorted(registry.PROPERTY))
    a = ap.parse_args()
    prop = registry.PROPERTY[a.prop]
    sheets = registry._sheets(a.folder)
    for report in UNCHECKED:
        mod = registry.MODULES[report]
        found = [(f, n, l) for f, n, l in sheets if registry._match(report, x.title_info(l)["title"]) and x.title_info(l)["property"].lower() == prop.lower()]
        print(f"\n=== {report} ({prop})")
        if not found:
            print("  no sheet found")
            continue
        f, name, lines = found[0]
        print(f"  file {f}, sheet {name!r}, {len(lines)} lines, title line: {x.title_info(lines)}")
        for ln in lines[:12]:
            if ln.count("\t") >= 3:
                print("  header-ish:", [c for c in ln.split("\t") if c.strip()][:14])
                break
        try:
            print("  read:", summary(report, mod.parse(lines)))
        except x.LayoutError as e:
            print("  NOT READABLE:", e)


if __name__ == "__main__":
    main()
