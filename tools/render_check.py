"""Render the dashboard with a feed in headless Chromium and fail on NaN, undefined or script errors.

    python tools/render_check.py feeds/2026-10-02.json [--page index.html]
    python tools/render_check.py --site work/YYYY-MM-DD/site     (the exact files to deploy; see check_site)

index.html is the live page, synced from the artifact (never published from the routine). The page keeps a
built-in copy of the feed and, when it runs inside Claude, replaces it with the database document dash/feed.
index.html here has the built-in copy of the figures removed (tools/sync_page.py), because it held resident names.
Two passes:
  1. the feed is swapped in for the built-in copy (what the page draws first);
  2. a copy of the feed marked "fallback" is put in as the built-in copy, and a stub of the database hands the page
     the real feed as JSON text in field "json" (the live path: the page parses it and redraws). The check fails
     if the page still shows the fallback (its property names carry a marker).
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
    _, end = json.JSONDecoder().raw_decode(html[i + len(key):])  # an object, or null in this repository's copy
    rest = html[i + len(key) + end:]
    if rest.startswith(";"):
        rest = rest[1:]
    else:  # null followed by a placeholder comment up to the semicolon
        j = rest.find(";")
        rest = rest[j + 1:] if j != -1 and "\n" not in rest[:j] else rest
    return html[:i + len(key)] + json.dumps(feed) + ";" + rest


def db_stub(feed):
    payload = json.dumps({"json": json.dumps(feed), "asAt": feed["asAt"], "dataThrough": feed["dataThrough"], "generated": feed["generated"]})
    return ("window.claude={use:function(n){return Promise.resolve({doc:function(){return {get:function(){return Promise.resolve({data:function(){return "
            + payload + ";}});}};}});}};")


def run_pass(browser, label, html, feed, stub, tmp, base=None):
    """base: the address tmp is served at (site mode, so the page can fetch feed.json); None opens the file."""
    live = stub or base is not None
    path = os.path.join(tmp, f"{label}.html")
    open(path, "w", encoding="utf-8").write(html)
    problems = []
    for v in ["overview"] + [p["id"] for p in feed["properties"]]:
        pg = browser.new_page(viewport={"width": 1280, "height": 900})
        errs = []
        pg.on("pageerror", lambda e, errs=errs: errs.append(str(e)))
        if stub:
            pg.add_init_script(db_stub(feed))
        pg.goto(f"{base}/{label}.html#{v}" if base else f"file://{path}#{v}")
        pg.wait_for_timeout(1500 if live else 400)
        text = pg.inner_text("body")
        if len(text) < 200:
            problems.append(f"{label}/{v}: page is nearly empty ({len(text)} characters)")
        if live and v != "overview":
            name = next(p["name"] for p in feed["properties"] if p["id"] == v)
            if name not in text:
                problems.append(f"{label}/{v}: property name {name!r} not on the page")
        if live and "FALLBACKCOPY" in text:
            problems.append(f"{label}/{v}: the page still shows the fallback copy, so the {'database' if stub else 'feed.json'} path did not redraw it")
        for bad in BAD:
            if bad in text:
                i = text.index(bad)
                problems.append(f"{label}/{v}: found {bad!r} near {text[max(0, i - 40):i + 40]!r}")
        problems += [f"{label}/{v}: script error: {e}" for e in errs]
        pg.close()
    return problems


def fallback_copy(feed):
    return dict(feed, generated="FALLBACK-COPY", properties=[dict(p, name=p["name"] + " FALLBACKCOPY") for p in feed["properties"]])


def builtin_feed(html):
    """The object the page carries as window.CLIENT_FEED (None in this repository's copy)."""
    key = "window.CLIENT_FEED = "
    i = html.index(key)
    return json.JSONDecoder().raw_decode(html[i + len(key):])[0]


def site_feed(o):
    return json.loads(o["json"]) if isinstance(o.get("json"), str) else o


def check_site(site):
    """Check the exact files to deploy (tools/build_site.py output), served over http as Pages would.
    Passes: 'site' opens the deployed index.html as it is, with its feed.json beside it; 'sitefeed' opens a copy
    of that page whose built-in figures are marked as a fallback, with the same feed.json, and fails unless the
    page redraws from feed.json. Also fails if the page's built-in figures are not the feed in feed.json."""
    import functools
    import http.server
    import threading
    from playwright.sync_api import sync_playwright
    html = open(os.path.join(site, "index.html"), encoding="utf-8").read()
    feed_raw = open(os.path.join(site, "feed.json"), encoding="utf-8").read()
    feed = site_feed(json.loads(feed_raw))
    problems = []
    built = builtin_feed(html)
    if built != feed:
        problems.append("site: the built-in figures in index.html are not the feed in feed.json" if built else "site: index.html has no built-in figures")
    tmp = tempfile.mkdtemp()
    open(os.path.join(tmp, "feed.json"), "w", encoding="utf-8").write(feed_raw)
    handler = functools.partial(type("Quiet", (http.server.SimpleHTTPRequestHandler,), {"log_message": lambda *a: None}), directory=tmp)
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_address[1]}"
    try:
        with sync_playwright() as pw:
            b = pw.chromium.launch(executable_path=chrome(), args=["--no-sandbox"])
            problems += run_pass(b, "site", html, feed, False, tmp, base)
            problems += run_pass(b, "sitefeed", swap_builtin_feed(html, fallback_copy(feed)), feed, False, tmp, base)
            b.close()
    finally:
        srv.shutdown()
        shutil.rmtree(tmp)
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
            problems += run_pass(b, "database", swap_builtin_feed(html, fallback_copy(feed)), feed, True, tmp)
            b.close()
    finally:
        shutil.rmtree(tmp)
    return problems


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("feed", nargs="?")
    ap.add_argument("--page", default="index.html")
    ap.add_argument("--site", help="a folder from tools/build_site.py: check those exact files instead")
    a = ap.parse_args()
    if not a.site and not a.feed:
        ap.error("give a feed, or --site")
    probs = check_site(a.site) if a.site else check(a.feed, a.page)
    for p in probs:
        print("FAIL", p)
    print("render check:", "FAILED" if probs else "passed")
    sys.exit(1 if probs else 0)
