import re

import pdfplumber

NUM = r"\(?-?[\d,]+\.\d\d\)?"
NUM_RE = re.compile(r"^" + NUM + r"$")
DATE_RE = re.compile(r"\d{4}-\d\d-\d\d")


def num(s):
    """'1,234.50' -> 1234.5, '(1,234.50)' -> -1234.5, '12.5%' -> 12.5, '' or '-' -> None."""
    if s is None:
        return None
    s = str(s).strip().replace("$", "").replace("%", "")
    if s in ("", "-", "--"):
        return None
    neg = s.startswith("(") and s.endswith(")")
    s = s.strip("()").replace(",", "")
    v = float(s)
    return -v if neg else v


def read_lines(path):
    """Text of every page in reading order. use_text_flow keeps wrapped cells together."""
    out = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            out.extend((page.extract_text(use_text_flow=True) or "").split("\n"))
    return out


def read_pages_words(path):
    with pdfplumber.open(path) as pdf:
        return [page.extract_words() for page in pdf.pages]


def header_info(lines):
    """Report title, property name and the 'data as of' stamp."""
    info = {"title": lines[0].strip() if lines else "", "property": lines[1].strip("' ") if len(lines) > 1 else ""}
    for ln in lines:
        m = re.search(r"data as of (\d{4}-\d\d-\d\d) (\d\d:\d\d [ap]\.m\. \w+)", ln)
        if m:
            info["data_as_of"] = m.group(1)
            info["data_as_of_time"] = m.group(2)
            break
    for ln in lines[:6]:
        m = re.match(r"As of (\d{4}-\d\d-\d\d)", ln)
        if m:
            info["as_of"] = m.group(1)
    return info


def nearest_rows(words, anchors):
    """Assign each word to the anchor (a y position) it is closest to. Entrata centres
    wrapped cells on the row, so nearest-anchor groups a row's wrapped lines together."""
    rows = [[] for _ in anchors]
    for w in words:
        i = min(range(len(anchors)), key=lambda k: abs(w["top"] - anchors[k]))
        rows[i].append(w)
    return rows


def join_words(words, x_lo=None, x_hi=None):
    ws = [w for w in words if (x_lo is None or w["x0"] >= x_lo) and (x_hi is None or w["x0"] < x_hi)]
    ws.sort(key=lambda w: (round(w["top"] / 3), w["x0"]))
    return " ".join(w["text"] for w in ws)


def runs_by_anchor(words, anchors, line_gap=2.5):
    """Split words (a column of wrapped text) into one contiguous run of lines per
    anchor, in order, so each run's centre lies as close as possible to its anchor.
    Needed where records differ in height, so 'nearest anchor' puts lines in the wrong record."""
    if not words:
        return [[] for _ in anchors]
    ws = sorted(words, key=lambda w: (w["top"], w["x0"]))
    lines = []
    for w in ws:
        if lines and abs(w["top"] - lines[-1][0]["top"]) <= line_gap:
            lines[-1].append(w)
        else:
            lines.append([w])
    tops = [sum(w["top"] for w in ln) / len(ln) for ln in lines]
    n, k = len(lines), len(anchors)
    if n < k:
        raise ValueError("fewer text lines than records")
    inf = float("inf")
    # best[j][i]: cost of assigning the first i lines to the first j anchors
    best = [[inf] * (n + 1) for _ in range(k + 1)]
    cut = [[0] * (n + 1) for _ in range(k + 1)]
    best[0][0] = 0.0
    for j in range(1, k + 1):
        for i in range(j, n + 1):
            for s in range(j - 1, i):
                if best[j - 1][s] == inf:
                    continue
                centre = (tops[s] + tops[i - 1]) / 2
                cost = best[j - 1][s] + (centre - anchors[j - 1]) ** 2
                if cost < best[j][i]:
                    best[j][i], cut[j][i] = cost, s
    out, i = [], n
    for j in range(k, 0, -1):
        s = cut[j][i]
        out.append([w for ln in lines[s:i] for w in ln])
        i = s
    return out[::-1]
