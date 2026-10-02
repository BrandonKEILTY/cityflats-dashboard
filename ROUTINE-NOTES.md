# Routine notes

The run steps are in `ROUTINE.md`. This file keeps the facts it relies on.

- The page (template 2026-10-02.14 on) reads `feed.json` from its own site first, then `dash/feed` (field `json`, the whole feed as JSON text) inside Claude. Set `generated` to a new timestamp on every save so the page redraws.
- Cloudflare (pilot, from 2026-10-02): R2 bucket `keilty-dashboards`, folder `cityflats/` (`feed.json`, `history/<dataThrough>.json`, both the `{asAt, dataThrough, generated, json}` wrapper); Pages project `cityflats-dashboard`, branch `main`; Access one-time PIN on `cityflats-dashboard.pages.dev` and `*.cityflats-dashboard.pages.dev`, emails ending @keilty.com. The token needs Pages Edit and Workers R2 Storage Edit. First R2 load and deploy: 2026-10-02, figures through 2026-10-01.
- Two-week overlap from 2026-10-02: the routine still writes `dash/feed` as a backup. After two clean weeks Brandon retires the artifact and the `dash/feed` steps come out of ROUTINE.md.
- Connectors: Microsoft 365 only. The Artifact tools read the Command Center and read and write `dash/feed`.
- Setup script: `pip install -r requirements.txt` (pdfplumber for the PDF layout tests, playwright for the render check; the browser is already installed).
- The connector returns an `.xlsx` attachment as clean tab-separated text (empty cells kept, dates as Excel serial numbers) and flattens PDFs. The parsers read the Excel text. Entrata is being switched to send Excel with the Command Center Reports for The Grove and Faculty47.
- Command Center items: page `"items":` array, then `board/newitems`, then `board/edits`. Open = status open/progress, no mergedInto. Only `clientView: false` hides an item. `tools/command_center.py` does this.
- Availability has no bedrooms column; `planBeds` is supplied by Brandon. `inventory.plans`, `inventory.askingAvg` and `weeklyChecklist` are carried forward unchanged.
- Notice of Rent Increase is not used by this feed.
- Test data with resident names lives in `fixtures/` and `work/` (both git-ignored). Do not commit it.
- The routine is "Cityflats Dashboard, daily update" at 6:07 a.m. in the KEILTY environment (`CLOUDFLARE_API_TOKEN` and `CLOUDFLARE_ACCOUNT_ID` set, network access Full).
- The old 6:00 a.m. desktop task also writes `dash/feed` and stays on as a backup; the routine's later save wins. Brandon turns it off after three clean mornings on the routine (all six summary lines passed).
