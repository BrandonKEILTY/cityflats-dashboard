"""Replace resident and prospect names with placeholders ("Resident 1", "Prospect 1"), keeping the shape.

    python tools/anonymise_feed.py work/D/feed.json feeds/D.json --figures work/D/grove.json --figures work/D/f47.json
    python tools/anonymise_feed.py --text data.js            # any text file, in place

The live dash/feed in the dashboard is the record and keeps the real names. The copy committed to git does not.
Names come from the feed itself (arrears table, prospects) and from the Rent Roll residents in --figures.
After writing, run tools/check_repo_names.py on the output.
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools.check_feed import name_patterns  # noqa: E402


def feed_names(feed):
    residents, prospects = [], []
    for p in feed["properties"]:
        residents += [r[1] for r in (p.get("arrears") or {}).get("detail", []) or [] if len(r) > 1 and r[1]]
        prospects += [x["name"] for x in p.get("prospects", []) or [] if x.get("name")]
    return residents, prospects


def canon(name):
    """The same person written '[name removed]' or '[name removed]' gets one key."""
    name = " ".join(name.split())
    if "," in name:
        last, first = [x.strip() for x in name.split(",", 1)]
    else:
        toks = name.split()
        first, last = toks[0], " ".join(toks[1:])
    return (first.split()[0].lower(), last.lower())


def placeholders(residents, prospects, extra_residents=(), label_r="Resident", label_p="Prospect"):
    """name -> placeholder, numbered in order of first appearance: the arrears residents, then the prospects, then
    any other Rent Roll residents. The same person written in two forms gets one placeholder (the first label)."""
    out, seen, r, p = {}, {}, 0, 0

    def add(n, label, count):
        n = " ".join(n.split())
        if not name_patterns(n):
            return count
        k = canon(n)
        if k not in seen:
            count += 1
            seen[k] = f"{label} {count}"
        out[n] = seen[k]
        return count

    for n in residents:
        r = add(n, label_r, r)
    for n in prospects:
        p = add(n, label_p, p)
    for n in extra_residents:
        r = add(n, label_r, r)
    return out


def replace_names(text, mapping):
    # longest names first, so "[name removed]" is replaced before a shorter form could cut into it
    for name in sorted(mapping, key=len, reverse=True):
        for pat in name_patterns(name):
            text = pat.sub(mapping[name], text)
    return text


def anonymise_feed(feed, extra_residents=()):
    residents, prospects = feed_names(feed)
    mapping = placeholders(residents, prospects, sorted(extra_residents))
    return json.loads(replace_names(json.dumps(feed), mapping)), mapping


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("src", nargs="?")
    ap.add_argument("dst", nargs="?")
    ap.add_argument("--figures", action="append", default=[])
    ap.add_argument("--names-file", action="append", default=[], help="JSON list of extra resident names")
    ap.add_argument("--text", help="anonymise this text file in place (names come from --names-file and --figures)")
    a = ap.parse_args()
    extra = []
    for path in a.figures:
        extra += json.load(open(path)).get("residents", [])
    for path in a.names_file:
        extra += json.load(open(path))
    if a.text:
        mapping = placeholders([], [], sorted(extra), label_r="Person")
        text = open(a.text, encoding="utf-8").read()
        open(a.text, "w", encoding="utf-8").write(replace_names(text, mapping))
        print(f"{a.text}: {len(mapping)} names checked")
    else:
        feed = json.load(open(a.src))
        out, mapping = anonymise_feed(feed, extra)
        json.dump(out, open(a.dst, "w"), indent=1)
        print(f"{a.dst}: {len(mapping)} names replaced")
