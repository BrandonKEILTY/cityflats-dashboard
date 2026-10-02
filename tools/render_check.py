"""Render the dashboard with a feed in headless Chromium and fail on NaN, undefined or script errors.

    python tools/render_check.py feeds/2026-10-02.json [--page index.html]

Uses the page in this repository (index.html reading window.CLIENT_FEED), which may differ from the published
page, so it is a safety check before saving, not a replacement for Brandon's render check of the published page.
Checks the portfolio overview and each property. Needs: pip install playwright (the browser is already installed).
"""
import argparse
import glob
import json
import os
import shutil
import sys
import tempfile


def chrome():
    hits = sorted(glob.glob("/opt/pw-browsers/chromium-*/chrome-linux/chrome"))
    return hits[-1] if hits else None


def check(feed_path, page="index.html"):
    from playwright.sync_api import sync_playwright
    feed = json.load(open(feed_path))
    tmp = tempfile.mkdtemp()
    problems = []
    try:
        shutil.copy(page, os.path.join(tmp, "index.html"))
        logo = os.path.join(os.path.dirname(os.path.abspath(page)), "cityflats-logo.png")
        if os.path.exists(logo):
            shutil.copy(logo, tmp)
        with open(os.path.join(tmp, "data.js"), "w") as f:
            f.write("window.CLIENT_FEED = " + json.dumps(feed) + ";\n")
        views = ["overview"] + [p["id"] for p in feed["properties"]]
        with sync_playwright() as pw:
            b = pw.chromium.launch(executable_path=chrome(), args=["--no-sandbox"])
            for v in views:
                pg = b.new_page(viewport={"width": 1280, "height": 900})
                errs = []
                pg.on("pageerror", lambda e, errs=errs: errs.append(str(e)))
                pg.goto(f"file://{tmp}/index.html#{v}")
                pg.wait_for_timeout(300)
                text = pg.inner_text("body")
                if len(text) < 200:
                    problems.append(f"{v}: page is nearly empty ({len(text)} characters)")
                for bad in ("NaN", "undefined", "[object Object]", "null"):
                    if bad in text:
                        i = text.index(bad)
                        problems.append(f"{v}: found {bad!r} near {text[max(0, i - 40):i + 40]!r}")
                problems += [f"{v}: script error: {e}" for e in errs]
                pg.close()
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
