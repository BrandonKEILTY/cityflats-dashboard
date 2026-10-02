"""Run: python -m unittest discover -s tests -v

Tests for the Excel-text readers. tests/data/xlsx holds made-up workbooks in the real layout (fake names).
The real Cityflats workbooks are in fixtures/xlsx_text (git-ignored; resident names) and are used when present.
assumed_layouts.txt covers reports whose Excel layout has not been seen yet: those tests only exercise the code.
"""
import glob
import json
import os
import unittest

from parsers import activity_log, derive, figures, registry, xlsxtext as x

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "tests", "data", "xlsx")
LEASEUP, STABLE = "Test Lease-Up Building", "Test Stabilised Building"
PRIVATE = sorted(glob.glob(os.path.join(ROOT, "fixtures", "xlsx_text", "*.txt")))


def load(prop, name):
    return registry.load(DATA, prop, property_name=name)


class TextHelpers(unittest.TestCase):
    def test_serial_dates(self):
        self.assertEqual(x.date("46266"), "2026-09-01")
        self.assertEqual(x.date("46388"), "2027-01-01")
        self.assertEqual(x.date("2026-10-02 07:01:34 a.m. EDT"), "2026-10-02")
        self.assertIsNone(x.date(""))

    def test_numbers_drop_float_noise(self):
        self.assertEqual(x.num("-36849.240000000005"), -36849.24)
        self.assertEqual(x.num("1700"), 1700)
        self.assertEqual(x.num("(3,440.00)"), -3440)
        self.assertIsNone(x.num(""))
        with self.assertRaises(x.LayoutError):
            x.num("abc")

    def test_sheets_split_and_empty_cells_kept(self):
        t = "=== Sheet: A ===\nT\tP\n1\t\t3\n\n=== Sheet: B ===\nx\n"
        s = x.split_sheets(t)
        self.assertEqual([n for n, _ in s], ["A", "B"])
        self.assertEqual(x.cells(s[0][1][1]), ["1", "", "3"])
        self.assertEqual(x.split_sheets("just\ttext")[0][0], "")


class LeaseUp(unittest.TestCase):
    def setUp(self):
        self.r = load("grove", LEASEUP)

    def test_rent_roll(self):
        rr = self.r["Rent Roll"]
        self.assertEqual(len(rr["suites"]), 5)
        self.assertEqual(rr["suites"][2]["status"], "Excluded -Model Unit")
        self.assertEqual(rr["suites"][0]["budget_rent"], 1700)
        self.assertIsNone(rr["suites"][0]["resident"])
        self.assertEqual(len(rr["future"]), 4)
        self.assertEqual(rr["future"][1]["unit"], "101")  # second resident inherits the suite
        self.assertEqual(rr["future"][1]["move_in"], "2027-03-01")
        self.assertEqual(rr["status_summary"]["Vacant Rented Ready"], 3)

    def test_stack_counts_and_deals(self):
        rr = self.r["Rent Roll"]
        st = {u: s for u, _, s in derive.stack(rr, None)}
        self.assertEqual(st, {"101": "progress", "102": "leased", "103": "model", "104": "available", "105": "leased"})
        self.assertEqual(derive.counts(rr, None)["leased"], 2)
        deals = derive.deals(rr, "leaseup")  # leases in progress only
        self.assertEqual([d["unit"] for d in deals], ["101"])
        self.assertEqual(len(derive.deals(rr, "stabilised")), 3)

    def test_rent_figures(self):
        r = derive.rent(self.r["Rent Roll"], None, "leaseup")
        self.assertEqual((r["signed"], r["signedCount"], r["signedBudget"], r["lossToLease"]), (3013, 2, 3013, 0))
        self.assertEqual((r["avgSuite"], r["avgSqft"]), (1507, 2.93))
        self.assertEqual((r["committed"], r["committedCount"]), (4713, 3))
        self.assertEqual((r["fullBudget"], r["fullCount"]), (6026, 4))

    def test_receivables_future_residents_never_owing(self):
        a = derive.arrears(self.r["Resident Aged Receivables"])
        self.assertEqual((a["owing"], a["due"], a["former"], a["future_charges"]), (0, 0, 0, 279.45))

    def test_concessions_blank_total_and_cancelled(self):
        c = derive.concessions(self.r["Concessions"], self.r["Rent Roll"])
        self.assertEqual(c["total"], 3440)
        self.assertEqual([u["unit"] for u in c["units"]], ["102"])
        self.assertEqual(self.r["Concessions"]["rows"][0]["total"], -3440)

    def test_budget_labels_period_and_unknown_headings(self):
        b = derive.budget(self.r["Income Statement - Budget vs Actual"], self.r["Income Statement - Trailing 12"])
        self.assertEqual(b["period"], "2026-09")
        self.assertEqual(b["noi"][:2], [-36849.24, -27478.17])
        self.assertEqual(b["annualNoi"], -375601.04)
        self.assertEqual(b["noiMonths"][0], "2026-01")
        self.assertEqual(b["noiMonths"][-1], "2026-09")
        self.assertEqual(b["noiTrend"][-1], -36849.24)
        self.assertEqual([l[0] for l in b["lines"]], ["Interest on last month's rent deposits", "Payroll"])
        self.assertEqual(b["unknownHeadings"], ["Surprise Heading"])

    def test_work_order_with_line_break_in_cell(self):
        wo = self.r["Work Order Details"]
        self.assertEqual((wo["declared"], len(wo["orders"])), ([1], 1))
        o = wo["orders"][0]
        self.assertEqual((o["ref"], o["unit"], o["created"], o["due"], o["days_open"]), ("17445368", "", "2026-09-28", "2026-12-07", 3))
        self.assertEqual(o["description"], "Test building BID 1 deferred task for December.")


class RenewalsAndIncreases(unittest.TestCase):
    def test_add_months_and_days(self):
        self.assertEqual(derive.add_months("2026-10-01", 12), "2027-10-01")
        self.assertEqual(derive.add_months("2028-02-29", 12), "2029-02-28")
        self.assertEqual(derive.add_months("2026-08-31", 6), "2027-02-28")
        self.assertEqual(derive.add_days("2027-04-20", -90), "2027-01-20")

    def test_by_end_is_the_next_12_months_only(self):
        rr = load("f47", STABLE)["Rent Roll"]
        r = derive.renewals(rr, None, "2026-09-30")
        # three leases: 102 ends 2027-04-28, 101 ends 2027-08-28, and the future resident in 202 ends 2027-09-28
        self.assertTrue(all("2026-09-30" <= d <= "2027-09-30" for d, _ in r["byEnd"]))
        self.assertEqual(sum(c for _, c in r["byEnd"]), 3)
        self.assertEqual(r["firstEnd"], "2027-04-28")
        later = derive.renewals(rr, None, "2026-12-01")  # the 2027-09-28 lease is still inside 12 months
        self.assertEqual(sum(c for _, c in later["byEnd"]), 3)
        early = derive.renewals(rr, None, "2026-05-01")  # only leases ending by 2027-05-01 count
        self.assertEqual([d for d, _ in early["byEnd"]], ["2027-04-28"])

    def test_expiring_leases_count_is_separate(self):
        rr = load("f47", STABLE)["Rent Roll"]
        self.assertEqual(derive.renewals(rr, {"rows": [1, 2]}, "2026-09-30")["expiring120"], 2)
        self.assertEqual(derive.renewals(rr, {"rows": []}, "2026-09-30")["expiring120"], 0)

    def test_increases_one_row_per_lease_with_notice_90_days_before(self):
        rr = load("f47", STABLE)["Rent Roll"]
        # leases start 2026-09-01 (x2): earliest 2027-09-01, notice by 2027-06-03
        self.assertEqual(derive.increases(rr, "2026-09-30"), [])  # notice 2027-06-03 is more than 6 months out
        rows = derive.increases(rr, "2026-12-15")  # window reaches 2027-06-15
        self.assertEqual([(r["num"], r["rent"], r["earliest"], r["noticeBy"]) for r in rows],
                         [("101", 3495, "2027-09-01", "2027-06-03"), ("102", 3000, "2027-09-01", "2027-06-03")])
        self.assertTrue(all(set(r) == {"num", "rent", "earliest", "noticeBy"} for r in rows))  # no newRent
        edge = derive.increases(rr, "2026-12-03")  # window ends 2027-06-03: a notice date on the last day still counts
        self.assertEqual({r["num"] for r in edge}, {"101", "102"})
        self.assertEqual(derive.increases(rr, "2026-12-02"), [])
        late = derive.increases(rr, "2027-08-01")  # notices already due are still listed
        self.assertEqual({r["num"] for r in late}, {"101", "102", "202"})
        self.assertEqual(derive.increases(rr, "2027-08-01"), sorted(late, key=lambda r: (r["noticeBy"], r["num"])))

    def test_renewed_suites_are_left_off(self):
        import copy
        rr = load("f47", STABLE)["Rent Roll"]
        ar = load("f47", STABLE)["Resident Aged Receivables"]
        self.assertEqual(derive.renewed_units(rr, ar), [])
        ar2 = copy.deepcopy(ar)
        ar2["rows"][1]["status"] = "Current - Renewed"  # suite 102
        self.assertEqual(derive.renewed_units(rr, ar2), ["102"])
        self.assertEqual([r["num"] for r in derive.increases(rr, "2026-12-15", derive.renewed_units(rr, ar2))], ["101"])
        rr2 = copy.deepcopy(rr)  # a renewal lease on an occupied suite: a future lease for the same suite
        rr2["future"].append(dict(rr["future"][0], unit="101", resident="Fakename, Newterm", lease_start="2027-09-01"))
        self.assertEqual(derive.renewed_units(rr2, None), ["101"])
        self.assertEqual([r["num"] for r in derive.increases(rr2, "2026-12-15", derive.renewed_units(rr2, None))], ["102"])

    def test_future_lease_on_an_empty_suite_is_not_a_renewal(self):
        rr = load("grove", LEASEUP)["Rent Roll"]  # suite 101 has two future residents and no current one
        self.assertEqual(derive.renewed_units(rr, None), [])

    def test_availability_notes_are_never_a_lease_date_source(self):
        import inspect
        self.assertNotIn("availab", inspect.getsource(derive.increases).split('"""')[2].lower())  # code uses lease start only

    def test_lease_start_to_confirm_is_reported_while_listed(self):
        old = dict(derive.LEASE_START_TO_CONFIRM)
        derive.LEASE_START_TO_CONFIRM["f47"] = ["101", "999"]
        try:
            f = figures.build(DATA, "f47", "2026-12-14", property_name=STABLE, as_at="2026-12-15")
        finally:
            derive.LEASE_START_TO_CONFIRM.clear()
            derive.LEASE_START_TO_CONFIRM.update(old)
        self.assertEqual(f["leaseStartToConfirm"], ["101"])  # 999 is not on the list, so it is not reported
        self.assertEqual(f["renewedSuites"], [])
        self.assertNotIn("increasesBasis", f)  # no --previous, so no way to say the list changed

    def test_basis_line_only_when_the_increases_list_changes(self):
        now = figures.build(DATA, "f47", "2026-12-14", property_name=STABLE, as_at="2026-12-15")["increases"]
        self.assertEqual([r["num"] for r in now], ["101", "102"])

        def prev(nums):
            return {"properties": [{"id": "f47", "increases": [{"num": n} for n in nums]}]}

        same = figures.build(DATA, "f47", "2026-12-14", property_name=STABLE, as_at="2026-12-15", previous_feed=prev(["101", "102"]))
        self.assertEqual(same["increasesChange"], {"added": [], "dropped": []})
        self.assertNotIn("increasesBasis", same)
        added = figures.build(DATA, "f47", "2026-12-14", property_name=STABLE, as_at="2026-12-15", previous_feed=prev(["101"]))
        self.assertEqual(added["increasesChange"], {"added": ["102"], "dropped": []})
        self.assertIn("lease start", added["increasesBasis"])
        dropped = figures.build(DATA, "f47", "2026-12-14", property_name=STABLE, as_at="2026-12-15", previous_feed=prev(["101", "102", "303"]))
        self.assertEqual(dropped["increasesChange"], {"added": [], "dropped": ["303"]})
        self.assertIn("lease start", dropped["increasesBasis"])

    def test_no_suite_is_waiting_for_a_lease_start_confirmation(self):
        self.assertEqual(derive.LEASE_START_TO_CONFIRM, {})

    def test_lease_up_future_leases_are_not_due(self):
        rr = load("grove", LEASEUP)["Rent Roll"]
        self.assertEqual(derive.increases(rr, "2026-10-01"), [])
        self.assertEqual(derive.renewals(rr, None, "2026-10-01")["byEnd"], [])


class NewFieldsForTemplate12(unittest.TestCase):
    def test_month_to_month_counts_occupied_leases_with_no_end_or_a_past_end(self):
        import copy
        rr = load("f47", STABLE)["Rent Roll"]
        self.assertEqual(derive.mtm_count(rr, "2026-10-02"), 0)  # both leases end in 2027
        rr2 = copy.deepcopy(rr)
        rr2["suites"][0]["lease_end"] = "2026-09-28"  # ended and still living there
        rr2["suites"][1]["lease_end"] = None  # no end date
        self.assertEqual(derive.mtm_count(rr2, "2026-10-02"), 2)
        self.assertEqual(derive.mtm_count(rr2, "2026-09-27"), 1)  # not yet ended on 2026-09-27
        rr2["suites"][2]["lease_end"] = None  # a vacant suite is never month to month
        self.assertEqual(derive.mtm_count(rr2, "2026-10-02"), 2)

    def test_lease_up_building_has_no_month_to_month(self):
        self.assertEqual(derive.mtm_count(load("grove", LEASEUP)["Rent Roll"], "2026-10-02"), 0)

    def test_rent_roll_charge_codes_and_parking_income(self):
        rr = load("f47", STABLE)["Rent Roll"]
        names = [c["name"] for c in rr["charge_codes"]]
        self.assertEqual(names, ["Ledger: Resident", "Delta Rent", "Parking, Residents"])
        self.assertEqual(derive.parking_income(rr), 400)
        self.assertEqual(figures.build(DATA, "f47", "2026-09-30", property_name=STABLE).get("items"), None)  # no Rentable Items sheet here
        self.assertIsNone(derive.parking_income(load("grove", LEASEUP)["Rent Roll"]))  # no charge codes at all

    def test_parking_income_is_never_estimated(self):
        self.assertIsNone(derive.parking_income({"charge_codes": [{"name": "Delta Rent", "scheduled": 170, "type": "Rent"}]}))
        self.assertIsNone(derive.parking_income({"charge_codes": [{"name": "Parking", "scheduled": None, "type": ""}]}))
        self.assertIsNone(derive.parking_income({}))
        self.assertEqual(derive.parking_income({"charge_codes": [{"name": "Parking, Residents", "scheduled": 80, "type": "Rent"},
                                                                 {"name": "Parking, Visitors", "scheduled": 20.5, "type": "Rent"}]}), 100.5)

    def test_figures_write_mtm_and_name_the_fields_the_reports_do_not_carry(self):
        f = figures.build(DATA, "f47", "2026-09-30", property_name=STABLE, as_at="2026-10-01")
        self.assertEqual(f["renewals"]["mtm"], 0)
        gaps = " ".join(f["notCarried"])
        self.assertIn("leadsWeek", gaps)
        self.assertIn("funnel.since", gaps)
        self.assertNotIn("items.income", gaps)  # this Rent Roll does carry a parking code
        self.assertNotIn("leadsWeek", f)
        self.assertNotIn("since", f.get("funnel", {}))


class FinancialMonth(unittest.TestCase):
    """Only the post month the statements report is used; unchanged months are kept; changed closed months are restated."""

    def setUp(self):
        r = load("grove", LEASEUP)
        self.new = derive.budget(r["Income Statement - Budget vs Actual"], r["Income Statement - Trailing 12"])

    def old_from(self, new):
        return {"period": "Sep 2026", "noi": list(new["noi"]), "annualNoi": new["annualNoi"], "lines": [list(l) for l in new["lines"]],
                "noiMonths": list(new["noiMonths"]), "noiTrend": list(new["noiTrend"])}

    def test_partial_current_month_is_never_used(self):
        self.assertEqual(self.new["noiMonths"][-1], "2026-09")  # the sheet also has an Oct 2026 column (partial): not shown
        self.assertNotIn("2026-10", self.new["noiMonths"])

    def test_same_month_same_figures_is_kept(self):
        st = derive.budget_status(self.new, self.old_from(self.new))
        self.assertTrue(st["keep"])
        self.assertEqual((st["restated"], st["periodChanged"], st["behind"]), ([], False, False))

    def test_new_month_is_not_kept_and_not_restated(self):
        old = self.old_from(self.new)
        old["period"] = "Aug 2026"
        old["noiMonths"], old["noiTrend"] = old["noiMonths"][:-1], old["noiTrend"][:-1]
        st = derive.budget_status(self.new, old)
        self.assertFalse(st["keep"])
        self.assertTrue(st["periodChanged"])
        self.assertEqual(st["restated"], [])

    def test_changed_closed_month_is_restated(self):
        old = self.old_from(self.new)
        old["noiTrend"][-3] += 100  # an earlier closed month now reads differently
        st = derive.budget_status(self.new, old)
        self.assertEqual(st["restated"], [self.new["noiMonths"][-3]])
        self.assertFalse(st["keep"])
        old = self.old_from(self.new)
        old["noi"][0] += 50  # the reported month itself changed
        self.assertEqual(derive.budget_status(self.new, old)["restated"], ["2026-09"])

    def test_report_month_going_backwards_keeps_the_feed(self):
        old = self.old_from(self.new)
        old["period"] = "Oct 2026"
        st = derive.budget_status(self.new, old)
        self.assertTrue(st["behind"] and st["keep"])

    def test_month_label(self):
        self.assertEqual(derive.month_of_label("Sep 2026 (run 2026-10-01)"), "2026-09")
        self.assertIsNone(derive.month_of_label(""))


class Stabilised(unittest.TestCase):
    def setUp(self):
        self.r = load("f47", STABLE)

    def test_rent_figures(self):
        r = derive.rent(self.r["Rent Roll"], None, "stabilised")
        self.assertEqual((r["inPlace"], r["occupiedCount"], r["avgSuite"]), (6495, 2, 3248))  # 3247.5 rounds up
        self.assertEqual(r["avgSqft"], round(6495 / (869 + 712), 2))
        self.assertEqual(r["futureRent"], 1585)

    def test_deals_are_every_future_resident(self):
        self.assertEqual([d["unit"] for d in derive.deals(self.r["Rent Roll"], "stabilised")], ["202"])

    def test_receivables_split_current_overdue_former(self):
        a = derive.arrears(self.r["Resident Aged Receivables"])
        self.assertEqual(a["owing"], 100)
        self.assertEqual(a["due"], 150)
        self.assertEqual((a["former"], a["formerCount"]), (6800, 1))
        rows = self.r["Resident Aged Receivables"]["rows"]
        self.assertEqual(rows[2]["note"], "2026-03-03 02:27 p.m. Test note second line of the note")
        self.assertEqual(rows[3]["unit"], "")

    def test_open_work_orders_only(self):
        wo = self.r["Work Order Details"]
        self.assertEqual(len(wo["orders"]), 3)
        o = {w["ref"]: w for w in derive.open_work_orders(wo)}
        self.assertEqual(sorted(o), ["17445203", "17445467"])
        self.assertEqual(o["17445203"]["vendor"], "Dependable Appliances (Kingston)")  # exactly as Entrata reports it
        self.assertIn("second paragraph", o["17445203"]["note"])
        self.assertIsNone(o["17445467"]["employee"])
        self.assertIsNone(o["17445467"]["due"])

    def test_concessions_leave_out_cancelled_lease(self):
        c = derive.concessions(self.r["Concessions"], self.r["Rent Roll"])
        self.assertEqual(c["total"], 3495 + 1800)
        self.assertEqual(len(c["units"]), 2)

    def test_budget_label_table(self):
        b = derive.budget(self.r["Income Statement - Budget vs Actual"], self.r["Income Statement - Trailing 12"])
        self.assertEqual([l[0] for l in b["lines"]], ["Rental income", "Other income", "Administration"])
        self.assertEqual(b["lines"][0][1:], [48530, 76000, 307965, 670588.24])
        self.assertEqual(b["unknownHeadings"], [])
        self.assertEqual(b["noiMonths"], ["2026-08", "2026-09"])  # October is not closed
        self.assertEqual(b["noi"][0], 33531.72)


class MissingAndUnreadable(unittest.TestCase):
    def test_missing_report_is_listed_not_guessed(self):
        r = load("f47", STABLE)
        self.assertIn("Availability", r["missing"])
        self.assertIsNone(r["Availability"])
        self.assertEqual(r["unreadable"], [])

    def test_other_property_does_not_leak(self):
        r = registry.load(DATA, "grove", property_name="No Such Property")
        self.assertEqual(sorted(r["missing"]), sorted(registry.EXPECTED))

    def test_unreadable_sheet_is_flagged_and_others_still_read(self):
        import shutil
        import tempfile
        d = tempfile.mkdtemp()
        try:
            shutil.copy(os.path.join(DATA, "stabilised_workbook.txt"), d)
            with open(os.path.join(d, "bad.txt"), "w") as f:
                f.write("=== Sheet: Availability ===\nAvailability (CC)\n" + STABLE + "\nAs of 2026-10-01\nnot a table\n")
            r = registry.load(d, "f47", property_name=STABLE)
        finally:
            shutil.rmtree(d)
        self.assertEqual([u["report"] for u in r["unreadable"]], ["Availability"])
        self.assertIsNone(r["Availability"])
        self.assertIsNotNone(r["Rent Roll"])  # one bad report does not stop the others

    def test_figures_carry_the_flags(self):
        f = figures.build(DATA, "f47", "2026-09-30", property_name=STABLE)
        self.assertIn("Availability", f["missing"])
        self.assertEqual(f["snapshot"]["date"], "2026-09-30")
        self.assertEqual(len(f["workOrders"]), 2)
        self.assertNotIn("inventory", f)
        prev = json.load(open(os.path.join(ROOT, "feeds", "2026-10-02.json")))
        f2 = figures.build(DATA, "f47", "2026-09-30", property_name=STABLE, previous_feed=prev)
        self.assertIn("budgetStatus", f2)


class AssumedLayouts(unittest.TestCase):
    """The Excel layouts of these five reports have not been seen. These tests only run the code."""

    def setUp(self):
        self.r = load("grove", LEASEUP)

    def test_every_assumed_report_warns(self):
        w = " ".join(self.r["warnings"])
        for name in ("Availability", "Lease Term Progress Summary", "Activity Log", "Rentable Items Availability", "Expiring Leases"):
            self.assertIn(name, w)

    def test_availability(self):
        av = self.r["Availability"]
        self.assertEqual({k: v["found"] for k, v in av["sections"].items()}, {"Vacant Unrented Ready": 1, "Vacant Rented Ready": 1})
        self.assertEqual(av["units"][1]["lease_rent"], 1700)
        self.assertEqual(av["units"][1]["available_on"], "2027-01-01")

    def test_lease_term_progress(self):
        lt = self.r["Lease Term Progress Summary"]
        self.assertEqual((lt["stages"][0][1], lt["total"], lt["avg_total"]), (19, 36, "11:08:06"))
        self.assertEqual(derive.funnel(lt)["apps"], 11)

    def test_activity_log_dedupes(self):
        al = self.r["Activity Log"]["entries"]
        self.assertEqual(len(al), 3)
        self.assertEqual(len(activity_log.dedupe(al)), 2)
        self.assertEqual(al[0]["when"], "2026-09-30 12:03")
        self.assertEqual(al[0]["description"], "Wants a one bedroom. Second line.")
        self.assertEqual(al[1]["unit"], "")

    def test_rentable_items(self):
        p = derive.parking(self.r["Rentable Items Availability"])
        self.assertEqual(p["list"], [["P54", "Reserved", "205"], ["P59", "Available", ""], ["P67 (accessible)", "Available", ""]])

    def test_expiring_leases_empty(self):
        ex = self.r["Expiring Leases"]
        self.assertTrue(ex["no_data"])
        self.assertEqual(ex["rows"], [])


@unittest.skipUnless(PRIVATE, "real workbooks not present")
class RealWorkbooks(unittest.TestCase):
    """The Cityflats ownership workbooks of 2026-10-01 (Sep 2026 data). Shapes and totals tie out."""

    def test_rent_rolls(self):
        g = registry.load(os.path.join(ROOT, "fixtures", "xlsx_text"), "grove")
        f = registry.load(os.path.join(ROOT, "fixtures", "xlsx_text"), "f47")
        self.assertEqual(len(g["Rent Roll"]["suites"]), 82)
        self.assertEqual(g["Rent Roll"]["status_summary"]["Vacant Rented Ready"], 31)
        self.assertAlmostEqual(sum(s["scheduled"] or 0 for s in g["Rent Roll"]["future"]), g["Rent Roll"]["totals"]["future"][2], 2)
        self.assertEqual(len(f["Rent Roll"]["suites"]), 19)
        occ = [s for s in f["Rent Roll"]["suites"] if s["status"].startswith("Occupied")]
        self.assertAlmostEqual(sum(s["scheduled"] for s in occ), 59420)

    def test_f47_reports(self):
        f = registry.load(os.path.join(ROOT, "fixtures", "xlsx_text"), "f47")
        self.assertEqual(f["Work Order Details"]["declared"], [33])
        self.assertEqual(len(f["Work Order Details"]["orders"]), 33)
        self.assertAlmostEqual(sum(r["total"] for r in f["Concessions"]["rows"]), -67225)
        self.assertAlmostEqual(f["Concessions"]["totals"][2], -67225)
        a = derive.arrears(f["Resident Aged Receivables"])
        self.assertEqual((a["owing"], a["former"], a["formerCount"]), (0, 13735.5, 2))
        b = derive.budget(f["Income Statement - Budget vs Actual"], f["Income Statement - Trailing 12"])
        self.assertEqual(b["noi"][0], 29435.14)
        self.assertEqual(b["unknownHeadings"], [])
        self.assertEqual(len(b["lines"]), 13)

    def test_real_rent_rolls_carry_no_parking_charges(self):
        for pid in ("grove", "f47"):
            r = registry.load(os.path.join(ROOT, "fixtures", "xlsx_text"), pid)
            self.assertIsNone(derive.parking_income(r["Rent Roll"]), pid)
            self.assertEqual(derive.mtm_count(r["Rent Roll"], "2026-10-02"), 0, pid)


if __name__ == "__main__":
    unittest.main()
