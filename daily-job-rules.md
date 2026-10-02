# Daily job rules (copy of the Claude app scheduled task, as at 2026-10-02)

This is the exact instruction set the current 6:00 a.m. Claude app task follows. The GitHub job must produce the same result. Where it says "Artifact tool" or "ArtifactData", use whatever the Command Center's GitHub job uses to read and publish claude.ai artifacts.

---

Update the Cityflats Dashboard for Brandon Ackerman (KEILTY Realty Management Inc.). This runs automatically every morning at 6:00; Brandon can also start it by hand. Dates are always YYYY-MM-DD. Canadian spelling, no em dashes. The goal is that every figure comes from Entrata. Only three things come from the team on the Command Center: client items (awaiting your input), what we are working on (open KEILTY items), and tours booked ahead (the Command Center's "Tours booked" section).

## HOW THE FIGURES ARE READ (added 2026-10-03)

- **Every figure comes from the parsers** in `parsers/` (see "How to run the parsers" in README-for-Claude-Code.md). Do not read figures off the PDFs by eye. Your own judgement is for client wording and the Command Center items only.
- Where the older text below says "read" or "write" a figure, it means: take it from `python -m parsers.figures`. The rules below still define what each figure means.
- **Rulings that apply to the parsers:**
  - `deals`: Grove lists only leases in progress; Faculty47 lists every future resident (leased or in progress).
  - `inventory.units`: "available on" is the report's date for every suite.
  - Vendor names are written exactly as Entrata reports them.
  - Open work orders only; completed orders are dropped.
  - `holds` on the history snapshot = `counts.applications`.
  - Financials: only the post month the income statements report, read from the Budget vs Actual header; never a partial current month. Unchanged month: keep. Changed closed month: update it and say "restated" in `budget.note` and the summary.
  - Amounts are as the export shows them; do not adjust for what a later report would say.
  - A report missing from the package (for example Faculty47 Concessions on a day it is left out) keeps its last figures and is flagged, never filled in.
  - The first time Expiring Leases has rows, say so in the summary, because that layout has not been checked against a real report.
- **Input is Excel.** The connector returns an `.xlsx` attachment as clean tab-separated text; PDFs come back flattened and are not parsed. The step-by-step run is in `ROUTINE.md`.
  - A report with no Excel in any of today's packages is missing: keep its last figures and flag it.
  - A sheet the parser cannot read: keep that report's last figures, raise a `fix` flag, describe it in the summary, and carry on with the rest. Only a failed whole-feed check stops the run.
  - Expiring Leases that says "returned no data" means zero expiring leases.
  - `inventory.plans`, `inventory.askingAvg` and `weeklyChecklist` are carried forward unchanged.

## THE DASHBOARD

- **Where it lives:** https://claude.ai/artifact/JLRG3EwBZa3G1576ZJ8xxy (title "Cityflats Dashboard").
  - The page (index.html) never changes in a normal run.
  - All figures live in its supporting file data.js (window.CLIENT_FEED = {...}).
- **How to update it:**
  - First read the artifact, then read its "data.js".
  - Edit a local copy of data.js and republish with the artifact URL, the saved index.html as the page, and files {"data.js": <your edited data.js>}.
  - Keep the same structure and keys; only change values.
  - If data for a key is unavailable, keep the structure and add an entry to that property's "missing" list rather than inventing a figure.
- **The two properties:**
  - "grove": The Cedar at the Grove, 1245 Centennial Drive, Centennial Land Development LP. Lease-up, 82 suites, 81 rentable plus model suite 103, target full 2027-03-01.
  - "f47": Faculty47, 47 Wellington Street, Faculty 47 Development LP. 17 suites let as 19 rentable units, because 301 is let as 301A/301B/301C.
- **Dates:** the Entrata reports run at about 1:00 a.m., so every figure is as of CLOSE OF BUSINESS YESTERDAY. Set top-level "asAt" to today (the run date) and "dataThrough" to yesterday.
- **Charts and history:** the page draws the trend charts, weekly history, lease-up curve, tours this week and week-on-week changes by itself, from "weeks" (the team's weekly updates, history up to 2026-09-30 only) and "history" (daily Entrata snapshots). Do not hand-build trend figures and never edit "weeks".
- **Client view only:** the page shows no working notes, verification lists, source pills or source map. Keep each property's "checks" list empty; put anything worth checking in the summary to Brandon instead.
- **planBeds:** if a property has "planBeds" (floor plan name -> bedrooms, set by Brandon), never change or remove it.

### WRITING RULES

These apply to every "note" and every sentence written into data.js: arrears.note, concessions.note, items.note, renewals.note, rent.note, budget.note, work order notes and open items.

- Write for the owner: plain, short and factual.
- No resident names in any note or sentence. Names belong only in the arrears table and the prospects list. Refer to a suite instead ("Suite 302 has already renewed").
- Do not name reports or systems ("Rent Roll", "Expiring Leases report", "Activity Log", "package", "Command Center").
- Do not give report run times.
- Do not mention data problems, mismatches, report totals that do not add up, or figures still to be confirmed. Send those to Brandon in the summary.
- Never mention prepayments, credits or residents who paid ahead.
- Leave a note "" when there is nothing an owner needs.

Examples:

- renewals.note: "No leases expire in the next four months. Eight leases end 2027-04-28."
- items.note: "Listed at $125 a month."
- concessions.note: "Totals per lease, rent and parking concessions together."
- arrears.note: "Nothing is owed."

## STEP 1: GET TODAY'S ENTRATA REPORTS

- **Where they come from:** Entrata emails Brandon's inbox at about 3:00 a.m. from system@entrata.com. Search for "Entrata Reports - Command Center Reports" and take EVERY email received today, not just the Cityflats one.
- **Packages:** there are several, for example "Command Center Reports - Cityflats", "Command Center Reports - Main", and possibly per-property packages for The Grove or Faculty47. Any expected report may arrive in any of them; Work Order Details, Availability and Rentable Items Availability, for example, come in the Main package.
- **Reading them:**
  - Each email carries PDF attachments.
  - Portfolio-wide reports group rows under "Property: <name>" or list several properties in the header. Keep only the rows for "The Cedar at the Grove" and "Faculty47".
  - Read Work Order Details by word position (for example pdfplumber), because its rows wrap.
- **Duplicates across packages:**
  - If the same report comes in more than one package, use the copy that covers the property most specifically (a Cityflats or per-property package before Main). Use the other only to fill gaps.
  - A report counts as received if it is in ANY of today's packages; only flag it missing if it is in none of them.
- **Expected reports for each property:**
  - Activity Log - Leasing
  - Availability
  - Concessions
  - Expiring Leases
  - Income Statement - Budget vs Actual
  - Income Statement - Trailing 12
  - Lease Term Progress Summary
  - Rent Roll
  - Rentable Items Availability
  - Resident Aged Receivables
  - Work Order Details (current year, and prior year where it exists)
- **A report found in none of today's packages:** keep its last figures, add a "missing" entry naming it and the property, and list it in the summary. Never present older figures as current.
- **No Entrata email at all today:** do not change the Entrata figures. Still do STEP 3 (Command Center) and publish that, and say in the summary that today's Entrata emails were not found.

## STEP 2: WHAT EACH ENTRATA REPORT FEEDS (keys in data.js)

### Availability

- Per-suite status, floor plan, sq ft, budgeted rent and Available On date feed:
  - inventory.units (every suite as [suite, plan, sqft, budgeted rent, available on, status])
  - inventory.unleasedMonthly (budgeted rent of available suites)
  - counts.available
  - counts.applications (suite shown rented but nobody on the Rent Roll)
  - stack
  - delivery dates (Grove)
- If the report ever carries a bedrooms column, report it in the summary so Brandon can confirm planBeds.

### Rent Roll (Current Post Month)

- Current residents, future residents with rent, deposit held, balance, move-in and lease end feed:
  - counts.occupied / counts.leased / counts.inProgress
  - stack
  - deals
  - rent.*
  - renewals.byEnd: [date, count] pairs for lease ends in the next 12 months only (current and future residents)
  - increases: one row per lease, {num, rent, earliest, noticeBy}; no new rent (the dashboard shows when an increase is due, not the amount). earliest = lease start + 12 months; noticeBy = earliest minus 90 days; only rows whose noticeBy is by the run date + 6 months, notices already due included. Suites with a renewal are left off: "Renewed" on the receivables report means a renewal lease is signed for the next term and sets the new rent, and so does a future lease on a suite that has a current resident. The rent last changed on the Rent Roll lease start; Availability dates and notes are never a source for lease dates. A rent change during a lease (a later rent line in Scheduled Charges) would be measured from that change, and a renewed lease from the renewal's start; neither can be read from the Rent Roll columns we receive, so the lease start is used and the summary says so.
- Status rules:
  - occupied = current resident
  - leased (Grove) or "Leased, moving in" (F47) = future resident with last month's rent received (Deposit Held > 0, or a negative Balance / Pre-Payment)
  - progress = future resident without it
  - applied = suite rented in Availability but not on the Rent Roll
  - available
  - model

### Expiring Leases

- Its header shows the current month, but it lists leases expiring over the next four months.
- Write:
  - renewals.expiring120 (number of leases on the report)
  - renewals.source "Expiring Leases"
  - renewals.note
  - renewals.rows, one per lease, as {unit, end, status, rent} (no new rent: the dashboard shows when, not how much)
- Note any resident whose Lease Status on the receivables report reads "Renewed".

### Resident Aged Receivables (arrears)

- owing = current residents' balances in the 31-60, 61-90 and 90+ columns (overdue).
- due and dueLabel = current residents' 0-30 day balances (this month's charges not yet paid, e.g. "October charges not yet paid"). On the first days of the month this is normal and not late.
- former and formerCount = past residents' positive balances.
- detail = ONLY rows with a balance owing, as [suite (or "Parking" if no suite), resident, status in plain words, 0-30, 31-60, 61-90, 90+, balance, comment].
  - Status examples: "Current resident, October rent", "Current resident (renewed), October rent", "Former resident, with collections", "Former resident, eviction file, with collections".
  - Comment = Last Delinquency Note shortened to its date and gist, or "".
- note in a sentence.
- Status wording: the page finds former residents in collections by the word "collections" in the status, so write "Former resident, with collections" (or "Former resident" when not in collections). Never write legal steps or file numbers in any status, comment or note: no "eviction", "LTB", "N4", hearings or file numbers. Do not copy Entrata's status text.
- Do not show pre-payments or credits anywhere.

### Lease Term Progress Summary

- Feeds funnel.stages counts and average time in status.
- NEW LEADS = the "Guest Card Completed" count. Store it as "leads" on the day's history snapshot.

### Activity Log - Leasing

- Set to YESTERDAY; activity types Notes and Tour. Feeds prospects.
- Build on what is already there; never remove older entries.
- The report often repeats the same entry two or three times; count each once.
- For each entry:
  - Find the prospect by name (add if new).
  - Add [date and time, activity type, short cleaned note] at the top of their "entries", skipping any entry already present (same name, date and time, activity type).
  - Update "status", "unit" and "agent".
- Remove a prospect once Entrata shows the lease approved, or the guest card or application cancelled or archived.
- Set toursDate to yesterday and counts.toursToday to the number of Tour entries. Store it as "tours" on the day's history snapshot.

### Rentable Items Availability

- Feeds items: list of [stall with type, Occupied/Reserved/Available, suite number], occupied = occupied plus reserved, total, and a note with rates.

### Concessions

- concessions.units = ONE row per lease, {unit, plan, term, total}, where total = recurring plus one-time for that lease, rent and parking together.
- The report names the resident, not the parking stall, so do not split by stall.
- concessions.total = sum, excluding cancelled leases.
- If the report returns no concessions for a property, set units to [] and total 0, and say so in the summary.

### Income Statement Budget vs Actual and Trailing 12

- Feed budget.lines, budget.noi (month actual, month budget, YTD actual, YTD budget), annualNoi, noiMonths and noiTrend.
- Use only the post month the income statements report (they are set to the prior post month). Never compute or show a partial current month: the Trailing 12 sheet's current-month column is ignored.
- If the report's month has not changed since the last run and nothing in it changed, keep the budget section exactly as it is.
- If a closed month's figures change (the same month re-run, or an earlier month in the trend now reads differently), update them and say "restated" in budget.note and in the summary.
- If the report's month is earlier than the feed's, keep the feed's figures and flag it for the summary.

### Work Order Details

- Combine every Work Order Details report found for the property (current year and prior year, from whichever package carries them) and drop duplicates by reference number.
- Write every open order to workOrders as {ref, unit, problem (short, from Problem and Description), status, created, due, age (Days Open), vendor (Assigned Vendor), notes: [[report date, Internal Note shortened and cleaned]]}, with earlier notes kept below.
- Never copy caller names, phone numbers, emails, door or lockbox codes.
- If an order disappears from all of them it is closed; drop it and mention it in the summary.

## STEP 3: COMMAND CENTER: OPEN ITEMS AND TOURS BOOKED (every run, even with no Entrata email)

Command Center: https://claude.ai/artifact/ErKdkkfCb4PMfw4uwSchLW. **Read only; never write to the Command Center.**

### A. Build the full item list

Read from THREE places, in this order, with later ones winning:

1. **The items built into the Command Center page.** Read the page's index.html. The page holds a JSON array after the key "items":, whose objects carry "id", "clientId", "owner", "area", "type", "kind", "status", "title", "notes", "raised", "disc", "due", "who", "unit", "tour", "tourTime", "tourTent". Parse that array.
2. **Its database, collection "board", doc "newitems".** Its "body" is a list of items added on the board, including every tour the team submits on its update form (kind "Tour").
3. **Collection "board", doc "edits".** Its "body" is {item id: changed fields}. Merge each into the matching item (status, title, notes, owner, area, tour, tourTime, tourTent, disc, due, closedDate, closedReason, mergedInto and so on).

An item is OPEN when its status is "open" or "progress" and it has no mergedInto. "closed" and "retired" are not open.

### B. Tours booked ahead

- This is exactly what the Command Center's "Tours booked" section shows for that client. The section is drawn from the same items using this rule, so apply the same rule:
  - clientId cCEN (grove) or cF47 (f47)
  - item OPEN
  - a "tour" date of today or later
  - sorted by tour date, then tourTime
- Write to toursBooked as [{name, tour, tent}]:
  - name: who, or the title before ", tour booked" if who is empty
  - tour: "YYYY-MM-DD HH:MM", or the date only if there is no time
  - tent: true when tourTent is true (date still to be confirmed)
- Replace the list completely every run; if none, [].
- Do not take tours from anywhere else. The Activity Log only shows tours already held.
- The team submits upcoming tours on Tuesday, so Wednesday morning's run is when the new week's tours appear.

### C. Open items

Keep an item only when ALL of these hold:

- clientId is "cCEN" (grove) or "cF47" (f47), and the item is OPEN.
- It is not a tour and not something Entrata already reports. Drop:
  - items with kind "Tour"
  - items whose id starts with "p" (prospects)
  - items with kind "Work order" or a title starting "WO "
  - items with type "fyi" in Leasing
  - any item that is only a leasing prospect, tour, work order, arrears, renewal or concession record

  Keep leasing DECISIONS and ACTIONS, such as "Provide new pricing for the Grove".
- If the item has a "clientView" field, keep it only when clientView is true. If it has "clientNote", use that wording as written.

Write them, replacing each property's lists completely every run so closed items drop off:

- **owner "Client" -> "waiting":** {area, what, since, last}.
  - what = the title rewritten as one short, plain sentence for the owner. For example, "Jack to provide feedback on billboards and other display ads" becomes "Feedback on the billboards and other display ads."
  - since = raised.
  - last = the newest dated line of the notes as "YYYY-MM-DD: gist", or "Raised YYYY-MM-DD." if there are no notes.
  - Sort oldest first.
- **owner "KEILTY" -> "working":** {area, what, since, notes: [[date, short note], ...]}, newest note first, up to three.
- **Clean everything for a client audience:**
  - no credit scores, income amounts, personal or family circumstances, legal file numbers, access or lockbox codes, phone numbers or emails
  - no blaming wording
  - keep first names of the client's own people (e.g. Jack, Ian) only where the title already uses them

### D. Summary

In the summary, list open items and booked tours that were added or dropped since yesterday.

## STEP 3B: HISTORY

- Each property has a "history" list of daily Entrata snapshots: {date, leads, apps (Lease Term Progress application stages, started through approved, added up), leased, inProgress, holds, available, parking (occupied plus reserved stalls), wo (open work orders), owing (overdue only), tours}.
- Append one snapshot per run, dated with dataThrough (yesterday), never with the run date.
- Never change earlier snapshots. If a run repeats a date, replace only that date's snapshot.
- Leave a field null when its report was not in today's emails.

## STEP 4: FLAGS (kept in data.js for KEILTY only; the page does not show them)

- Each property's "missing" list holds {sec, level, what, need}. Levels:
  - "team": the three Command Center items, always present
  - "fix": a new problem found in today's reports
  - "missing": a report found in none of today's packages. Use sec "conc" for Concessions, "ren" for Expiring Leases, "wo" for work orders, "arr" for receivables, "inv" for Availability, "items" for Rentable Items, "leads" for Activity Log or Lease Term Progress, and "fin" for income statements.
- Remove a "fix" or "missing" entry as soon as the problem clears.
- Keep "weeklyChecklist" current.
- Set package.received to today, and package.reports to the list of reports used, with the package each came from.

## STEP 5: PUBLISH AND REPORT

- Syntax-check data.js before publishing, then publish to the dashboard URL.
- Send Brandon a short summary covering:
  - figures as of close of business yesterday and what changed: new leads, leased, available, anything overdue and who owes it, tours held, new prospects or Activity Log entries, new or closed work orders, price changes, renewals or expiring leases, concessions, restated income figures
  - open items and booked tours added or dropped
  - any missing or fix flag
  - which packages were read, and any report that was in none of them
  - anything worth checking in Entrata, for example a future resident whose move-in date has passed, report totals that do not add up, or reports that disagree
