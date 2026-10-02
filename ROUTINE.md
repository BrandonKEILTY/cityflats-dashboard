# ROUTINE.md: the Cityflats Dashboard daily run

The routine's instructions are one line: "Follow ROUTINE.md in this repository exactly; this run is unattended." Change the run by changing this file.

This run is unattended. Never stop to ask a question. If something cannot be done, say so in the summary and carry on with the rest. Dates are always YYYY-MM-DD. Canadian spelling. No em dashes in anything the client sees. Never write to the Command Center. Never change how the dashboard looks: `index.html` in this repository is the page template (template 2026-10-02.14 on, synced from the live page, built-in figures removed). The run writes figures only: it saves them to R2 and deploys that template with today's figures to Cloudflare Pages (section 6). Never republish the Claude artifact.

Read `README-for-Claude-Code.md` and `daily-job-rules.md` first. They define what each figure means and the writing rules. This file says what to run, in what order.

## 0. Set up

1. `pip install -r requirements.txt` (pdfplumber for the layout tests, playwright for the render check). The browser is already installed; never run `playwright install`.
2. Today is the run date. `dataThrough` is yesterday. Work in `work/YYYY-MM-DD/` (git-ignored; it holds resident names).
3. Cloudflare: the environment carries `CLOUDFLARE_API_TOKEN` and `CLOUDFLARE_ACCOUNT_ID`. Run wrangler as `npx -y wrangler@4` with `CI=1` set, so it never prompts. Every R2 command takes `--remote`. Bucket `keilty-dashboards`, folder `cityflats/`; Pages project `cityflats-dashboard`, branch `main`.

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

`previous.json` is yesterday's feed read from R2 in section 4, so read it before running these. Every number comes from these two files. Do not read figures off the spreadsheets by eye, and do not type a figure from memory.

Each file lists:
- `missing`: reports with no sheet for the property. Handle as in section 1, step 4.
- `unreadable`: a sheet was there but a parser could not read it. **Carry on with the other reports.** For that report keep its last figures, add a `fix` flag naming it and why, and describe it in the summary.
- `warnings`: pass every one on in the summary. Five reports (Availability, Lease Term Progress, Activity Log, Rentable Items, Expiring Leases) have Excel layouts that have not yet been checked against a real export. Until that changes, say so each day and compare the figures with the PDF text where it is easy to.
- `renewedSuites`: suites with a renewal; they are already left off `increases` (check 13 fails the feed if one is on the list). `increasesChange` (needs `--previous`): the suites added to or dropped from the rent increases list since the feed already saved. `increasesBasis` is present only on a morning that list changes: then say which suites were added or dropped and include the basis line (the lease start is used for every lease because a rent change during a lease cannot be read). On every other morning say nothing about it, to keep the summary short. `leaseStartToConfirm`: list each suite in the summary as "lease start to confirm" while it is on `LEASE_START_TO_CONFIRM` in `parsers/derive.py` (empty now; remove a suite from it once Brandon confirms the date in Entrata).
- `notCarried`: fields the page can show but today's reports did not give (`leadsWeek` when no reliable count could be made). Leave them out of the feed and never estimate them. Say so in the summary on the day it applies.
- `leadsWeekMissingDays`: name any day listed there in the summary.
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

Start from yesterday's feed in R2, which is the record:

```
npx -y wrangler@4 r2 object get keilty-dashboards/cityflats/feed.json --file work/YYYY-MM-DD/r2-previous.json --remote
```

It is the `{asAt, dataThrough, generated, json}` wrapper. Parse its `json` field and save the feed as `work/YYYY-MM-DD/previous.json`.

During the two-week overlap (until Brandon retires the Claude artifact), also `ArtifactData get` the current `dash/feed` on https://claude.ai/artifact/JLRG3EwBZa3G1576ZJ8xxy, collection `dash`, document `feed`, and keep its `version` for the backup write in section 6. If its `generated` differs from the R2 copy's, say so in the summary; R2 wins. If the R2 read fails, build from `dash/feed` instead, say so in the summary and send a notification.

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
| `history` | Append `snapshot` (dated `dataThrough`). It carries `newCards` (the day's count of guest cards created, a number and never names) only when the Activity Log gave one. If that date is already there, replace only that entry. Never change earlier entries. A `null` field stays null. |
| `prospects`, `toursDate` | From `activity.entries` (already de-duplicated). For each entry find the prospect by name (add if new) and add `[date time, type, short cleaned note]` at the top of `entries`, skipping any already present (same name, date and time, type). Update `status`, `unit`, `agent`. Remove a prospect once the lease is approved or the guest card or application is cancelled or archived. `toursDate` = `activity.date`. |
| `leadsWeek` | built from the daily Activity Log, never from Lease Term Progress (that report covers last week, Monday to Sunday). Each morning count the distinct names on that day's log with Status "Guest Card : Completed" that were not seen before (not in the saved feed's prospects); the parser stores that count as `newCards` on the day's history snapshot (counts only, no names). `leadsWeek` is the sum of `newCards` from Thursday through `dataThrough` and restarts Thursday. A day with no stored count is listed in `leadsWeekMissingDays`: keep the sum of the days you have and name the missing days in the summary. If the count cannot be made reliably (no saved feed to compare with, no log), leave `leadsWeek` out and say so in the summary: the tile shows a dash. Never fill it with the Lease Term Progress count. |
| `funnel.since`, `funnel.until` | the Lease Term Progress report is set to "last week", weeks starting Monday. The parser works both out from the run date: since = Monday of the previous week, until = the Sunday after (2026-10-02 -> 2026-09-21 and 2026-09-27). The page reads "activity 2026-09-21 to 2026-09-27". Written by the parser; do not change them. |
| `items.income` | parking rent per month, only from a real parking charge on the Rent Roll's Charge Code Summary. Never from stall rates or Rentable Items. Until one appears, leave the field out. Every morning say in the summary: if `parkingCodes` is set, the exact code name(s) and the monthly figure for each property; if not, the codes the summary does show (`chargeCodesSeen`). |
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

A report or summary must never quote the feed's `json` text: it holds resident names.

These are the checks in README section 6. If either fails, **stop, change nothing, and say why**: push a notification with the first failures. This is the only reason to stop. A single unreadable report is not a stop (section 2).

## 6. Save to R2, then deploy

The order matters. Save first; deploy only after the save is confirmed.

1. **Wrap the feed.** `python -m tools.build_site work/YYYY-MM-DD/feed.json work/YYYY-MM-DD/site` writes the exact files to deploy: `site/index.html` (this repository's template with today's figures built in, so the page never opens blank), `site/feed.json` (the `{asAt, dataThrough, generated, json}` wrapper the page reads first) and `site/_headers`. `site/feed.json` is also what goes to R2.
2. **Save to R2:**
   ```
   npx -y wrangler@4 r2 object put keilty-dashboards/cityflats/feed.json --file work/YYYY-MM-DD/site/feed.json --content-type application/json --remote
   npx -y wrangler@4 r2 object put keilty-dashboards/cityflats/history/<dataThrough>.json --file work/YYYY-MM-DD/site/feed.json --content-type application/json --remote
   ```
   Then read `cityflats/feed.json` back (`r2 object get ... --file work/YYYY-MM-DD/r2-check.json --remote`) and `cmp` it with `site/feed.json`. If either write or the read-back fails or differs, retry once. If it still fails, **do not deploy**: skip steps 4 and 5, still do step 6, and send a notification saying the figures were not saved and the page was not updated. Never overwrite an earlier day's history file except the one for today's `dataThrough`.
3. **Render check the exact files:** `python tools/render_check.py --site work/YYYY-MM-DD/site`. It serves the folder as Pages would, opens every view, and fails if the page shows NaN or undefined, has a script error, does not redraw from `feed.json`, or carries figures that differ from `feed.json`. If it fails, do not deploy (the R2 save stands); say why in the summary and send a notification.
4. **Deploy:**
   ```
   npx -y wrangler@4 pages deploy work/YYYY-MM-DD/site --project-name cityflats-dashboard --branch main --commit-dirty=true --commit-message "Cityflats figures <dataThrough>"
   ```
   Deploy only the `site` folder, nothing else. If the deploy fails, retry once. If it still fails, keep the R2 save (never undo it), say in the summary that the figures are saved in R2 but the page still shows the previous day, and send a notification. The next run deploys as normal.
5. **Check the gate.** `curl -sS -o /dev/null -w "%{http_code} %{redirect_url}" https://cityflats-dashboard.pages.dev/feed.json` must be a 302 to `cloudflareaccess.com`. If it returns the file, send a notification at once: the figures are open to anyone.
6. **Backup write during the two-week overlap.** `ArtifactData set` on the dashboard URL, collection `dash`, document `feed`, with `if_version` = the version read in section 4, `file_path` = `work/YYYY-MM-DD/site/feed.json`. Do not republish the artifact. If the write is refused for a version change, re-read and write again; if it needs approval or fails for any other reason, say so in the summary (R2 and the site are the record). Do this even when step 2 failed. Brandon drops this step when the artifact is retired.
7. **No GitHub commits.** Daily figures live in R2 only. Do not commit, push or open a pull request.

## 7. Summary and notification

Finish with a short summary:
- figures as of close of business yesterday and what changed: new leads, leased, in progress, available, anything overdue and who owes it, tours held, new prospects, new or closed work orders, price changes, renewals or expiring leases, concessions, restated income figures
- open items and booked tours added or dropped
- every `missing`, `fix` and `warnings` entry, and which reports came from which package
- rent increases: only on a morning the list changes, the suites added or dropped plus `increasesBasis`; always any `leaseStartToConfirm` suites ("lease start to confirm")
- anything worth checking in Entrata (a future resident whose move-in date has passed, reports that disagree, totals that do not add up)

Push a notification (PushNotification, message inside `<routine_summary>` tags) when: the R2 save failed, the render check on the site failed, the deploy failed, the gate let `feed.json` through, a check failed, no Excel arrived, any report is missing or unreadable, a `warnings` entry appears for the first time, or something in Entrata needs Brandon. Lead with the one thing that matters. A clean run sends no notification.

After the first save that uses the parsers, and on any run that changed how the feed is built, tell Brandon that a parser-built feed is saved and deployed so he can check https://cityflats-dashboard.pages.dev against the Claude artifact.

The summary always opens with three lines, each passed or failed: **R2 save** (with the history file name and that the read-back matched), **deploy** (with the deployment address wrangler printed), **gate check** (the status and where `feed.json` redirected). Then whether the `dash/feed` backup write went through.
