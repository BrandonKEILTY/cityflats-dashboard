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

    def test_banned_words_and_nan(self):
        self.new["properties"][0]["arrears"]["note"] = "Per the Rent Roll, nothing is owed."
        self.assertTrue(any(f.startswith("7.") for f in self.fails()))
        self.new = copy.deepcopy(self.old)
        self.new["properties"][0]["rent"]["signed"] = "NaN"
        self.assertTrue(any(f.startswith("1.") for f in self.fails()))


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
