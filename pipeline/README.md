# Construction pipeline

These scripts rebuild the published series in [`../data`](../data) from the underlying
vendor data. **The inputs are licensed and are not included in this repository.** To run
the pipeline you need your own access to:

- **S&P Global Market Intelligence** (formerly SNL): the "RE Companies" workbook export
  described below;
- **WRDS**: CRSP CIZ monthly stock file (`crsp.msf_v2`, `crsp.stocknames_v2`) and
  Compustat North America (`comp.fundq`, `comp.funda`).

Keep every intermediate file in a working directory *outside* this repository (the
`.gitignore` also blocks `*.dta`). Only `05_build_indices.py` writes into the repository,
and only the two aggregate CSVs.

## Steps

| Step | Script | Reads (from `--data-dir`) | Writes |
|---|---|---|---|
| 1 | `01_import_spg.py` | S&P Global workbook (`--spg-file`) | `spg_companies.dta`, `spg_fin_qtr.dta`, `spg_fin_ann.dta` |
| 2 | `02_wrds_pull.py` | `spg_companies.dta`; WRDS | `crsp_stocknames.dta`, `crsp_msf.dta`, `comp_fundq.dta`, `comp_funda.dta` |
| 3 | `03_build_crsp_comp_qtr.py` | outputs of steps 1–2 | `crsp_re_qtr.dta` (quarterly equity returns), `comp_qtr.dta` (Compustat backfill) |
| 4 | `04_unlevered_returns.do` (Stata) | `spg_fin_qtr.dta`, `spg_fin_ann.dta`, `crsp_re_qtr.dta`, `comp_qtr.dta` | `UnlevRet_qtr.dta` (firm-quarter levered and unlevered returns) |
| 5 | `05_build_indices.py` | `UnlevRet_qtr.dta` | `../data/reit_return_indices.csv`, `../data/reit_returns_by_property_type.csv` |

```bash
WORK=/path/outside/the/repo          # licensed intermediates live here
python pipeline/01_import_spg.py --spg-file "RE Companies (S&P Global).xlsx" --data-dir "$WORK"
export WRDS_USERNAME=your_wrds_id    # optional; the wrds package prompts otherwise
python pipeline/02_wrds_pull.py --data-dir "$WORK"
python pipeline/03_build_crsp_comp_qtr.py --data-dir "$WORK"
stata-mp -b do pipeline/04_unlevered_returns.do "$WORK"      # or: do ... "$WORK" inside Stata
python pipeline/05_build_indices.py --data-dir "$WORK"       # writes ../data/*.csv
python scripts/build_outputs.py && python scripts/check_data.py
```

Run the commands from the repository root. After step 5, `git diff data/` shows what
changed relative to the published vintage.

## S&P Global workbook layout (step 1)

- Sheet `Companies`: data start in row 6; the first nine columns are, in order, company
  name, SNL Institution Key, CUSIP, Property Type, Property Subtype, REIT election status
  (`Yes`/`No`), REIT month, REIT year, ticker.
- Fourteen financial sheets named `<Item> (Qtr)` and `<Item> (Ann)` for the items Total
  Assets, Total Debt, Total Preferred Equity, Market Capitalization, Interest Expense,
  Preferred Dividends Paid and ROAE. Period labels (e.g. `2025Q4`, `2025Y`) are in row 4,
  the SNL Institution Key is in column B, and values start in column D and row 6.
- Money items are in $000 except Market Capitalization ($M); the script converts
  everything to $M. `NA`/`NM` are treated as missing.

## Environment

- Python 3.11+ with the packages in [`requirements.txt`](requirements.txt)
  (pandas ≥ 2.2 is required for `groupby(...).apply(..., include_groups=False)`).
- Stata 16.1 or later; only built-in commands are used (no user-written packages).

## Relation to the production code

These are public copies of the scripts used to build the 2026-09 vintage. Steps 1–4
differ from the production versions only in how paths and the WRDS login are supplied
(command-line arguments and an environment variable instead of hard-coded locations).
Step 5 keeps the production index function (`idx`) unchanged and adds the Core/Non-core
groups, the fewer-than-3-firms rule for property-type cells, and the CSV writers.

| Public script | Production script |
|---|---|
| `01_import_spg.py` | `01_import_spg.py` |
| `02_wrds_pull.py` | `03_wrds_pull.py` |
| `03_build_crsp_comp_qtr.py` | `04_build_crsp_comp_qtr.py` |
| `04_unlevered_returns.do` | `02_unlevered_spg.do` |
| `05_build_indices.py` | `11_levered_indices.py` |

The method is documented in [`../docs/methodology.md`](../docs/methodology.md).
