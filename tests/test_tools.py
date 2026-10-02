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
        row = {"num": "101", "rent": 3000, "earliest": "2027-05-01", "noticeBy": "2027-01-31"}
        self.new["properties"][1]["increases"] = [row]
        self.assertEqual(self.fails(), [])
        for bad, why in ((dict(row, noticeBy="2027-02-01"), "minus 90 days"), (dict(row, newRent=3100), "wrong fields"),
                         (dict(row, noticeBy="2027-12-01", earliest="2028-03-01"), "more than 6 months"), ({"num": "101"}, "wrong fields")):
            self.new["properties"][1]["increases"] = [bad]
            self.assertTrue(any(why in f for f in self.fails()), why)
        self.new["properties"][1]["increases"] = [dict(row, num="2"), dict(row, num="1"), dict(row, noticeBy="2027-01-30", earliest="2027-04-30")]
        self.assertTrue(any("not sorted" in f for f in self.fails()))

    def test_no_resident_names_in_notes(self):
        names = {"f47": ["Fakename, Ada", "Testname, Bo"], "grove": ["Fakename, Cy Marie"]}
        self.assertEqual(check_feed.check(self.new, self.old, names), [])
        self.new["properties"][1]["renewals"]["note"] = "Ada Fakename (302) has already renewed."
        f = check_feed.check(self.new, self.old, names)
        self.assertTrue(any(x.startswith("12.") and "Fakename" in x for x in f))
        self.new = copy.deepcopy(self.old)
        self.new["properties"][1]["workOrders"][0]["notes"] = [["2026-10-01", "Called Bo Testname about the access."]]
        self.assertTrue(any(x.startswith("12.") for x in check_feed.check(self.new, self.old, names)))
        self.new = copy.deepcopy(self.old)
        self.new["properties"][0]["rent"]["note"] = "Lease for Fakename, Cy Marie signed."
        self.assertTrue(any(x.startswith("12.") for x in check_feed.check(self.new, self.old, names)))
        # names in the arrears table and prospects are allowed; a plan called Hill or a first name alone is not a name
        self.new = copy.deepcopy(self.old)
        self.new["properties"][0]["rent"]["note"] = "The Hill plan; Ada is the property manager."
        self.assertEqual(check_feed.check(self.new, self.old, names), [])

    def test_renewed_suite_must_not_be_on_the_increases_list(self):
        row = {"num": "302", "rent": 4295, "earliest": "2027-05-01", "noticeBy": "2027-01-31"}
        self.new["properties"][1]["increases"] = [row]
        self.assertEqual(check_feed.check(self.new, self.old, None, {"f47": []}), [])
        f = check_feed.check(self.new, self.old, None, {"f47": ["302"]})
        self.assertTrue(any(x.startswith("13.") and "302" in x for x in f))

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


@unittest.skipUnless(os.path.exists(FEED), "feed not present")
class NewFields(unittest.TestCase):
    def setUp(self):
        self.old = json.load(open(FEED))
        self.new = copy.deepcopy(self.old)

    def test_committed_feed_has_mtm_and_passes(self):
        self.assertTrue(all(isinstance(p["renewals"].get("mtm"), int) for p in self.new["properties"]))
        self.assertEqual(check_feed.check(self.new, self.old), [])

    def test_mtm_is_required_and_a_count(self):
        for bad in (None, -1, 1.5, "0", True):
            self.new["properties"][0]["renewals"]["mtm"] = bad
            self.assertTrue(any(f.startswith("14.") for f in check_feed.check(self.new, self.old)), bad)
        del self.new["properties"][0]["renewals"]["mtm"]
        self.assertTrue(any(f.startswith("14.") for f in check_feed.check(self.new, self.old)))
        self.new["properties"][0]["renewals"]["mtm"] = 2
        self.assertEqual(check_feed.check(self.new, self.old), [])

    def test_leads_week_must_equal_the_stored_daily_counts(self):
        p = self.new["properties"][0]
        h = p["history"]
        self.assertEqual(h[-1]["date"], "2026-10-01")  # a Thursday: the week starts today
        h[-1]["newCards"] = 3
        p["leadsWeek"] = 3
        self.assertEqual(check_feed.check(self.new, self.old), [])
        p["leadsWeek"] = 4  # not the sum of the counts
        self.assertTrue(any(f.startswith("15.") and "add to 3" in f for f in check_feed.check(self.new, self.old)))
        del p["leadsWeek"]  # counts exist but the feed does not use them
        self.assertTrue(any(f.startswith("15.") and "missing" in f for f in check_feed.check(self.new, self.old)))

    def test_leads_week_sums_thursday_to_dataThrough_only(self):
        p = self.new["properties"][0]
        h = p["history"]
        h[-2]["newCards"] = 9  # 2026-09-30, a Wednesday: last week's
        self.old["properties"][0]["history"][-2]["newCards"] = 9  # already stored yesterday; earlier days never change
        h[-1]["newCards"] = 2
        p["leadsWeek"] = 2
        self.assertEqual(check_feed.check(self.new, self.old), [])
        p["leadsWeek"] = 11
        self.assertTrue(any(f.startswith("15.") for f in check_feed.check(self.new, self.old)))

    def test_daily_counts_are_counts_only(self):
        p = self.new["properties"][0]
        for bad in (-1, 1.5, "Fake Name", ["Fake Name"], True):
            p["history"][-1]["newCards"] = bad
            self.assertTrue(any(f.startswith("15.") and "no names" in f for f in check_feed.check(self.new, self.old)), bad)

    def test_leads_week_zero_is_valid_when_counted(self):
        p = self.new["properties"][0]
        p["history"][-1]["newCards"] = 0
        p["leadsWeek"] = 0
        self.assertEqual(check_feed.check(self.new, self.old), [])
        for bad in (-1, 2.5, None, "3"):
            p["leadsWeek"] = bad
            self.assertTrue(any(f.startswith("15.") for f in check_feed.check(self.new, self.old)), bad)

    def test_funnel_since_when_present(self):
        p = self.new["properties"][0]
        p["funnel"]["since"] = "2026-08-01"
        self.assertEqual(check_feed.check(self.new, self.old), [])
        for bad in ("08/01/2026", "2026-13", "2026-10-09", 20260801):  # the last is after dataThrough
            p["funnel"]["since"] = bad
            self.assertTrue(any(f.startswith("16.") for f in check_feed.check(self.new, self.old)), bad)

    def test_items_income_when_present(self):
        p = self.new["properties"][1]
        p["items"]["income"] = 1200
        self.assertEqual(check_feed.check(self.new, self.old), [])
        p["items"]["income"] = 0
        self.assertEqual(check_feed.check(self.new, self.old), [])
        for bad in (-5, None, "1200", True):
            p["items"]["income"] = bad
            self.assertTrue(any(f.startswith("17.") for f in check_feed.check(self.new, self.old)), bad)

    def test_missing_optional_fields_are_noted_not_failed(self):
        notes = check_feed.gaps(self.new)
        self.assertTrue(any("leadsWeek" in n for n in notes))
        self.assertTrue(any("funnel.since" in n for n in notes))
        self.assertFalse(any("items.income" in n for n in notes))  # on hold: not even noted
        self.new["properties"][0]["history"][-1]["newCards"] = 1
        self.new["properties"][0]["leadsWeek"] = 1
        self.assertFalse(any("grove: leadsWeek" in n for n in check_feed.gaps(self.new)))


class SyncPage(unittest.TestCase):
    PAGE = ('<html><script>/* x */\nwindow.CLIENT_FEED = {"properties": [{"arrears": {"detail": [["1", "Fake, Name"]]}}], "a": "}"};\n'
            '</script><script>var F = window.CLIENT_FEED; /* page code */</script></html>')

    def test_built_in_figures_are_removed(self):
        from tools import sync_page
        out = sync_page.strip_builtin_feed(self.PAGE)
        self.assertNotIn("Fake, Name", out)
        self.assertEqual(sync_page.feed_left_in(out), [])
        self.assertIn("window.CLIENT_FEED = null;", out)
        self.assertIn("var F = window.CLIENT_FEED; /* page code */", out)  # the page's own code is untouched
        self.assertEqual(sync_page.feed_left_in(self.PAGE), ['"properties":', '"arrears":'])

    def test_repo_page_carries_no_figures(self):
        from tools import sync_page
        path = os.path.join(ROOT, "index.html")
        if not os.path.exists(path):
            self.skipTest("page not present")
        html = open(path, encoding="utf-8").read()
        self.assertEqual(sync_page.feed_left_in(html), [], "index.html still holds the built-in figures (resident names)")
        self.assertIn("keilty-template", html)

    def test_render_swap_works_on_the_placeholder_and_on_a_real_object(self):
        from tools import render_check, sync_page
        stripped = sync_page.strip_builtin_feed(self.PAGE)
        out = render_check.swap_builtin_feed(stripped, {"z": 1})
        self.assertIn('window.CLIENT_FEED = {"z": 1};', out)
        self.assertIn("var F = window.CLIENT_FEED;", out)
        full = render_check.swap_builtin_feed(self.PAGE, {"z": 1})  # a page that still has the real object
        self.assertIn('window.CLIENT_FEED = {"z": 1};', full)
        self.assertNotIn("Fake, Name", full)


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


class NamesOutOfGit(unittest.TestCase):
    FEED = {"properties": [
        {"id": "a", "arrears": {"detail": [["101", "Ada Fakename", "Current resident", 0, 0, 0, 0, 0, ""], ["Parking", "Bo Testname", "x", 0, 0, 0, 0, 0, ""]],
                                "note": "Ada Fakename owes nothing."},
         "prospects": [{"name": "Cy Placeholder", "entries": [["2026-10-01 10:00", "Tour", "Toured with Cy Placeholder."]]}],
         "renewals": {"note": "Suite 302 has renewed."}},
        {"id": "b", "arrears": {"detail": []}, "prospects": [{"name": "Dee Invented", "entries": []}]}]}

    def test_names_become_placeholders_and_the_shape_stays(self):
        from tools import anonymise_feed
        out, mapping = anonymise_feed.anonymise_feed(self.FEED, ["Fakename, Ada", "Extra, Eve"])
        a, b = out["properties"]
        self.assertEqual([r[1] for r in a["arrears"]["detail"]], ["Resident 1", "Resident 2"])
        self.assertEqual(a["arrears"]["note"], "Resident 1 owes nothing.")
        self.assertEqual([p["name"] for p in a["prospects"]], ["Prospect 1"])
        self.assertEqual(a["prospects"][0]["entries"][0][2], "Toured with Prospect 1.")
        self.assertEqual(b["prospects"][0]["name"], "Prospect 2")
        self.assertEqual(a["renewals"], {"note": "Suite 302 has renewed."})  # nothing else changes
        self.assertEqual(set(mapping.values()), {"Resident 1", "Resident 2", "Resident 3", "Prospect 1", "Prospect 2"})
        self.assertEqual(json.loads(json.dumps(out)).keys(), self.FEED.keys())

    def test_the_same_person_in_two_forms_gets_one_placeholder(self):
        from tools import anonymise_feed
        m = anonymise_feed.placeholders(["Ada Fakename"], [], ["Fakename, Ada Marie", "Extra, Eve"])
        self.assertEqual(m["Ada Fakename"], m["Fakename, Ada Marie"])
        self.assertEqual(m["Extra, Eve"], "Resident 2")
        text = anonymise_feed.replace_names("Fakename, Ada Marie and Ada Fakename and Eve Extra.", m)
        self.assertEqual(text, "Resident 1 and Resident 1 and Resident 2.")

    def test_the_check_finds_a_name_in_any_file_and_passes_once_removed(self):
        import tempfile
        from tools import anonymise_feed, check_repo_names
        d = tempfile.mkdtemp()
        path = os.path.join(d, "feed.json")
        json.dump(self.FEED, open(path, "w"))
        names = check_repo_names.collect_names(names_files=[])
        json.dump(["Fakename, Ada", "Testname, Bo", "Placeholder, Cy"], open(os.path.join(d, "n.json"), "w"))
        names = check_repo_names.collect_names(names_files=[os.path.join(d, "n.json")])
        bad = check_repo_names.check_paths([path], names)
        self.assertEqual([p for p, _ in bad], [path])
        out, _ = anonymise_feed.anonymise_feed(self.FEED, ["Fakename, Ada"])
        json.dump(out, open(path, "w"))
        self.assertEqual(check_repo_names.check_paths([path], names), [])
        # a last name or a first name on its own is not a hit
        open(path, "w").write("The Hill plan. Ada is the manager. Fakename Road.")
        self.assertEqual(check_repo_names.check_paths([path], names), [])
        # the names can also come from an un-anonymised feed
        json.dump(self.FEED, open(os.path.join(d, "raw.json"), "w"))
        from_feed = check_repo_names.collect_names(feed=os.path.join(d, "raw.json"))
        self.assertIn("Cy Placeholder", from_feed)

    def test_history_lists_commits_that_held_a_name(self):
        import subprocess
        import tempfile
        from tools import check_repo_names
        d = tempfile.mkdtemp()
        run = lambda *a: subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t"] + list(a), cwd=d, check=True, capture_output=True)
        run("init", "-q")
        open(os.path.join(d, "a.txt"), "w").write("Ada Fakename owes rent\\n")
        run("add", "."); run("commit", "-q", "-m", "first")
        open(os.path.join(d, "a.txt"), "w").write("Resident 1 owes rent\\n")
        run("commit", "-q", "-am", "second")
        here = os.getcwd()
        os.chdir(d)
        try:
            found = check_repo_names.history(["Fakename, Ada"])
        finally:
            os.chdir(here)
        self.assertEqual([(s, f) for _, _, s, f in found], [("first", ["a.txt"])])  # only the commit that held it

    def test_the_committed_files_hold_no_names(self):
        """Skipped unless a names list is supplied: NAMES_FILE=names.json python -m unittest ..."""
        path = os.environ.get("NAMES_FILE")
        if not path or not os.path.exists(path):
            self.skipTest("no NAMES_FILE")
        from tools import check_repo_names
        names = check_repo_names.collect_names(names_files=[path])
        self.assertEqual(check_repo_names.check_paths(check_repo_names.tracked_files(), names), [])
