"""Resident Aged Receivables.

Rows are read by word position because names, lease status and notes wrap around the
number cells. Every row is returned with its raw columns; deciding what counts as
"owing" (current residents, 31+ days) is done in derive.py.
"""
import re

import pdfplumber

from .common import NUM_RE, num, header_info, nearest_rows, join_words

NUM_COLS = ["charges", "d0_30", "d31_60", "d61_90", "d90_plus", "prepayments", "balance"]


def _classify(status):
    s = status.lower()
    if s.startswith("current"):
        return "current"
    if s.startswith("future"):
        return "future"
    if s.startswith("past"):
        return "former"
    return "other"


def parse(path):
    rows, totals, lines = [], None, []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            words = page.extract_words()
            lines.extend((page.extract_text(use_text_flow=True) or "").split("\n"))
            hdr = {w["text"]: w for w in words if w["top"] < 160}
            x_unit_hi = hdr["Resident"]["x0"] - 4
            x_status = hdr["Lease"]["x0"] - 4
            x_num_lo = x_status + 38
            x_note = hdr["Last"]["x0"] - 4
            label_tops = [w["top"] for w in words if w["text"] in ("Property:", "Property")]
            body = [w for w in words if 140 < w["top"] < 760 and not any(abs(w["top"] - t) < 2 for t in label_tops)]
            bal_x1 = hdr["Balance"]["x1"]
            # anchors: the Balance cell of each row (and of the Total row)
            anchors = sorted({round(w["top"], 1) for w in body if NUM_RE.match(w["text"]) and abs(w["x1"] - bal_x1) <= 6})
            if not anchors:
                continue
            main = [w for w in body if w["x0"] < x_note]
            notes = sorted([w for w in body if w["x0"] >= x_note], key=lambda w: w["top"])
            groups = nearest_rows(main, anchors)
            # a note is a block of consecutive lines: place the whole block at once
            block, blocks = [], []
            for w in notes:
                if block and w["top"] - block[-1]["top"] > 10:
                    blocks.append(block)
                    block = []
                block.append(w)
            if block:
                blocks.append(block)
            for b in blocks:
                centre = (min(w["top"] for w in b) + max(w["top"] for w in b)) / 2
                i = min(range(len(anchors)), key=lambda k: abs(centre - anchors[k]))
                groups[i].extend(b)
            for top, grp in zip(anchors, groups):
                nums = sorted([w for w in grp if NUM_RE.match(w["text"]) and x_num_lo <= w["x0"] < x_note], key=lambda w: w["x0"])
                unit = join_words(grp, 0, x_unit_hi)
                resident = join_words(grp, x_unit_hi, x_status)
                status = join_words(grp, x_status, x_num_lo)
                note = join_words(grp, x_note, None)
                if len(nums) != 7:
                    raise ValueError(f"receivables row at y={top}: expected 7 amounts, got {len(nums)}")
                vals = dict(zip(NUM_COLS, (num(w["text"]) for w in nums)))
                if "Total" in status or "Total:" in unit + resident:
                    totals = vals
                    continue
                rows.append({"unit": unit, "resident": resident, "status": status, "kind": _classify(status), "note": note, **vals})
    return {"report": "Resident Aged Receivables", **header_info(lines), "rows": rows, "totals": totals}
