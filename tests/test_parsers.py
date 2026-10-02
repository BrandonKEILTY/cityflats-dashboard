"""Run: python -m unittest discover -s tests -v

Needs the four fixture folders in fixtures/ (git-ignored: they hold resident names and
balances). Tests are skipped when the PDFs are not there.
"""
import glob
import os
import unittest

from parsers import (activity_log, availability, concessions, derive, expiring_leases, income_budget, income_t12,
                     lease_term_progress, receivables, registry, rent_roll, rentable_items, work_orders)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def folder(prop, stamp):
    hits = glob.glob(os.path.join(ROOT, "fixtures", f"Command_Center_Reports_-_{prop}_-_{stamp}"))
    return hits[0] if hits else None


G1, F1 = folder("The_Grove", "2026-10-01_0951"), folder("Faculty47", "2026-10-01_0951")
G0, F0 = folder("The_Grove", "2026-09-30_1813"), folder("Faculty47", "2026-09-30_1756")


def pdf(d, prefix):
    return sorted(glob.glob(os.path.join(d, prefix + "*.pdf")))[0]


@unittest.skipUnless(G1 and F1, "fixtures not present")
class PriorityReports(unittest.TestCase):
    def test_rent_roll_grove(self):
        r = rent_roll.parse(pdf(G1, "Rent Roll"))
        self.assertEqual(len(r["suites"]), 82)
        self.assertEqual(r["status_summary"]["Vacant Rented Ready"], 30)
        self.assertEqual(r["status_summary"]["Vacant Unrented Ready"], 51)
        self.assertEqual(r["totals"]["future"][1], 56231.0)  # scheduled charges total printed on the report
        self.assertAlmostEqual(sum(f["scheduled"] or 0 for f in r["future"]), 56231.0)
        self.assertEqual(len(r["future"]), 31)  # 30 suites; 101 has two future residents
        self.assertEqual(sum(1 for s in r["suites"] if s["status"].startswith("Excluded")), 1)

    def test_rent_roll_f47(self):
        r = rent_roll.parse(pdf(F1, "Rent Roll"))
        self.assertEqual(len(r["suites"]), 19)
        occ = [s for s in r["suites"] if s["status"].startswith("Occupied")]
        self.assertEqual(len(occ), 16)
        self.assertAlmostEqual(sum(s["scheduled"] for s in occ), 59420.0)
        self.assertEqual([f["unit"] for f in r["future"]], ["202", "301C"])
        self.assertEqual(r["future"][1]["resident"], "[name removed]")

    def test_availability(self):
        g = availability.parse(pdf(G1, "Availability"))
        self.assertEqual({k: v["found"] for k, v in g["sections"].items()}, {k: v["declared"] for k, v in g["sections"].items()})
        self.assertEqual(len(g["units"]), 82)
        self.assertEqual(g["totals"]["non_excluded"][1], 175397.0)
        f = availability.parse(pdf(F1, "Availability"))
        self.assertEqual(len(f["units"]), 19)
        self.assertEqual(f["totals"]["non_excluded"][1], 56705.0)

    def test_receivables(self):
        g = receivables.parse(pdf(G1, "Resident Aged"))
        self.assertEqual(len(g["rows"]), 5)
        self.assertEqual({r["kind"] for r in g["rows"]}, {"future"})
        self.assertEqual(derive.arrears(g)["owing"], 0)
        f = receivables.parse(pdf(F1, "Resident Aged"))
        a = derive.arrears(f)
        self.assertEqual((a["owing"], a["former"], a["formerCount"]), (0, 13735.5, 2))
        self.assertAlmostEqual(sum(r["balance"] for r in f["rows"]), f["totals"]["balance"])
        zhang = next(r for r in f["rows"] if r["resident"].startswith("Zhang"))
        self.assertEqual(zhang["kind"], "former")
        self.assertIn("collections", zhang["note"])
        self.assertEqual(next(r for r in f["rows"] if r["resident"].startswith("Scott"))["unit"], "")

    def test_work_orders(self):
        g = work_orders.parse(pdf(G1, "Work Order Details - Cityflats (CC - Current)"))
        self.assertEqual((g["declared"], len(g["orders"])), (1, 1))
        self.assertEqual(g["orders"][0]["ref"], "17445368")
        f = work_orders.parse(pdf(F1, "Work Order Details - Cityflats (CC - Current)"))
        self.assertEqual((f["declared"], len(f["orders"])), (13, 13))
        by = {o["ref"]: o for o in f["orders"]}
        self.assertEqual(by["17442365"]["vendor"], "Ainsworth Inc.")
        self.assertEqual(by["17445203"]["vendor"], "Dependable Appliances (Kingston)")
        self.assertEqual(by["17441969"]["days_open"], 117)
        self.assertEqual(by["17445467"]["employee"], None)
        self.assertEqual(by["17444642"]["location"], "Bathroom")
        self.assertTrue(all(not o["needs_review"] for o in f["orders"]))
        prior = work_orders.parse(pdf(F1, "Work Order Details - Cityflats (CC - Prior)"))
        self.assertEqual(prior["orders"], [])
        self.assertEqual(len(work_orders.combine(f, prior)), 13)


@unittest.skipUnless(G1 and F1, "fixtures not present")
class OtherReports(unittest.TestCase):
    def test_activity_log(self):
        g = activity_log.parse(pdf(G1, "Activity Log"))
        self.assertEqual(len(g["entries"]), 5)
        self.assertEqual(g["activity_date"], "2026-09-30")
        e = next(x for x in g["entries"] if x["name"].startswith("Jaja"))
        self.assertEqual((e["when"], e["type"], e["agent"]), ("2026-09-30 14:15", "Tour", "Mercier, Cassandra"))
        self.assertTrue(e["description"].startswith("interested in affordable housing"))
        self.assertTrue(e["description"].endswith("no car, no pets."))
        f = activity_log.parse(pdf(F1, "Activity Log"))
        self.assertEqual([x["type"] for x in f["entries"]], ["Tour", "Notes"])
        self.assertEqual(f["entries"][0]["unit"], "301C")

    def test_activity_log_dedupe(self):
        a = {"name": "X, Y", "when": "2026-10-01 10:00", "type": "Tour"}
        b = dict(a, type="Notes")
        self.assertEqual(activity_log.dedupe([a, dict(a), b, dict(a)]), [a, b])

    def test_lease_term_progress(self):
        g = lease_term_progress.parse(pdf(G1, "Lease Term Progress"))
        self.assertEqual((g["stages"][0][1], g["total"]), (19, 36))
        self.assertEqual(derive.funnel(g)["apps"], 11)
        self.assertEqual(g["stages"][-1], ["Lease approved", 4, None])
        f = lease_term_progress.parse(pdf(F1, "Lease Term Progress"))
        self.assertEqual((f["total"], f["avg_total"]), (2, "00:00:00"))

    def test_concessions(self):
        g = concessions.parse(pdf(G1, "Concessions"))
        self.assertEqual(len(g["rows"]), 2)
        self.assertEqual(g["totals"][2], -9280.0)
        f = concessions.parse(pdf(F0, "Concessions"))
        self.assertEqual(len(f["rows"]), 12)
        self.assertEqual(f["totals"][2], -67225.0)
        rr = rent_roll.parse(pdf(F0, "Rent Roll"))
        self.assertEqual(derive.concessions(f, rr)["total"], 63475.0)  # cancelled lease (103 Hulme) left out

    def test_rentable_items(self):
        g = rentable_items.parse(pdf(G1, "Rentable Items"))
        self.assertEqual((g["declared"], len(g["items"])), (86, 86))
        self.assertIn(["P67 (accessible)", "Available", ""], derive.parking(g)["list"])
        self.assertIn(["P54", "Reserved", "205"], derive.parking(g)["list"])
        f = rentable_items.parse(pdf(F1, "Rentable Items"))
        self.assertEqual((f["declared"], len(f["items"])), (17, 17))
        self.assertIn(["P16 (snow spot)", "Available", ""], derive.parking(f)["list"])

    def test_expiring_leases_empty(self):
        for d in (G1, F1):
            r = expiring_leases.parse(pdf(d, "Expiring Leases"))
            self.assertTrue(r["no_data"])
            self.assertEqual(r["rows"], [])

    def test_income_statements(self):
        b = income_budget.parse(pdf(G1, "Income Statement - Budget"))
        t = income_t12.parse(pdf(G1, "Income Statement - Trailing"))
        m = derive.budget(b, t)
        self.assertEqual(m["noi"], [-36849.24, -27478.17, -204241.84, -297508.53])
        self.assertEqual(m["annualNoi"], -375601.04)
        self.assertEqual(m["noiMonths"][0], "2026-01")
        self.assertEqual(m["noiMonths"][-1], "2026-09")
        self.assertEqual(m["noiTrend"][-1], -36849.24)
        fb = income_budget.parse(pdf(F1, "Income Statement - Budget"))
        ft = income_t12.parse(pdf(F1, "Income Statement - Trailing"))
        fm = derive.budget(fb, ft)
        self.assertEqual(fm["noi"][0], 33531.72)
        self.assertEqual(len(fm["noiMonths"]), 12)


@unittest.skipUnless(G1 and F1 and G0 and F0, "fixtures not present")
class MissingReports(unittest.TestCase):
    def test_expiring_leases_absent_on_09_30(self):
        for d in (G0, F0):
            r = registry.load(d)
            self.assertIn("Expiring Leases", r["missing"])
            self.assertIsNone(r["Expiring Leases"])
        self.assertNotIn("Expiring Leases", registry.load(G1)["missing"])

    def test_prior_year_work_orders_only_for_faculty47(self):
        self.assertEqual(registry.load(F1)["Work Order Details"]["files"], 2)
        self.assertEqual(registry.load(G1)["Work Order Details"]["files"], 1)

    def test_faculty47_concessions_absent_on_10_01(self):
        self.assertIn("Concessions", registry.load(F1)["missing"])
        self.assertNotIn("Concessions", registry.load(F0)["missing"])

    def test_09_30_work_orders_are_all_completed_for_faculty47(self):
        wo = registry.load(F0)["Work Order Details"]
        self.assertEqual(len(wo["orders"]), 13)
        self.assertEqual(derive.open_work_orders(wo), [])


@unittest.skipUnless(G1 and F1, "fixtures not present")
class Derived(unittest.TestCase):
    def test_counts_match_report_totals(self):
        g = registry.load(G1)
        c = derive.counts(g["Rent Roll"], g["Availability"])
        self.assertEqual(c["leased"] + c["inProgress"], 30)
        self.assertEqual(c["leased"] + c["inProgress"] + c["applications"] + c["available"], 81)
        self.assertEqual(c["available"], 51)
        f = registry.load(F1)
        c = derive.counts(f["Rent Roll"], f["Availability"])
        self.assertEqual((c["occupied"], c["leased"], c["inProgress"], c["available"]), (16, 1, 1, 1))


if __name__ == "__main__":
    unittest.main()
