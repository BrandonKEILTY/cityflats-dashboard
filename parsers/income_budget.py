"""Income Statement - Budget vs Actual, from the Excel text. LAYOUT_CHECKED: yes (Grove and Faculty47 workbooks).

Columns are read by position after 'Account Name': month actual, budget, $ variance, % variance,
actual vs prior year, then year-to-date actual, budget, $ variance, % variance, YTD (prior year), annual budget."""
from . import xlsxtext as x

LAYOUT_CHECKED = True
KEY = "income statement - budget vs actual"
COLS = ["actual", "budget", "var", "var_pct", "vs_prior_year", "ytd_actual", "ytd_budget", "ytd_var", "ytd_var_pct", "ytd_prior", "annual_budget"]


def parse(lines):
    info = x.title_info(lines)
    rows = [x.cells(l) for l in lines]
    h = x.header_index(rows, "Property", "Account", "Account Name", "Actual", "Budget")
    start = x.col(x.columns(rows[h]), "account name") + 1
    out = {"report": "Income Statement - Budget vs Actual", **info, "groups": [], "accounts": []}
    cur = None
    for r in rows[h + 1:]:
        nonblank = [c for c in r if c.strip()]
        if not nonblank:
            continue
        name = x.get(r, 2)
        vals = {k: x.num(x.get(r, start + i)) for i, k in enumerate(COLS)}
        if len(nonblank) == 1:  # section heading, e.g. "Payroll"
            cur = nonblank[0].strip()
        elif x.get(r, 1):  # account row: property, code, name, figures
            out["accounts"].append({"group": cur, "code": x.get(r, 1), "name": name, **vals})
        elif name:  # group total, e.g. "Payroll" or "Net Operating Income"
            out["groups"].append({"name": name, **vals})
    if not any(g["name"] == "Net Operating Income" for g in out["groups"]):
        raise x.LayoutError("budget vs actual: Net Operating Income row not found")
    return out
