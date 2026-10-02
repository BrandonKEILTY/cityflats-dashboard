# Routine notes

The run steps are in `ROUTINE.md`. This file keeps the facts it relies on.

- Dashboard v53 reads `dash/feed`, field `json` (whole feed as JSON text). Set `generated` to a new timestamp on every save so the page redraws.
- Connectors: Microsoft 365 only. The Artifact tools read the Command Center and read and write `dash/feed`.
- Setup script: `pip install -r requirements.txt` (pdfplumber for the PDF layout tests, playwright for the render check; the browser is already installed).
- The connector returns an `.xlsx` attachment as clean tab-separated text (empty cells kept, dates as Excel serial numbers) and flattens PDFs. The parsers read the Excel text. Entrata is being switched to send Excel with the Command Center Reports for The Grove and Faculty47.
- Command Center items: page `"items":` array, then `board/newitems`, then `board/edits`. Open = status open/progress, no mergedInto. Only `clientView: false` hides an item. `tools/command_center.py` does this.
- Availability has no bedrooms column; `planBeds` is supplied by Brandon. `inventory.plans`, `inventory.askingAvg` and `weeklyChecklist` are carried forward unchanged.
- Notice of Rent Increase is not used by this feed.
- Test data with resident names lives in `fixtures/` and `work/` (both git-ignored). Do not commit it.
- The old 6:00 app task also writes `dash/feed`; the routine's later save wins. Brandon turns the old task off after three clean routine runs that use the parsers.
