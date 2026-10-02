# Routine notes (2026-10-02)

- Dashboard v53 reads `dash/feed`, field `json` (whole feed as JSON text). Set `generated` to a new timestamp on every save so the page redraws.
- Connectors: Microsoft 365 only. Artifact tools read the Command Center and read/write `dash/feed`.
- Setup script: `pip install -r requirements.txt` (pdfplumber); node for `node --check`.
- Command Center items: page `"items":` array, then `board/newitems`, then `board/edits`. Open = status open/progress, no mergedInto. `clientView` false hides an item; true, null or missing shows it.
- Availability has no bedrooms column; `planBeds` is supplied by Brandon.
- Notice of Rent Increase is not used by this feed.
- Work Order Details wraps rows: read by word position. Activity Log repeats entries: de-duplicate on name, date and time, type.
- Test PDFs (resident names and balances) live in `fixtures/`, which is git-ignored. Do not commit them.
- The old 6:00 app task also writes `dash/feed`; the routine's later save wins. Turn the old task off after the first good routine run.
