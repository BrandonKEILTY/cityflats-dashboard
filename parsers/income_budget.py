"""Income Statement - Budget vs Actual (month and year to date)."""
import re

from .common import read_lines, header_info, num

VAL = r"\(?-?[\d,]+\.\d\d\)?%?"
COLS = ["actual", "budget", "var", "var_pct", "vs_prior_year", "ytd_actual", "ytd_budget", "ytd_var", "ytd_var_pct", "ytd_prior", "annual_budget"]
ACCOUNT = re.compile(r"^(?P<prop>.+?) (?P<code>\d{3}-\d{3}) (?P<name>.+?) (?P<vals>(?:" + VAL + r" ?){11})$")
GROUP = re.compile(r"^(?P<name>[A-Za-z&,' ]+?) (?P<vals>(?:" + VAL + r" ?){11})$")


def _vals(s):
    return dict(zip(COLS, (num(x) for x in re.findall(VAL, s))))


def parse(path):
    lines = read_lines(path)
    info = header_info(lines)
    out = {"report": "Income Statement - Budget vs Actual", **info, "period": lines[2].strip() if len(lines) > 2 else None, "groups": [], "accounts": []}
    cur = None
    for ln in lines:
        s = ln.strip()
        m = ACCOUNT.match(s)
        if m:
            out["accounts"].append({"group": cur, "code": m["code"], "name": m["name"].strip(), **_vals(m["vals"])})
            continue
        m = GROUP.match(s)
        if m:
            out["groups"].append({"name": m["name"].strip(), **_vals(m["vals"])})
            continue
        if re.fullmatch(r"[A-Za-z&,' ]+", s) and s not in ("Accrual Basis",):
            cur = s
    return out
