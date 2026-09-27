# Data dictionary

Vintage **2026-09**. All returns are nominal total returns in **percent per calendar
quarter** (not annualized). `quarter_end` is the last day of the calendar quarter. Missing
values are empty fields. How the series are built is described in
[`../docs/methodology.md`](../docs/methodology.md).

## `reit_return_indices.csv`

All equity REITs, Core and Non-core. One row per quarter, 1993Q1–2025Q4 (132 rows).

| Column | Description |
|---|---|
| `year`, `quarter`, `quarter_end` | Calendar quarter |
| `vw_unlev_all`, `vw_unlev_core`, `vw_unlev_noncore` | Value-weighted **unlevered** return: all equity REITs, Core, Non-core |
| `ew_unlev_all`, `ew_unlev_core`, `ew_unlev_noncore` | Equal-weighted unlevered return |
| `vw_lev_all`, `vw_lev_core`, `vw_lev_noncore` | Value-weighted **levered** (stock) return |
| `ew_lev_all`, `ew_lev_core`, `ew_lev_noncore` | Equal-weighted levered return |
| `n_all`, `n_core`, `n_noncore` | Number of REITs with both a levered and an unlevered return in the quarter |

- **Core**: Office, Multifamily, Industrial, Shopping Center, Regional Mall and Other Retail
  REITs. **Non-core**: all other property types. `n_all = n_core + n_noncore`.
- **Value weights** are equity market capitalizations at the end of the prior quarter. A
  REIT enters value-weighted averages from its second quarter in the sample, so a
  value-weighted average can rest on slightly fewer REITs than `n`.
- Levered and unlevered returns use the same REITs in each quarter.
- **Pending in this vintage:** the 1993Q1 values of `vw_lev_core`, `vw_unlev_noncore` and
  `vw_lev_noncore` are blank (see [`../CHANGELOG.md`](../CHANGELOG.md)).

## `reit_returns_by_property_type.csv`

One row per S&P Global property type and quarter in which the type has at least one REIT
(1,716 rows).

| Column | Description |
|---|---|
| `year`, `quarter`, `quarter_end` | Calendar quarter |
| `property_type` | S&P Global property type of the REIT (see list below) |
| `core` | 1 if the type belongs to Core, 0 otherwise |
| `n_firms` | Number of REITs with both a levered and an unlevered return |
| `vw_unlev`, `ew_unlev`, `vw_lev`, `ew_lev` | As above, for the property type |

- Property types: Casino (from 2014Q1), Data Center (from 2005Q1), Diversified, Health
  Care, Hotel, Industrial, Manufactured Home, Multifamily, Office, Other Retail, Regional
  Mall, Self-Storage, Shopping Center, Specialty. The six Core types add up to Core and the
  rest to Non-core.
- **Small cells.** When `n_firms` is below 3 the four returns are left blank (88 of 1,716
  rows); `n_firms` is always reported. This is a reliability rule for series that would
  otherwise be one or two companies' returns. It is not a confidentiality mechanism: with the
  Core/Non-core aggregates, a blank cell can be backed out.

## `summary_statistics.csv`

| Column | Description |
|---|---|
| `group` | All, Core, Non-core, or a property type with a published value in every quarter of the period |
| `weighting` | `VW` (value-weighted) or `EW` (equal-weighted) |
| `series` | `unlevered` or `levered` |
| `period_start`, `period_end` | 1993Q1–2025Q4, 1993Q1–2012Q4, or 2013Q1–2025Q4 |
| `n_quarters` | Quarters with a value in the period |
| `mean_qtr`, `sd_qtr` | Mean and standard deviation of quarterly returns, % |
| `ann_return` | Annualized geometric mean return, % |
| `ann_volatility` | `sd_qtr` × 2, % |
| `min_qtr`, `max_qtr` | Lowest and highest quarterly return, % |

Computed from the two CSVs by [`../scripts/build_outputs.py`](../scripts/build_outputs.py).

## `REIT_Return_Indices.xlsx`

The two CSVs and the summary statistics as worksheets, plus a *Notes* sheet with
definitions, sources, citation and license. Generated from the CSVs, which are the
authoritative copies.

## Mapping from the 2021 release

| 2021 workbook column (`legacy/2021-04/`) | 2026 column |
|---|---|
| `vw unlev` | `vw_unlev_all` |
| `vw unlev (core)` | `vw_unlev_core` |
| `vw unlev (non-core)` | `vw_unlev_noncore` |
| `ew unlev` | `ew_unlev_all` |
| `ew unlev (core)` | `ew_unlev_core` |
| `ew unlev (non-core)` | `ew_unlev_noncore` |
| `L&N unlev (core)` | Not carried forward; the Ling and Naranjo (2015) series (1993Q1–2012Q4) remains in the legacy workbook |

The two releases are built from different data sources and universes; how they compare is
in [`../CHANGELOG.md`](../CHANGELOG.md).
