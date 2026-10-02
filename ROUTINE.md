# ROUTINE.md: the Cityflats Dashboard daily run

The routine's instructions are one line: "Follow ROUTINE.md in this repository exactly; this run is unattended." Change the run by changing this file.

This run is unattended. Never stop to ask a question. If something cannot be done, say so in the summary and carry on with the rest. Dates are always YYYY-MM-DD. Canadian spelling. No em dashes in anything the client sees. Never write to the Command Center. Never publish or edit the dashboard page: `index.html` in this repository is a copy of the live page (synced when the page is republished from a chat), used only by the render check.

Read `README-for-Claude-Code.md` and `daily-job-rules.md` first. They define what each figure means and the writing rules. This file says what to run, in what order.

## 0. Set up

1. `pip install -r requirements.txt` (pdfplumber for the layout tests, playwright for the render check). The browser is already installed; never run `playwright install`.
2. Today is the run date. `dataThrough` is yesterday. Work in `work/YYYY-MM-DD/` (git-ignored; it holds resident names).

## 1. Get today's Entrata Excel files

1. Search Brandon's Outlook for mail from system@entrata.com with a subject starting "Entrata Reports - Command Center Reports", received today. Take every package: The Grove, Faculty47, Main, KEILTY, Podium and any other. Where a report appears in several packages, the property's own package comes first; the others only fill gaps.
2. For each email, read it, then read each `.xlsx` attachment with `read_resource`. Write the text **exactly as returned** to `work/YYYY-MM-DD/<n>.txt`, one file per attachment. If the tool saved a large result to a file, copy that file. Do not edit, tidy or summarise it.
3. Ignore the PDFs. The connector returns PDFs flattened (cells joined, empty cells dropped), which cannot be read reliably.
4. A report with no Excel attachment in any of today's packages is **missing**. Keep its last figures and add a `missing` flag. Last resort only: if its figures matter today, read the PDF text by hand, put them in, add a `fix` flag saying "read from PDF text, check it", and say so in the summary. Never present older figures as current.
5. If there is no Entrata Excel at all, leave every Entrata figure as it was, still do section 3 (Command Center), save, and push a notification saying no Excel arrived.

## 2. Run the parsers

```
python -m parsers.figures work/YYYY-MM-DD grove --data-through YYYY-MM-DD --previous work/YYYY-MM-DD/previous.json > work/YYYY-MM-DD/grove.json
python -m parsers.figures work/YYYY-MM-DD f47   --data-through YYYY-MM-DD --previous work/YYYY-MM-DD/previous.json > work/YYYY-MM-DD/f47.json
```

`previous.json` is the feed read in section 4, step 1, so read the current `dash/feed` before running these. Every number comes from these two files. Do not read figures off the spreadsheets by eye, and do not type a figure from memory.

Each file lists:
- `missing`: reports with no sheet for the property. Handle as in section 1, step 4.
- `unreadable`: a sheet was there but a parser could not read it. **Carry on with the other reports.** For that report keep its last figures, add a `fix` flag naming it and why, and describe it in the summary.
- `warnings`: pass every one on in the summary. Five reports (Availability, Lease Term Progress, Activity Log, Rentable Items, Expiring Leases) have Excel layouts that have not yet been checked against a real export. Until that changes, say so each day and compare the figures with the PDF text where it is easy to.
- `renewedSuites`: suites with a renewal; they are already left off `increases` (check 13 fails the feed if one is on the list). `increasesChange` (needs `--previous`): the suites added to or dropped from the rent increases list since the feed already saved. `increasesBasis` is present only on a morning that list changes: then say which suites were added or dropped and include the basis line (the lease start is used for every lease because a rent change during a lease cannot be read). On every other morning say nothing about it, to keep the summary short. `leaseStartToConfirm`: list each suite in the summary as "lease start to confirm" while it is on `LEASE_START_TO_CONFIRM` in `parsers/derive.py` (empty now; remove a suite from it once Brandon confirms the date in Entrata).
- `notCarried`: fields the page can show but the reports do not carry yet (`leadsWeek`, `funnel.since`, and `items.income` while the Rent Roll has no parking charge codes). Leave them out of the feed, never estimate them, and do not repeat them in the summary. When a report starts carrying one, `parsers/derive.py` is where it gets added.
- `budgetStatus` (needs `--previous`): `keep` means the report's month is the same as the feed's and nothing changed, so leave the budget section exactly as it is. `restated` lists closed months whose figures changed. `behind` means the report's month is earlier than the feed's: keep the feed's figures and say so in the summary.
- `budget.unknownHeadings`: income statement headings the label table in `parsers/derive.py` does not know. List them in the summary; do not invent a label.

Rulings built into the parsers are in `daily-job-rules.md` ("How the figures are read"). Expiring Leases that says "returned no data" means zero expiring leases. Its flag stays until a run actually has rows: say in the summary every day that its row layout is still untested, and the first time it has rows, say so and check them against the report.

## 3. Command Center, read only

1. Read the Command Center artifact (https://claude.ai/artifact/ErKdkkfCb4PMfw4uwSchLW) with the Artifact tool. It saves the full page to a file; note the path.
2. With ArtifactData, `get` `board/newitems` and `board/edits` with `out_dir` set to `work/YYYY-MM-DD/cc`.
3. `python tools/command_center.py <saved page path> work/YYYY-MM-DD/cc/board/newitems.json work/YYYY-MM-DD/cc/board/edits.json --today YYYY-MM-DD > work/YYYY-MM-DD/cc.json`
4. It returns, per property, `waiting` (client items), `working` (KEILTY items) and `toursBooked`. It applies the rules in STEP 3 of `daily-job-rules.md`: open means `open` or `progress` with no `mergedInto`; tours, prospects, work orders and Leasing fyi items are dropped; only an explicit `clientView: false` hides an item.
5. Write the wording yourself under the writing rules: `what` is one short plain sentence for the owner, `last` is the newest dated line of the notes as "YYYY-MM-DD: gist" or "Raised YYYY-MM-DD." Use `clientNote` as written when present. No credit scores, incomes, personal circumstances, legal file numbers, codes, phone numbers or emails. `toursBooked` is replaced completely each run; if none, `[]`.
6. Note which items and tours were added or dropped since yesterday's feed, for the summary.

## 4. Build the feed

Start from the current `dash/feed`: `ArtifactData get` on https://claude.ai/artifact/JLRG3EwBZa3G1576ZJ8xxy, collection `dash`, document `feed`. Keep its `version`. Parse its `json` field. Save a copy as `work/YYYY-MM-DD/previous.json`.

Top level: `asAt` = today, `dataThrough` = yesterday, `generated` = a new timestamp (the page redraws when it changes), `rentRollAsOf` = the rent roll's data-as-of date.

For each property, replace these from its parser file, keeping the structure and keys:

| Feed key | From |
|---|---|
| `counts`, `stack`, `deals`, `rent` | `counts`, `stack`, `deals`, `rent`. Grove (lease-up) and Faculty47 (stabilised) get different rent keys; use what the parser gives. `counts.toursToday` is yesterday's tour count. |
| `inventory.units`, `inventory.unleasedMonthly` | `inventory` |
| `renewals`, `increases` | `renewals`: `mtm` (month-to-month leases, 0 if none), `expiring120` (the Expiring Leases count), `firstEnd`, and `byEnd` as `[date, count]` pairs for the next 12 months only. Rows from Expiring Leases when it has any. Write `note` under the writing rules. `increases`: the list from the parser, one row per lease as `{num, rent, earliest, noticeBy}` (there is no new rent); `[]` when none. |
| `arrears` | `arrears`: `owing`, `due`, `former`, `formerCount`, and `detail` rows (only rows with a balance owing). Never show credits or prepayments. Write each status and comment yourself: "Current resident, October rent", "Current resident (renewed), October rent", "Former resident, with collections" (or "Former resident" when not in collections). The page finds collections by that word. Never write legal steps or file numbers (no "eviction", "LTB", "N4", hearings) and do not copy Entrata's status text. Write `note`. |
| `funnel` | `funnel`: `stages`, `total`, `avgTotal` |
| `concessions` | `concessions`: `units`, `total`. Write `note`. |
| `items` | `items`: `list`, `occupied`, `total`. Write `note` with the rates. |
| `budget` | Use only the post month the income statements report (they are set to the prior post month); never compute or show a partial current month. If `budgetStatus.keep` is true, leave the whole budget section as it is. Otherwise take `lines`, `noi`, `annualNoi`, `noiMonths`, `noiTrend` and `period` from the parser. If `budgetStatus.restated` lists months, update them and write "restated" in `note` (say which months and what moved), and again in the summary. Write `note` under the writing rules. |
| `workOrders` | `workOrders` (open orders only). Per order: `ref`, `unit`, `status`, `created`, `due`, `age` = `days_open`, `vendor` exactly as reported. Write a short `problem` for the owner from `problem` and `description`. Keep each order's earlier `notes` from the previous feed and add today's note first if it changed. Never copy caller names, phone numbers, emails or door and lockbox codes. An order that disappeared is closed: drop it and mention it in the summary. |
| `history` | Append `snapshot` (dated `dataThrough`). If that date is already there, replace only that entry. Never change earlier entries. A `null` field stays null. |
| `prospects`, `toursDate` | From `activity.entries` (already de-duplicated). For each entry find the prospect by name (add if new) and add `[date time, type, short cleaned note]` at the top of `entries`, skipping any already present (same name, date and time, type). Update `status`, `unit`, `agent`. Remove a prospect once the lease is approved or the guest card or application is cancelled or archived. `toursDate` = `activity.date`. |
| `waiting`, `working`, `toursBooked` | `cc.json`, section 3 |
| `package` | `received` = today; `reports` = the reports used, with the package each came from |
| `missing` | The three `team` entries stay. Add a `missing` entry (with `sec`) for each report in `missing`, and a `fix` entry for each `unreadable` report or other new problem. Remove an entry the day its problem clears. |

Carry forward unchanged: `weeks`, `missedWeeks`, `planBeds`, `inventory.plans`, `inventory.askingAvg`, `weeklyChecklist`, `checks` (`[]`), `toCapture` (`[]`), and every fixed fact.

A report that is missing or unreadable keeps the last values for its keys. Never leave a key empty or invent a figure.

Client wording follows the writing rules in `daily-job-rules.md`: short, plain, factual; no resident names in any note (refer to the suite: "Suite 302 has already renewed"), because names belong only in the arrears table and the prospects list; no report or system names, run times, data problems, prepayments or credits; leave a note `""` when the owner needs nothing.

Write the finished feed to `work/YYYY-MM-DD/feed.json`.

## 5. Checks

```
python tools/check_feed.py work/YYYY-MM-DD/feed.json work/YYYY-MM-DD/previous.json --figures work/YYYY-MM-DD/grove.json --figures work/YYYY-MM-DD/f47.json
python tools/render_check.py work/YYYY-MM-DD/feed.json
```

These are the checks in README section 6. If either fails, **stop, change nothing, and say why**: push a notification with the first failures. This is the only reason to stop. A single unreadable report is not a stop (section 2).

## 6. Save

1. `ArtifactData set` on the dashboard URL, collection `dash`, document `feed`, with `if_version` = the version read in section 4. Data: `json` (the whole feed as JSON text), `asAt`, `dataThrough`, `generated`. Use `file_path` to send it. Do not republish the page.
2. If the write is refused for a version change, re-read, rebuild from the new version and write again.
3. If the write needs approval or fails for any other reason, do not work around it: push a notification.
4. Copy the feed to `feeds/YYYY-MM-DD.json` in the repository and commit only that file with a short message. Push it **straight to `main`**: `git pull --rebase origin main`, then `git push origin HEAD:main`. No branch and no pull request. If the push is refused, say so in the summary and send a notification; do not push anywhere else.

## 7. Summary and notification

Finish with a short summary:
- figures as of close of business yesterday and what changed: new leads, leased, in progress, available, anything overdue and who owes it, tours held, new prospects, new or closed work orders, price changes, renewals or expiring leases, concessions, restated income figures
- open items and booked tours added or dropped
- every `missing`, `fix` and `warnings` entry, and which reports came from which package
- rent increases: only on a morning the list changes, the suites added or dropped plus `increasesBasis`; always any `leaseStartToConfirm` suites ("lease start to confirm")
- anything worth checking in Entrata (a future resident whose move-in date has passed, reports that disagree, totals that do not add up)

Push a notification (PushNotification, message inside `<routine_summary>` tags) when: the run could not save or could not push the feed file to `main`, a check failed, no Excel arrived, any report is missing or unreadable, a `warnings` entry appears for the first time, or something in Entrata needs Brandon. Lead with the one thing that matters. A clean run sends no notification.

After the first save that uses the parsers, and on any run that changed how the feed is built, tell Brandon that a parser-built `dash/feed` is saved so he can render-check it against the published page.
