"""Build the files to deploy to Cloudflare Pages: the page with today's figures built in, and feed.json beside it.

    python tools/build_site.py <feed.json> <out dir> [--page index.html]

<feed.json> is the plain feed object or the {asAt, dataThrough, generated, json} wrapper (the form saved to R2
and to dash/feed). The out dir gets:
  index.html  this repository's page (template, built-in figures removed) with the feed written in as
              window.CLIENT_FEED, so the live page never opens blank
  feed.json   the wrapper form, read by the page first (template 2026-10-02.14 on)
  _headers    feed.json is never cached; nothing is indexed
The out dir holds resident names: keep it under work/ (git-ignored). Run tools/render_check.py --site on it
before deploying.
"""
import argparse
import json
import os
import sys

from tools.render_check import swap_builtin_feed

HEADERS = """/*
  X-Robots-Tag: noindex
/feed.json
  Cache-Control: no-store
"""


def plain(o):
    """The feed object from either form."""
    return json.loads(o["json"]) if isinstance(o.get("json"), str) else o


def wrapper(feed):
    return {"asAt": feed["asAt"], "dataThrough": feed["dataThrough"], "generated": feed["generated"], "json": json.dumps(feed, ensure_ascii=False)}


def build(feed_obj, out, page="index.html"):
    feed = plain(feed_obj)
    html = open(page, encoding="utf-8").read()
    os.makedirs(out, exist_ok=True)
    open(os.path.join(out, "index.html"), "w", encoding="utf-8").write(swap_builtin_feed(html, feed))
    json.dump(wrapper(feed), open(os.path.join(out, "feed.json"), "w", encoding="utf-8"), ensure_ascii=False)
    open(os.path.join(out, "_headers"), "w", encoding="utf-8").write(HEADERS)
    return feed


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("feed")
    ap.add_argument("out")
    ap.add_argument("--page", default="index.html")
    a = ap.parse_args()
    if os.path.abspath(a.out).startswith(os.path.abspath(".") + os.sep) and not os.path.abspath(a.out).startswith(os.path.abspath("work") + os.sep):
        print("REFUSED: the site holds resident names; build it under work/")
        sys.exit(1)
    f = build(json.load(open(a.feed, encoding="utf-8")), a.out, a.page)
    print(f"wrote {a.out}: index.html, feed.json, _headers (asAt {f['asAt']}, dataThrough {f['dataThrough']}, generated {f['generated']})")
