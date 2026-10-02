"""Concessions: one row per lease, with recurring and one-time amounts."""
import re

from ..common import NUM, num, read_lines, header_info

ROW = re.compile(
    r"^(?P<unit>\S+) (?P<res>.+?) (?P<status>Current|Future|Cancelled|Past|Notice|Applicant)(?: -[ A-Za-z]+?)? (?P<term>\d+) months? "
    r"(?P<nums>(?:" + NUM + r" ?){7})$")


def parse(path):
    lines = read_lines(path)
    out = {"report": "Concessions", **header_info(lines), "rows": [], "totals": None}
    for ln in lines:
        s = ln.strip()
        if s.startswith("Concessions Burn-off"):
            break
        if s.startswith("Total/Average:"):
            out["totals"] = [num(x) for x in re.findall(NUM, s)]
            continue
        m = ROW.match(s)
        if m:
            n = [num(x) for x in re.findall(NUM, m["nums"])]
            out["rows"].append({"unit": m["unit"], "resident": m["res"], "status": m["status"], "term_months": int(m["term"]),
                                "recurring": n[0], "one_time": n[1], "total": n[2], "remaining": n[3],
                                "market_rent": n[4], "lease_rent": n[5], "effective_rent": n[6]})
    return out
