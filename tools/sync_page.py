"""Copy the live dashboard page into this repository without the figures it carries.

    python tools/sync_page.py <saved index.html> [--out index.html]

Read the live page with the Artifact tool (action read, path index.html); it saves the file and prints the path.
The page holds a built-in copy of the figures (`window.CLIENT_FEED = {...}`), which includes arrears and prospect
names. That copy is replaced with `null` before anything is written, so no resident name reaches git.
tools/render_check.py supplies a feed when it renders the page. The routine never publishes the page.
"""
import argparse
import json
import re
import sys

KEY = "window.CLIENT_FEED = "
PLACEHOLDER = "null; /* the live page carries a built-in copy of the figures here; it is removed in this repository because it holds resident names */"
# anything that only the feed (and not the page's own code) contains
FEED_MARKERS = ('"properties":', '"prospects":', '"arrears":', '"workOrders":', '"weeklyChecklist":')


def strip_builtin_feed(html):
    i = html.index(KEY)
    _, end = json.JSONDecoder().raw_decode(html[i + len(KEY):])
    out = html[:i + len(KEY)] + PLACEHOLDER + html[i + len(KEY) + end:]
    # drop the semicolon that followed the object, now doubled
    out = out.replace(PLACEHOLDER + ";", PLACEHOLDER, 1)
    return out


def feed_left_in(html):
    """Names of feed markers still in the text. Empty means the built-in figures are gone."""
    return [m for m in FEED_MARKERS if m in html]


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("page")
    ap.add_argument("--out", default="index.html")
    a = ap.parse_args()
    html = strip_builtin_feed(open(a.page, encoding="utf-8").read())
    left = feed_left_in(html)
    if left:
        print("REFUSED: figures still in the page after stripping:", left)
        sys.exit(1)
    open(a.out, "w", encoding="utf-8").write(html)
    print(f"wrote {a.out} ({len(html)} bytes), built-in figures removed")
