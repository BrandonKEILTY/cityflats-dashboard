# Cityflats Dashboard: daily routine (Claude Code, cloud)

Prepared 2026-10-02 for Brandon Ackerman (KEILTY Realty Management Inc.).
Dates are always YYYY-MM-DD. Canadian spelling. No em dashes in anything the client sees.

This folder goes into a GitHub repository. A **Claude Code routine** clones that repository every morning, follows these instructions and refreshes the dashboard, all in the cloud. My computer doesn't need to be on.

---

## 0. Before building anything

1. Look at how the Command Center's routine works: its repository, prompt, connectors, and how it gets each morning's results onto the Command Center.
2. Tell me in a few lines what you found.
3. Build this one the same way.

The Command Center's daily results land in its artifact database (collection `board`, document `feed`), so the page itself is not republished each day. This dashboard should work the same way (see section 3).

---

## 1. What exists today

| | |
|---|---|
| Dashboard | **Cityflats Dashboard**, https://claude.ai/artifact/JLRG3EwBZa3G1576ZJ8xxy |
| Published files today | `index.html` (the page), `data.js` (every figure), `cityflats-logo.png` |
| Current updater | A Claude app scheduled task, "City Flats Dashboard, daily update", 6:00 a.m. daily. It needs my computer on. The full rules are in `daily-job-rules.md`. |
| Command Center (data source and model) | https://claude.ai/artifact/ErKdkkfCb4PMfw4uwSchLW |
| Client | Centennial Land Development LP and Faculty 47 Development LP |
| Properties | `grove`: The Cedar at the Grove, 1245 Centennial Drive, Kingston (lease-up, 82 suites, 81 rentable plus model suite 103, target full 2027-03-01)<br>`f47`: Faculty47, 47 Wellington Street, Kingston (stabilised, 17 suites let as 19 rentable units; 301 is let as 301A, 301B and 301C) |

This folder holds live copies of `index.html`, `data.js` and `cityflats-logo.png` from 2026-10-02.

---

## 2. What each run does

`daily-job-rules.md` is the specification. In short:

1. **Read today's Entrata emails** through the Microsoft 365 / Outlook connector. The figures come from the **Excel attachments**, not the PDFs: the connector returns an `.xlsx` as clean tab-separated text (empty cells kept, dates as Excel serial numbers) but flattens a PDF.
   - They arrive in Brandon.Ackerman@keilty.com at about 3:00 a.m. from system@entrata.com, with subjects starting "Entrata Reports - Command Center Reports - ...".
   - There are several packages, so read them all.
   - Keep only the rows for "The Cedar at the Grove" and "Faculty47".
2. **Get the figures from the parsers** (section 4 and "How to run the parsers" below), not by reading the spreadsheets yourself. Every number comes from `python -m parsers.figures`. Your own judgement is for client wording only (notes, problem text, prospect note text, open-item sentences) and for the Command Center items.
3. **Read the Command Center's open items and tours booked, read only.** These come from the page's built-in `"items":` array, then `board/newitems`, then `board/edits`, using the filters in STEP 3. **Never write to the Command Center.**
4. **Add one history snapshot**, dated yesterday.
5. **Run the checks in section 6.** If any check fails, don't save.
6. **Save the day's feed** to the dashboard (section 3).
7. **Commit** the day's feed to the repository as `feeds/YYYY-MM-DD.json`, so there's a record and a way to roll back.
8. **Email me a short summary** (STEP 5 of the rules).

If no Entrata email arrived, still refresh the Command Center items, leave the Entrata figures as they were, save, and say so in the summary.

---

## 3. How the routine updates the page (do this first, once)

**The problem:** a routine only republishes an artifact without asking when the publish is the page alone, with no supporting files, and the artifact's viewers don't automatically see each new version. Today the dashboard has two supporting files and is shared with the organization so viewers see updates immediately. A run would stop and wait for approval that nobody gives at 6 a.m.

**The fix, the same pattern as the Command Center:**

1. **Make the page read its figures from its own artifact database.**
   - Store them in collection `dash`, document `feed`; the value is the same object that `data.js` sets today.
   - Keep `data.js` loaded only as a fallback for the first load.
   - Inline the logo as a data URI, so the page has no supporting files.
2. **Republish the page once by hand** (with me present) with the database capability. After that, the page never needs republishing for a daily update.
3. **The routine then only writes the database document** `dash/feed`, pinned to the version it last read. No publish, so no approval stop.
4. **Check before switching over:** confirm in a test run that the database write goes through unattended. If it needs approval, tell me; don't work around it.

---

## 4. The reading is fixed code (done, in `parsers/`)

The same report is read the same way every morning. One parser per report, committed here. **The full run steps are in `ROUTINE.md`.**

- **Input:** the text the Outlook connector returns for each `.xlsx` attachment, saved exactly as returned, one `.txt` file per attachment. Cells are separated by tabs, empty cells are kept, a cell with a line break continues on the next line, dates are Excel serial numbers (46266 = 2026-09-01), and each sheet starts with `=== Sheet: <name> ===`. Sheets are found by the report title on the first line and the property on the second, so any package layout works. Columns are found by their heading, so an added column does not break a parser.
- **Numbers come from the scripts.** Only wording is yours: short client sentences and the cleaning rules in section 5.
- **Not used:** PDFs. The connector returns PDF text flattened, which is not reliable. `parsers/pdf/` keeps the old PDF readers as a layout reference (they need real PDF files, which the cloud run never has). If a report has no Excel at all, keep its last figures and flag it; reading the PDF text by hand is a last resort and must be flagged.
- **Setup script for the routine's cloud environment:** `pip install -r requirements.txt`. The render check uses Playwright with the Chromium that is already installed.

### What has been checked against real Excel text

| Layout checked on real workbooks (Cityflats ownership package, Grove and Faculty47) | Written from the PDF headings only (no Excel export seen yet) |
|---|---|
| Rent Roll, Resident Aged Receivables, Concessions, Work Order Details, Income Statement Budget vs Actual, Income Statement Trailing 12 | Availability, Lease Term Progress Summary, Activity Log, Rentable Items Availability, Expiring Leases |

The five on the right are read with the same header-driven approach, but until a real Command Center Excel export of each has been run through them, every run lists them under `warnings` so the figures get a look. Once a real export has been compared and tests added, set `LAYOUT_CHECKED = True` in that module.

### How to run the parsers

```
pip install -r requirements.txt
# one property, one folder of that day's saved attachment text:
python -m parsers.figures work/YYYY-MM-DD grove --data-through YYYY-MM-DD > grove.json
python -m parsers.figures work/YYYY-MM-DD f47   --data-through YYYY-MM-DD > f47.json
# Command Center items and tours (read only):
python tools/command_center.py <saved page> <newitems.json> <edits.json> --today YYYY-MM-DD
# before every save:
python tools/check_feed.py new.json previous.json
python tools/render_check.py new.json
# tests:
python -m unittest discover -s tests -v
```

- `figures` prints counts, stack, deals, rent, renewals, inventory units, arrears, funnel, concessions, parking items, budget (with `lines` labelled and any `unknownHeadings`), open work orders, the day's activity entries and the history snapshot (dated `--data-through`).
- `missing` lists reports with no sheet for the property: keep the last figures and raise a `missing` flag. `unreadable` lists sheets a parser could not read: keep the last figures, raise a `fix` flag, **carry on with the other reports**. `warnings` are passed on in the summary.
- Only a failed whole-feed check (section 6) stops the run.

### Fixed rules for the fields the parsers build

- **Grove `rent`:** `signed` = rent on the leased suites; `signedCount` = how many; `signedBudget` = Availability's budgeted rent for the same suites; `lossToLease` = `signedBudget` minus `signed` (0 shows as "On budget"); `avgSuite` = `signed` / `signedCount`; `avgSqft` = `signed` / those suites' square feet; `committed` = `signed` plus the rent on leases in progress; `fullBudget` = budgeted rent for all 81 rentable suites.
- **Faculty47 `rent`:** `inPlace` = current rent on occupied suites; `avgSuite` = `inPlace` / `occupiedCount`; `avgSqft` = `inPlace` / those suites' square feet; `futureRent` = rent of the "leased, moving in" future residents.
- **`budget.lines`:** the Budget vs Actual sections in plain wording through a fixed table (`BUDGET_LABELS` in `parsers/derive.py`). A heading not in the table is listed in the summary, not guessed.
- **Carried forward unchanged:** `inventory.plans`, `inventory.askingAvg` (the page doesn't use them) and `weeklyChecklist` (team view only).

## 5. Feed structure and rules

### Top level

`asAt` (run date), `dataThrough` (yesterday), `rentRollAsOf`, `client`, `short`, `generated`, `weeklyChecklist`, `properties` (list of two).

### Each property

| Key | What it holds | Source |
|---|---|---|
| `id, name, address, entity, mode, units, rentable, model, target, targetSource, delivery, stalls, leaseupPts` | Fixed facts | Never change |
| `weeks`, `missedWeeks` | The team's weekly history up to 2026-09-30 | **Never change** |
| `planBeds` (if present) | Floor plan to bedrooms, set by me | **Never change** |
| `counts` | `leased, inProgress, applications, available, toursToday` (F47 also `occupied`) | Rent Roll, Availability, Activity Log |
| `stack` | `[suite, plan, status]`; status is `occupied, leased, progress, applied, available, model` | Availability + Rent Roll |
| `deals` | `{unit, plan, rent, movein}`, one per suite. Grove (lease-up): only leases in progress ("Leases in progress"). Faculty47 (stabilised): every future resident, leased or in progress ("Moving in"). | Rent Roll |
| `inventory` | `{source, plans, askingAvg, unleasedMonthly, units}`; `units` is `[suite, plan, sqft, budgeted rent, available on, status]`. "Available on" is the report's date for every suite, occupied ones included (the page only shows it for suites that are not occupied). | Availability |
| `funnel` | `{source, stages, total, avgTotal}` | Lease Term Progress Summary |
| `prospects` | `{name, unit, status, agent, entries}`; entries newest first and never removed | Activity Log, Leasing |
| `items` | Parking `{source, list, occupied, total, note}` | Rentable Items Availability |
| `renewals` | `{source, expiring120, firstEnd, byEnd, rows, note}` | Expiring Leases + Rent Roll |
| `arrears` | `{source, owing, due, dueLabel, former, formerCount, detail, note}` | Resident Aged Receivables |
| `rent` | Rent in place, averages, loss to lease, committed, full budget | Rent Roll + Availability |
| `concessions` | `{source, units: [{unit, plan, term, total}], total, note}` | Concessions |
| `budget` | `{source, period, lines, noi, annualNoi, noiMonths, noiTrend, note}`. Closed months are the period on the Budget vs Actual header and earlier. | Income Statement Budget vs Actual + Trailing 12 |
| `workOrders` | `{ref, unit, problem, status, created, due, age, vendor, notes}`. Open orders only (completed are dropped). Vendor exactly as Entrata reports it. | Work Order Details, current and prior year |
| `history` | `{date, leads, apps, leased, inProgress, holds, available, parking, wo, owing, tours}`; `holds` = `counts.applications`. Built by `parsers.figures` (`snapshot`). | Built by the run |
| `waiting` / `working` | Open items | Command Center |
| `toursBooked` | `{name, tour, tent}` | Command Center, Tours booked rule |
| `package`, `missing` | For KEILTY only; not shown on the page | Built by the run |
| `checks`, `toCapture` | Always `[]` | |

### Rules that must not be lost

The full wording is in `daily-job-rules.md`.

- **Leased:** Deposit Held > 0 or a negative balance. Otherwise "in progress". "Application" means rented in Availability but not on the Rent Roll.
- **Arrears:**
  - "owing" is 31+ days, current residents only.
  - "due" is 0 to 30 days.
  - Former residents are shown separately.
  - **Never show prepayments or credits.**
- **Concessions:** one total per lease, rent and parking together.
- **New leads** = Guest Card Completed.
- **Expiring Leases** lists the next four months.
- **Amounts are as the export shows them.** Do not adjust a figure because a later report would differ (for example arrears `due` is the export's figure at its own time).
- **Tours booked ahead:** exactly the Command Center's Tours booked rule. That means open items with a tour date of today or later, sorted by date then time.
- **Open items:**
  - Client items go to `waiting`; KEILTY items go to `working`.
  - Drop prospects, tours, work orders and Leasing fyi items.
  - Respect `clientView` and `clientNote` if present.
- **Writing for the owner:**
  - No report or system names, run times, data problems or prepayments.
  - No credit scores, incomes, personal circumstances, legal file numbers, codes, phone numbers or emails.
  - Anything worth checking goes in my summary.

---

## 6. Checks before every save

1. The feed is valid and the page renders both properties and the overview with no `NaN` or `undefined`.
2. Grove `stack` has 82 suites and F47 has 19, and their status counts match `counts`.
3. `arrears.owing` equals the sum of current residents' overdue columns, and there are no prepayments or credits.
4. `concessions.total` equals the sum of its rows.
5. The history snapshot date is `dataThrough`.
6. `weeks` and `planBeds` are unchanged from the day before.
7. No client-facing text contains "Rent Roll", "Activity Log", "Command Center", "package", "report total" or "prepay".

---

## 7. What to send back to me

- How the Command Center routine works, and confirmation this one follows it.
- The repository layout.
- The connectors and environment settings the routine needs.
- The result of the first **Run now**.
- Anything in `daily-job-rules.md` you couldn't do, and what you did instead.
