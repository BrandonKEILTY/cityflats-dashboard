"""Reading the text the Outlook connector returns for an Excel (.xlsx) attachment.

Layout of that text (checked on the Cityflats ownership workbooks):
  - "=== Sheet: <name> ===" starts each sheet (the name is cut at 31 characters);
  - every spreadsheet row is a line, cells separated by tabs, empty cells kept;
  - a cell that contains a line break continues onto the next line;
  - dates are Excel serial numbers (46266 = 2026-09-01), numbers can carry float noise;
  - the first lines of a sheet are title, property, period.
"""
import re
from datetime import datetime, timedelta

SHEET = re.compile(r"^=== Sheet: (.*) ===\s*$")
EXCEL_EPOCH = datetime(1899, 12, 30)


class LayoutError(ValueError):
    """The text does not look like the layout this parser knows. Flag the report, keep its last figures."""


def split_sheets(text):
    """[(sheet name, [lines])] in order. Text with no sheet marker is one sheet called ''."""
    sheets, name, buf = [], None, []
    for line in text.replace("\r\n", "\n").split("\n"):
        m = SHEET.match(line)
        if m:
            if name is not None or buf:
                sheets.append((name or "", buf))
            name, buf = m.group(1), []
        else:
            buf.append(line)
    if name is not None or any(l.strip() for l in buf):
        sheets.append((name or "", buf))
    return [(n, [l for l in b]) for n, b in sheets]


def cells(line):
    return line.split("\t")


def num(s):
    """Cell -> number. '' -> None. Float noise is rounded to cents; whole numbers stay ints."""
    if s is None:
        return None
    s = str(s).strip()
    if s in ("", "-", "--"):
        return None
    neg = s.startswith("(") and s.endswith(")")
    s = s.strip("()").replace(",", "").replace("$", "").replace("%", "")
    try:
        v = float(s)
    except ValueError:
        raise LayoutError(f"not a number: {s!r}")
    v = -v if neg else v
    r = round(v, 2)
    return int(r) if r == int(r) and abs(r) < 1e15 else r


def to_number(s, default=None):
    try:
        v = num(s)
    except LayoutError:
        return default
    return default if v is None else v


def serial_to_datetime(v):
    return EXCEL_EPOCH + timedelta(seconds=round(float(v) * 86400))  # whole seconds, so 12:02:59.99 reads as 12:03


def date(s):
    """Cell -> 'YYYY-MM-DD'. Accepts an Excel serial number or text that already starts with an ISO date."""
    s = str(s or "").strip()
    if not s:
        return None
    if re.fullmatch(r"\d{4,6}(\.\d+)?", s):
        return serial_to_datetime(s).strftime("%Y-%m-%d")
    m = re.match(r"\d{4}-\d\d-\d\d", s)
    return m.group(0) if m else None


def get(row, i):
    return row[i].strip() if i is not None and i < len(row) else ""


def header_index(rows, *names, start=0):
    """Index of the first row at or after start whose cells include every name. Raises LayoutError."""
    want = {n.lower() for n in names}
    for i in range(start, len(rows)):
        have = {c.strip().lower() for c in rows[i]}
        if want <= have:
            return i
    raise LayoutError(f"header row with {', '.join(names)} not found")


def columns(header_row):
    """Header cell -> index of its first occurrence (case-insensitive)."""
    out = {}
    for i, c in enumerate(header_row):
        k = c.strip().lower()
        if k and k not in out:
            out[k] = i
    return out


def col(cols, name):
    if name.lower() not in cols:
        raise LayoutError(f"column {name!r} not found")
    return cols[name.lower()]


def title_info(lines):
    """Title, property (quotes stripped) and the third line (period or date range)."""
    ls = [l.split("\t")[0].strip() for l in lines[:6]]
    return {"title": ls[0] if ls else "", "property": ls[1].strip("' ") if len(ls) > 1 else "", "period": ls[2] if len(ls) > 2 else ""}


def merge_by_start(lines, is_start):
    """Join a cell's line breaks back into one logical row. A new row starts where is_start(line) is true;
    the lines in between are glued on with a line break so the tabs still split the right cells."""
    out = []
    for ln in lines:
        if is_start(ln) or not out:
            out.append(ln)
        else:
            out[-1] += "\n" + ln
    return out


def one_line(s):
    return re.sub(r"\s+", " ", s or "").strip()
