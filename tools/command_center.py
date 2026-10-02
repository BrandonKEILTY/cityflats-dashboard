"""Command Center items for the dashboard (read only): open client items, KEILTY items and booked tours.

    python tools/command_center.py <page.html> <newitems.json> <edits.json> --today YYYY-MM-DD

page.html is the saved Command Center page (it holds the base list after the key "items":), newitems.json and
edits.json are the saved board/newitems and board/edits documents. Wording is not changed here: the run
rewrites titles and notes for the owner under the writing rules.
"""
import argparse
import json
import re

CLIENTS = {"cCEN": "grove", "cF47": "f47"}


def load_items(page_html, newitems, edits):
    h = open(page_html, encoding="utf-8").read()
    i = h.index('"items":')
    base, _ = json.JSONDecoder().raw_decode(h[h.index("[", i):])
    items = {x["id"]: dict(x) for x in base}
    new = json.load(open(newitems))["body"]
    new = json.loads(new) if isinstance(new, str) else new
    for x in new:
        items[x["id"]] = dict(x)
    ed = json.load(open(edits))["body"]
    ed = json.loads(ed) if isinstance(ed, str) else ed
    for k, v in ed.items():
        if k in items:
            items[k].update(v)
    return list(items.values())


def is_open(x):
    return x.get("status") in ("open", "progress") and not x.get("mergedInto")


def client_visible(x):
    """Only an explicit false hides an item from the client."""
    return x.get("clientView") is not False


def is_record_not_decision(x):
    """Tours, prospects, work orders and Leasing fyi items are reported by Entrata or elsewhere."""
    return (x.get("kind") == "Tour" or str(x.get("id", "")).startswith("p") or x.get("kind") == "Work order"
            or str(x.get("title", "")).startswith("WO ") or (x.get("type") == "fyi" and x.get("area") == "Leasing"))


def build(items, today):
    out = {pid: {"waiting": [], "working": [], "toursBooked": []} for pid in CLIENTS.values()}
    for x in items:
        pid = CLIENTS.get(x.get("clientId"))
        if not pid or not is_open(x):
            continue
        if x.get("kind") == "Tour" or x.get("tour"):
            if x.get("tour") and x["tour"] >= today:
                name = x.get("who") or re.split(r",\s*tour booked", x.get("title", ""), flags=re.I)[0]
                out[pid]["toursBooked"].append({"name": name, "tour": (x["tour"] + (" " + x["tourTime"] if x.get("tourTime") else "")).strip(),
                                                "tent": bool(x.get("tourTent")), "id": x["id"]})
        if is_record_not_decision(x) or not client_visible(x):
            continue
        row = {"id": x["id"], "area": x.get("area"), "title": x.get("title"), "since": x.get("raised"), "notes": x.get("notes") or "",
               "clientNote": x.get("clientNote")}
        (out[pid]["waiting"] if x.get("owner") == "Client" else out[pid]["working"]).append(row)
    for pid in out:
        out[pid]["toursBooked"].sort(key=lambda t: t["tour"])
        out[pid]["waiting"].sort(key=lambda r: r["since"] or "")
        out[pid]["working"].sort(key=lambda r: r["since"] or "")
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("page")
    ap.add_argument("newitems")
    ap.add_argument("edits")
    ap.add_argument("--today", required=True)
    a = ap.parse_args()
    print(json.dumps(build(load_items(a.page, a.newitems, a.edits), a.today), indent=1))
