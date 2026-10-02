"""Render the dashboard with a feed in headless Chromium and fail on NaN, undefined or script errors.

    python tools/render_check.py feeds/2026-10-02.json [--page index.html]

index.html is the live page, synced from the artifact (never published from the routine). The page keeps a
built-in copy of the feed and, when it runs inside Claude, replaces it with the database document dash/feed.
Two passes:
  1. the feed is swapped in for the built-in copy (what the page draws first);
  2. the built-in copy is left alone and a stub of the database hands the page the feed as JSON text in field
     "json" (the real live path: the page parses it and redraws).
Each pass opens the portfolio overview and every property. This is a safety check before saving; Brandon still
render-checks the published page. Needs: pip install playwright (the browser is already installed).
"""
import argparse
import glob
import json
import os
import shutil
import sys
import tempfile

BAD = ("NaN", "undefined", "[object Object]", "Infinity")


def chrome():
    hits = sorted(glob.glob("/opt/pw-browsers/chromium-*/chrome-linux/chrome"))
    return hits[-1] if hits else None


def swap_builtin_feed(html, feed):
    """Replace the page's built-in `window.CLIENT_FEED = {...};` with the given feed."""
    key = "window.CLIENT_FEED = "
    i = html.index(key)
    _, end = json.JSONDecoder().raw_decode(html[i + len(key):])
    return html[:i + len(key)] + json.dumps(feed) + html[i + len(key) + end:]


def db_stub(feed):
    payload = json.dumps({"json": json.dumps(feed), "asAt": feed["asAt"], "dataThrough": feed["dataThrough"], "generated": feed["generated"]})
    return ("window.claude={use:function(n){return Promise.resolve({doc:function(){return {get:function(){return Promise.resolve({data:function(){return "
            + payload + ";}});}};}});}};")


def run_pass(browser, label, html, feed, stub, tmp):
    path = os.path.join(tmp, f"{label}.html")
    open(path, "w", encoding="utf-8").write(html)
    problems = []
    for v in ["overview"] + [p["id"] for p in feed["properties"]]:
        pg = browser.new_page(viewport={"width": 1280, "height": 900})
        errs = []
        pg.on("pageerror", lambda e, errs=errs: errs.append(str(e)))
        if stub:
            pg.add_init_script(db_stub(feed))
        pg.goto(f"file://{path}#{v}")
        pg.wait_for_timeout(1500 if stub else 400)
        text = pg.inner_text("body")
        if len(text) < 200:
            problems.append(f"{label}/{v}: page is nearly empty ({len(text)} characters)")
        if stub and v != "overview":
            name = next(p["name"] for p in feed["properties"] if p["id"] == v)
            if name not in text:
                problems.append(f"{label}/{v}: property name {name!r} not on the page")
        for bad in BAD:
            if bad in text:
                i = text.index(bad)
                problems.append(f"{label}/{v}: found {bad!r} near {text[max(0, i - 40):i + 40]!r}")
        problems += [f"{label}/{v}: script error: {e}" for e in errs]
        pg.close()
    return problems


def check(feed_path, page="index.html"):
    from playwright.sync_api import sync_playwright
    feed = json.load(open(feed_path))
    html = open(page, encoding="utf-8").read()
    tmp = tempfile.mkdtemp()
    try:
        with sync_playwright() as pw:
            b = pw.chromium.launch(executable_path=chrome(), args=["--no-sandbox"])
            problems = run_pass(b, "builtin", swap_builtin_feed(html, feed), feed, False, tmp)
            problems += run_pass(b, "database", html, feed, True, tmp)
            b.close()
    finally:
        shutil.rmtree(tmp)
    return problems


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("feed")
    ap.add_argument("--page", default="index.html")
    a = ap.parse_args()
    probs = check(a.feed, a.page)
    for p in probs:
        print("FAIL", p)
    print("render check:", "FAILED" if probs else "passed")
    sys.exit(1 if probs else 0)
