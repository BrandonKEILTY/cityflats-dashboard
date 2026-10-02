# Report parsers

Input is the text the Outlook connector returns for an Excel (.xlsx) attachment, saved as `.txt` files in one folder. One module per report; `parse(lines)` reads one sheet. `registry.load(folder, "grove"|"f47")` finds each report's sheet by its title and property, reads it, and lists reports that are `missing` (no sheet) or `unreadable` (a sheet a parser could not read). `derive.py` applies the rules in `daily-job-rules.md`; `figures.py` prints everything for one property as JSON; `xlsxtext.py` has the text helpers (sheet splitting, Excel dates, number clean-up, header lookup).

```
python -m parsers.figures work/2026-10-02 grove --data-through 2026-10-01
python -m unittest discover -s tests -v
python tools/render_check.py tests/data/feed-2026-10-02.json     # renders index.html (a copy of the live page) with a feed, both paths
python -m parsers.diff_report > DIFFERENCES.md      # needs the PDF fixtures; see below
```

| Report | Module | Layout checked on real Excel text |
|---|---|---|
| Rent Roll | `rent_roll` | yes |
| Resident Aged Receivables | `receivables` | yes |
| Concessions | `concessions` | yes (the Total cell is blank on lease rows, so recurring + one-time is used) |
| Work Order Details | `work_orders` | yes (cells with line breaks are joined back) |
| Income Statement, Budget vs Actual | `income_budget` | yes |
| Income Statement, Trailing 12 | `income_t12` | yes (no section headings in the sheet; only the NOI row is needed) |
| Availability | `availability` | no, written from the PDF headings |
| Lease Term Progress Summary | `lease_term_progress` | no |
| Activity Log - Leasing | `activity_log` | no (`dedupe()` keeps one per name, date and time, and type) |
| Rentable Items Availability | `rentable_items` | no |
| Expiring Leases | `expiring_leases` | no (and no export with rows exists yet) |

Modules marked "no" have `LAYOUT_CHECKED = False`, so `registry.load` adds a warning every time one is read. Flip the flag after a real export has been compared and a test added.

A parser raises `LayoutError` on something it does not recognise; the registry turns that into `unreadable` rather than stopping the run. Numbers are cleaned of float noise; dates become `YYYY-MM-DD`.

## Tests and data

- `tests/test_xlsx.py`: made-up workbooks in `tests/data/xlsx` (fake names, real layout) plus, when present, the real workbooks in `fixtures/xlsx_text` (git-ignored).
- `tests/test_tools.py`: the feed checks and the Command Center item rules.
- `tests/test_pdf_layout.py`: the old PDF readers in `parsers/pdf`, kept as a layout reference. They need the PDF fixtures (git-ignored) and are not used by the routine. `parsers/compare.py` and `parsers/diff_report.py` still read those PDFs to compare with a feed.
