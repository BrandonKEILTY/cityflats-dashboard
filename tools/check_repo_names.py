"""Fail if a resident or prospect name appears in a file that is (or is about to be) committed.

    python tools/check_repo_names.py --figures work/D/grove.json --figures work/D/f47.json --feed work/D/feed.json [paths...]
    python tools/check_repo_names.py --names-file names.json --history        # which commits already hold a name

Names come from: the Rent Roll residents in each parsers.figures output (--figures), the arrears table and prospects
of an un-anonymised feed (--feed), and any JSON list of names (--names-file). Matches "First Last" (up to two middle
words) and "Last, First". A last or first name alone is not matched. With no paths it checks every tracked file.
--history reports, for every commit on every branch, the files that hold a name; it never changes anything.
"""
import argparse
import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools.check_feed import name_patterns  # noqa: E402

BINARY = (".png", ".jpg", ".jpeg", ".gif", ".pdf", ".ico", ".woff", ".woff2", ".zip", ".xlsx")


def collect_names(figures=(), feed=None, names_files=()):
    names = set()
    for path in figures:
        names |= set(json.load(open(path)).get("residents", []))
    if feed:
        f = json.load(open(feed))
        for p in f["properties"]:
            names |= {r[1] for r in (p.get("arrears") or {}).get("detail", []) or [] if len(r) > 1 and r[1]}
            names |= {x["name"] for x in p.get("prospects", []) or [] if x.get("name")}
    for path in names_files:
        names |= set(json.load(open(path)))
    return sorted(n for n in names if name_patterns(n))


def git_regex(names):
    """One extended regex for git grep, built from the same two forms the patterns use."""
    parts = []
    for n in names:
        n = " ".join(n.split())
        if "," in n:
            last, first = [x.strip() for x in n.split(",", 1)]
        else:
            toks = n.split()
            first, last = toks[0], " ".join(toks[1:])
        ft = first.split()[0]
        parts.append(rf"{re.escape(ft)}[[:space:]]+([[:alnum:].'-]+[[:space:]]+){{0,2}}{re.escape(last)}")
        parts.append(rf"{re.escape(last)},[[:space:]]*{re.escape(ft)}")
    return "|".join(parts)


def scan_text(text, names):
    pats = [(n, p) for n in names for p in name_patterns(n)]
    return sorted({n for n, p in pats if p.search(text)})


def tracked_files():
    return subprocess.run(["git", "ls-files"], capture_output=True, text=True, check=True).stdout.split("\n")[:-1]


def check_paths(paths, names):
    bad = []
    for path in paths:
        if path.lower().endswith(BINARY) or not os.path.isfile(path):
            continue
        try:
            text = open(path, encoding="utf-8").read()
        except UnicodeDecodeError:
            continue
        hits = scan_text(text, names)
        if hits:
            bad.append((path, hits))
    return bad


def history(names):
    """[(commit, date, subject, [files])] for every commit on every ref that holds a name."""
    rx = git_regex(names)
    commits = subprocess.run(["git", "rev-list", "--all", "--date-order", "--format=%H|%ad|%s", "--date=short"], capture_output=True, text=True, check=True).stdout.split("\n")
    out = []
    for line in commits:
        if "|" not in line:
            continue
        sha, date, subject = line.split("|", 2)
        r = subprocess.run(["git", "grep", "-l", "-i", "-E", rx, sha], capture_output=True, text=True)
        files = sorted({x.split(":", 1)[1] for x in r.stdout.split("\n") if ":" in x and not x.lower().endswith(BINARY)})
        if files:
            out.append((sha, date, subject, files))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="*")
    ap.add_argument("--figures", action="append", default=[])
    ap.add_argument("--feed")
    ap.add_argument("--names-file", action="append", default=[])
    ap.add_argument("--history", action="store_true")
    a = ap.parse_args()
    names = collect_names(a.figures, a.feed, a.names_file)
    if not names:
        print("FAIL: no names supplied (use --figures, --feed or --names-file), so nothing can be checked")
        sys.exit(2)
    if a.history:
        for sha, date, subject, files in history(names):
            print(f"{sha[:10]} {date} {subject}\n    {', '.join(files)}")
        return
    bad = check_paths(a.paths or tracked_files(), names)
    for path, hits in bad:
        print(f"FAIL {path}: {len(hits)} name(s), e.g. {hits[0].split(',')[0]!r}")
    print("repo names:", "FAILED" if bad else f"passed ({len(names)} names checked)")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
