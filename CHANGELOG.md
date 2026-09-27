# Changelog

## 2026-09 (current)

- **Coverage** extended to 1993Q1–2025Q4 (132 quarters).
- **Rebuilt** from CRSP (CIZ format; monthly returns include delisting returns), Compustat and
  S&P Global Market Intelligence, linked by CUSIP, with property types from S&P Global. See
  [`docs/methodology.md`](docs/methodology.md).
- **New series:** levered (stock) returns next to the unlevered returns; the four series for
  14 S&P Global property types; REIT counts for every cell.
- **New files:** CSV data, an Excel workbook, summary statistics, figures, validation
  scripts, integrity checks and the construction code.
- **Not carried forward:** the Ling and Naranjo (2015) comparison column; it remains in the
  legacy workbook.
- **Pending:** the 1993Q1 values of `vw_lev_core`, `vw_unlev_noncore` and `vw_lev_noncore`.
  They need REIT-level market-capitalization weights that were not available when this
  release was assembled and will be added in a revision. Until then, statistics for these
  three series cover 1993Q2–2025Q4.
- How the new series compare with the 2021-04 release over 1993Q1–2020Q4 is in
  [`docs/methodology.md`](docs/methodology.md#5-validation).

## 2021-04

- Quarterly unlevered REIT returns, 1993Q1–2020Q4: value- and equal-weighted, for all, core
  and non-core REITs, plus the Ling and Naranjo (2015) unlevered core index (1993Q1–2012Q4)
  for comparison. Built from CRSP-Ziman, Compustat and S&P Global Market Intelligence.
- Published in March 2022 at the repository root; moved unchanged to
  [`legacy/2021-04/`](legacy/2021-04) in the 2026-09 release.
