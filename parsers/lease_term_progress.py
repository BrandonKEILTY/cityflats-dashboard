"""Lease Term Progress Summary: funnel counts and average time in each status."""
import re

from .common import read_lines, header_info

STAGES = ["Guest card completed", "Application started", "Application partially completed", "Application completed",
          "Application approved", "Lease started", "Lease partially completed", "Lease completed", "Lease approved"]
TIME = re.compile(r"\d\d:\d\d:\d\d")


def parse(path):
    lines = read_lines(path)
    out = {"report": "Lease Term Progress Summary", **header_info(lines)}
    prop = out["property"]
    counts = times = None
    for i, ln in enumerate(lines):
        s = ln.strip()
        if s.startswith(prop + " ") and re.fullmatch(r"(\d+ ?)+", s[len(prop):].strip()):
            nums = [int(x) for x in s[len(prop):].split()]
            counts = nums
        elif s.startswith(prop + " ") and TIME.search(s):
            times = TIME.findall(s)
    if counts is None or len(counts) != len(STAGES) + 1:
        raise ValueError(f"lease term progress: expected {len(STAGES) + 1} counts, got {counts}")
    out["stages"] = [[name, counts[i], (times[i] if times and i < len(times) - 1 else None)] for i, name in enumerate(STAGES)]
    out["total"] = counts[-1]
    out["avg_total"] = times[-1] if times else None
    out["times_found"] = len(times or [])
    return out
