"""Income Statement - Trailing 12: 13 monthly columns, newest first."""
import re

from .common import read_lines, header_info, num

VAL = r"\(?-?[\d,]+\.\d\d\)?"
MONTH = r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec) \d{4}"
MONTHS = {m: i + 1 for i, m in enumerate(["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"])}


def parse(path):
    lines = read_lines(path)
    out = {"report": "Income Statement - Trailing 12", **header_info(lines), "months": [], "rows": []}
    for ln in lines:
        s = ln.strip()
        if s.startswith("Account Account Name Total"):
            ms = re.findall(MONTH, s)
            out["months"] = [f"{m[4:]}-{MONTHS[m[:3]]:02d}" for m in ms]
            continue
        m = re.match(r"^(?:(?P<code>\d{3}-\d{3}) )?(?P<name>[A-Za-z&,' -]+?) (?P<vals>(?:" + VAL + r" ?)+)$", s)
        if m and out["months"]:
            vals = [num(x) for x in re.findall(VAL, m["vals"])]
            if len(vals) == len(out["months"]) + 1:
                out["rows"].append({"code": m["code"], "name": m["name"].strip(), "total": vals[0], "by_month": dict(zip(out["months"], vals[1:]))})
    return out
