import copy
import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools import check_feed, command_center  # noqa: E402

FEED = os.path.join(ROOT, "feeds", "2026-10-02.json")


@unittest.skipUnless(os.path.exists(FEED), "feed not present")
class FeedChecks(unittest.TestCase):
    def setUp(self):
        self.old = json.load(open(FEED))
        self.new = copy.deepcopy(self.old)

    def fails(self):
        return check_feed.check(self.new, self.old)

    def test_the_committed_feed_passes(self):
        self.assertEqual(self.fails(), [])

    def test_stack_and_counts_must_agree(self):
        self.new["properties"][0]["counts"]["available"] += 1
        self.assertTrue(any(f.startswith("2.") for f in self.fails()))
        self.new["properties"][0]["stack"].pop()
        self.assertTrue(any("stack has 81" in f for f in self.fails()))

    def test_owing_must_equal_overdue_of_current_residents(self):
        a = self.new["properties"][1]["arrears"]
        a["detail"].append(["999", "Test", "Current resident", 0, 10, 0, 0, 10, ""])
        self.assertTrue(any(f.startswith("3.") for f in self.fails()))

    def test_credits_never_shown(self):
        self.new["properties"][1]["arrears"]["detail"].append(["999", "Test", "Former resident", 0, 0, 0, -5, -5, ""])
        self.assertTrue(any("credit or prepayment" in f for f in self.fails()))

    def test_concessions_total(self):
        self.new["properties"][0]["concessions"]["total"] += 1
        self.assertTrue(any(f.startswith("4.") for f in self.fails()))

    def test_history_date_and_frozen_fields(self):
        self.new["dataThrough"] = "2026-10-05"
        self.assertTrue(any(f.startswith("5.") for f in self.fails()))
        self.new = copy.deepcopy(self.old)
        self.new["properties"][0]["weeks"][0]["x"] = 1
        self.assertTrue(any("weeks changed" in f for f in self.fails()))
        self.new = copy.deepcopy(self.old)
        self.new["properties"][0]["history"][0]["leads"] += 1
        self.assertTrue(any("earlier history snapshot" in f for f in self.fails()))

    def test_budget_must_stop_at_a_closed_month(self):
        self.new["properties"][0]["budget"]["noiMonths"].append("2026-10")  # partial current month
        self.new["properties"][0]["budget"]["noiTrend"].append(0)
        self.assertTrue(any(f.startswith("8.") for f in self.fails()))
        self.new = copy.deepcopy(self.old)
        self.new["properties"][1]["budget"]["period"] = "Aug 2026"
        self.assertTrue(any("does not match" in f for f in self.fails()))

    def test_increases_must_be_a_list_with_the_agreed_fields(self):
        del self.new["properties"][0]["increases"]
        self.assertTrue(any(f.startswith("9.") and "must be present" in f for f in self.fails()))
        self.new = copy.deepcopy(self.old)
        row = {"num": "101", "rent": 3000, "newRent": None, "earliest": "2027-05-01", "noticeBy": "2027-01-31"}
        self.new["properties"][1]["increases"] = [row]
        self.assertEqual(self.fails(), [])
        for bad, why in ((dict(row, noticeBy="2027-02-01"), "minus 90 days"), (dict(row, newRent=3100), "newRent must stay null"),
                         (dict(row, noticeBy="2027-12-01", earliest="2028-03-01"), "more than 6 months"), ({"num": "101"}, "wrong fields")):
            self.new["properties"][1]["increases"] = [bad]
            self.assertTrue(any(why in f for f in self.fails()), why)
        self.new["properties"][1]["increases"] = [dict(row, num="2"), dict(row, num="1", noticeBy="2027-01-31"), dict(row, noticeBy="2027-01-30", earliest="2027-04-30")]
        self.assertTrue(any("not sorted" in f for f in self.fails()))

    def test_by_end_stays_inside_12_months(self):
        self.new["properties"][1]["renewals"]["byEnd"].append(["2027-12-28", 1])
        self.assertTrue(any(f.startswith("10.") and "outside" in f for f in self.fails()))
        self.new = copy.deepcopy(self.old)
        self.new["properties"][1]["renewals"]["byEnd"] = [["soon", 1]]
        self.assertTrue(any(f.startswith("10.") for f in self.fails()))

    def test_no_legal_words_in_arrears(self):
        d = self.new["properties"][1]["arrears"]["detail"]
        for text in ("Former resident, eviction file, with collections", "Former resident, with collections, LTB hearing set",
                     "2026-03-03: N4 served", "File no. 12345", "TNL-123456 filed"):
            d[-1][2] = text
            self.assertTrue(any(f.startswith("11.") for f in self.fails()), text)
        d[-1][2] = "Former resident, with collections"
        d[-1][8] = "2026-03-03: filed to collections, per accounting."
        self.assertEqual(self.fails(), [])
        d[-1][2] = "Former resident"
        d[-1][8] = "sent to collections"
        self.assertTrue(any("must read 'Former resident, with collections'" in f for f in self.fails()))

    def test_banned_words_and_nan(self):
        self.new["properties"][0]["arrears"]["note"] = "Per the Rent Roll, nothing is owed."
        self.assertTrue(any(f.startswith("7.") for f in self.fails()))
        self.new = copy.deepcopy(self.old)
        self.new["properties"][0]["rent"]["signed"] = "NaN"
        self.assertTrue(any(f.startswith("1.") for f in self.fails()))


class RenderCheck(unittest.TestCase):
    def test_swap_replaces_the_built_in_feed_only(self):
        from tools import render_check
        html = "<script>/* x */\nwindow.CLIENT_FEED = {\"a\": [1, {\"b\": \"}\"}], \"c\": 2};\n</script><p>after</p>"
        out = render_check.swap_builtin_feed(html, {"z": 1})
        self.assertEqual(out, "<script>/* x */\nwindow.CLIENT_FEED = {\"z\": 1};\n</script><p>after</p>")

    @unittest.skipUnless(os.path.exists(os.path.join(ROOT, "index.html")) and os.path.exists(FEED), "page or feed not present")
    def test_the_synced_page_renders_the_committed_feed(self):
        try:
            import playwright  # noqa: F401
            from tools import render_check
        except ImportError:
            self.skipTest("playwright not installed")
        if not render_check.chrome():
            self.skipTest("no browser")
        self.assertEqual(render_check.check(FEED, os.path.join(ROOT, "index.html")), [])


class CommandCenter(unittest.TestCase):
    def test_open_items_tours_and_client_view(self):
        base = [
            {"id": "i1", "clientId": "cCEN", "owner": "Client", "area": "Marketing", "type": "action", "status": "open", "title": "Feedback", "raised": "2026-08-26"},
            {"id": "i2", "clientId": "cCEN", "owner": "KEILTY", "area": "Maintenance", "status": "progress", "title": "Order a bed", "raised": "2026-09-30"},
            {"id": "i3", "clientId": "cF47", "owner": "KEILTY", "status": "closed", "title": "Done"},
            {"id": "p9", "clientId": "cCEN", "owner": "KEILTY", "status": "open", "title": "A prospect"},
            {"id": "i4", "clientId": "cCEN", "owner": "KEILTY", "status": "open", "kind": "Work order", "title": "Fix door"},
            {"id": "i5", "clientId": "cCEN", "owner": "KEILTY", "status": "open", "title": "WO 123"},
            {"id": "i6", "clientId": "cCEN", "owner": "KEILTY", "status": "open", "type": "fyi", "area": "Leasing", "title": "Note"},
            {"id": "i7", "clientId": "cF47", "owner": "Client", "status": "open", "title": "Hidden", "clientView": False},
            {"id": "i8", "clientId": "cF47", "owner": "Client", "status": "open", "title": "Shown, null", "clientView": None},
            {"id": "i9", "clientId": "cF47", "owner": "Client", "status": "open", "title": "Merged", "mergedInto": "i8"},
        ]
        new = [{"id": "t1", "clientId": "cCEN", "owner": "KEILTY", "status": "open", "kind": "Tour", "title": "Pat Test, tour booked", "tour": "2026-10-07", "tourTime": "10:00", "tourTent": True},
               {"id": "t2", "clientId": "cCEN", "owner": "KEILTY", "status": "open", "kind": "Tour", "who": "Old Tour", "tour": "2026-09-01", "tourTime": ""}]
        edits = {"i1": {"notes": "2026-09-30: still waiting."}, "i2": {"status": "closed"}}
        d = tempfile.mkdtemp()
        page = os.path.join(d, "p.html")
        open(page, "w").write("<script>var D={\"items\": " + json.dumps(base) + ", \"x\":1}</script>")
        json.dump({"body": json.dumps(new)}, open(os.path.join(d, "n.json"), "w"))
        json.dump({"body": edits}, open(os.path.join(d, "e.json"), "w"))
        out = command_center.build(command_center.load_items(page, os.path.join(d, "n.json"), os.path.join(d, "e.json")), "2026-10-02")
        g, f = out["grove"], out["f47"]
        self.assertEqual([r["id"] for r in g["waiting"]], ["i1"])
        self.assertEqual(g["waiting"][0]["notes"], "2026-09-30: still waiting.")
        self.assertEqual(g["working"], [])  # i2 was closed by an edit; work orders, prospects and fyi are dropped
        self.assertEqual([r["id"] for r in f["waiting"]], ["i8"])  # false hides, null shows, merged is not open
        self.assertEqual(g["toursBooked"], [{"name": "Pat Test", "tour": "2026-10-07 10:00", "tent": True, "id": "t1"}])
        self.assertEqual(f["toursBooked"], [])


if __name__ == "__main__":
    unittest.main()
