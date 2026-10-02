# Report parsers

One module per Entrata report. `parse(path)` returns numbers and rows read from the PDF; `derive.py` applies the rules in `daily-job-rules.md`; `registry.load(folder)` reads a whole folder and lists any report that is missing.

```
pip install -r requirements.txt
python -m parsers.figures fixtures/<folder> grove --data-through 2026-09-30   # every figure for one property, as JSON
python -m unittest discover -s tests -v          # needs fixtures/ (git-ignored)
python -m parsers.compare fixtures/<folder> grove --feed feeds/2026-10-02.json
python -m parsers.diff_report > DIFFERENCES.md
```

| Report | Module | How rows are read |
|---|---|---|
| Rent Roll | `rent_roll` | text flow, one regex per row type |
| Availability | `availability` | text flow, grouped by status heading, checked against "(Results: n)" |
| Resident Aged Receivables | `receivables` | word positions (names, status and notes wrap around the numbers) |
| Work Order Details | `work_orders` | text flow for fields, character positions for the vendor column |
| Activity Log - Leasing | `activity_log` | word positions; `dedupe()` keeps one per name, date and time, and type |
| Lease Term Progress Summary | `lease_term_progress` | text flow |
| Concessions | `concessions` | text flow |
| Rentable Items Availability | `rentable_items` | text flow |
| Expiring Leases | `expiring_leases` | empty case only (see DIFFERENCES.md) |
| Income Statement, Budget vs Actual | `income_budget` | text flow |
| Income Statement, Trailing 12 | `income_t12` | text flow |

A report that is not in a folder comes back as `None` and is listed in `missing`; nothing is guessed. Work Order Details files are read one by one (current year, prior year) and joined with `work_orders.combine`, which drops repeats by reference number.

The parsers raise an error on a row they can't read (for example a receivables row without seven amounts) rather than skip it.
