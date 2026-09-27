# Methodology

This note documents how the 2026-09 vintage of the series in [`../data`](../data) is built.
The code is in [`../pipeline`](../pipeline); step numbers below refer to its scripts.

## 1. Data sources

| Source | Tables / items | Used for |
|---|---|---|
| S&P Global Market Intelligence (formerly SNL), "RE Companies" export | Company list (SNL key, CUSIP, property type and subtype, REIT election status); quarterly and annual total debt, preferred equity, market capitalization, interest expense, preferred dividends | Universe, classification, capital structure |
| CRSP, CIZ format (via WRDS) | `crsp.stocknames_v2`, `crsp.msf_v2` | Monthly total stock returns, including delisting returns |
| Compustat North America (via WRDS) | `comp.fundq`, `comp.funda` | Backfill of market capitalization, debt, preferred equity, interest expense and preferred dividends |

All sources were retrieved in mid-2026. CRSP returns run through December 2025, which ends
the sample at 2025Q4.

## 2. Sample

The universe is the equity REITs in the S&P Global company list that have a CUSIP (rather
than a CINS) and U.S. REIT election status (step 1). They are linked to CRSP and Compustat
by 8-character CUSIP (steps 2–3); no CRSP–Compustat link table is needed.

| Stage | REITs | REIT-quarters from 1993Q1 |
|---|---:|---:|
| S&P Global equity REITs with a CUSIP and U.S. REIT status | 683 | |
| … with S&P Global financial data | 660 | 30,391 |
| … matched to CRSP returns | 437 | 20,683 |
| … with a valid unlevered return | 436 | 20,289 |

Each quarter holds 96–183 REITs (47–129 Core, 45–95 Non-core).

**Property types** are S&P Global's classification of each REIT, one type per REIT (the
classification is point-in-time and applies to the REIT's whole history). *Core* follows
Ling and Naranjo (2015): Office, Multifamily, Industrial and the three retail types
(Shopping Center, Regional Mall, Other Retail). *Non-core* is every other type: Diversified,
Health Care, Hotel, Self-Storage, Manufactured Home, Specialty, Data Center and Casino.

## 3. Returns

**Levered return.** The quarterly total stock return $r^{E}_{i,t}$ compounds the REIT's
CRSP monthly returns within the calendar quarter, $r^{E}_{i,t} = \prod_{m \in t}(1 + r_{i,m}) - 1$
(step 3). CIZ monthly returns already include delisting returns. Quarters with one or two
months of returns (listings, delistings) are kept as partial-quarter returns.

**Unlevered return** (step 4; Ling and Naranjo, 2015, eq. 5 and appendix):

$$
r^{U}_{i,t} = \theta^{E}_{i,t-1}\, r^{E}_{i,t} + \theta^{D}_{i,t-1}\, r^{D}_{i,t} + \theta^{P}_{i,t-1}\, r^{P}_{i,t},
\qquad
\theta^{k}_{i,t-1} = \frac{V^{k}_{i,t-1}}{E_{i,t-1} + D_{i,t-1} + P_{i,t-1}}
$$

- $E$ is the market value of common equity, $D$ total debt at book value, and $P$
  preferred equity at book value, all at the end of the quarter.
- $r^{D}_{i,t}$ is interest expense in quarter *t* divided by $D_{i,t-1}$, and
  $r^{P}_{i,t}$ is preferred dividends in quarter *t* divided by $P_{i,t-1}$ (zero when the
  REIT has no preferred stock).
- If a REIT has no debt or no preferred stock, the corresponding term drops out.

**Missing data.** Each input comes from S&P Global first. Missing quarterly interest expense
and preferred dividends are set to one quarter of the annual S&P Global value. Values still
missing are taken from Compustat quarterly data: market capitalization (`prccq` × `cshoq`),
debt (`dlttq` + `dlcq`), preferred equity (`pstkq`), interest expense (`xintq`) and
preferred dividends (`dvpq`). Missing preferred equity and dividends are set to zero. All
amounts are in millions of dollars and aligned to calendar quarters.

## 4. Indices

For each group and quarter (step 5), using REITs with both a levered and an unlevered return:

- **Equal-weighted** (`ew_*`): the simple average across REITs.
- **Value-weighted** (`vw_*`): the average weighted by equity market capitalization at the
  end of the prior quarter. A REIT enters from its second consecutive quarter in the sample,
  when a prior-quarter market capitalization exists. 1992Q4 is used only to weight 1993Q1.
- Levered and unlevered indices use the same REITs.

Groups are all equity REITs, Core, Non-core, and each property type. Property-type cells
with fewer than 3 REITs are published blank, with the REIT count, as a reliability rule
(see [`../data/README.md`](../data/README.md#reit_returns_by_property_typecsv)).

## 5. Validation

**Ling and Naranjo (2015).** The value-weighted unlevered Core index against their
unlevered core REIT index, over their sample (`python scripts/validate.py ln2015`):

| Statistic, 1993Q1–2012Q4 (80 quarters) | This dataset | Ling and Naranjo (2015) |
|---|---:|---:|
| Correlation of quarterly returns | 0.993 | |
| Mean, % per quarter | 2.468 | 2.349 |
| Annualized return | 9.62% | 9.21% |
| Annualized volatility | 10.74% | 9.84% |
| Tracking error, annualized | 1.49% | |

The largest quarterly differences are 2009Q1 (−3.29 points), 2008Q3 (+2.65) and 1993Q1
(+2.64).

**FTSE Nareit.** The value-weighted levered All index against the FTSE Nareit All Equity
REITs total return index, 1993Q1–2025Q4 (132 quarters;
`python scripts/validate.py nareit --nareit-file …`): correlation 0.986, annualized return
9.62% vs 9.45%, volatility 19.00% vs 19.22%, tracking error 3.19%. By property type, against
the corresponding FTSE Nareit sector index (value-weighted levered returns; the 128 quarters
through 2025Q4 that both series cover, or 40 where noted):

| Property type | FTSE Nareit index | Correlation |
|---|---|---:|
| Office | Office | 0.987 |
| Multifamily | Apartments | 0.997 |
| Industrial | Industrial | 0.938 |
| Shopping Center | Shopping Centers | 0.997 |
| Regional Mall | Regional Malls | 0.998 |
| Other Retail | Free Standing | 0.948 |
| Self-Storage | Self Storage | 0.999 |
| Health Care | Health Care | 0.988 |
| Hotel | Lodging/Resorts | 0.985 |
| Manufactured Home | Manufactured Homes | 0.994 |
| Data Center | Data Centers (40 quarters) | 1.000 |
| Diversified | Diversified | 0.586 |
| Specialty | Specialty (40 quarters) | 0.669 |

The low values for Diversified and Specialty reflect different classification of these
catch-all groups by S&P Global and FTSE Nareit. The property-type correlations were computed
before small cells were blanked.

**Previous release.** The 2021-04 vintage (in [`../legacy/2021-04`](../legacy/2021-04)) was
built from CRSP-Ziman, Compustat and S&P Global with a different universe and property
classification. Over the common period, 1993Q1–2020Q4, the unlevered series compare as
follows:

| Unlevered series | Quarters | Correlation | Annualized, 2021 vs 2026 vintage |
|---|---:|---:|---|
| Value-weighted, all REITs | 112 | 0.962 | 8.96% vs 9.05% |
| Value-weighted, Core | 112 | 0.994 | 8.28% vs 8.17% |
| Value-weighted, Non-core | 111 | 0.736 | 9.19% vs 9.78% |
| Equal-weighted, all REITs | 112 | 0.996 | 9.65% vs 9.65% |
| Equal-weighted, Core | 112 | 0.994 | 9.10% vs 8.93% |
| Equal-weighted, Non-core | 112 | 0.982 | 10.08% vs 10.54% |

Value-weighted Non-core differs most; this heterogeneous group is the one most affected by
the changes in universe and property classification.

## 6. Limitations

- Debt and preferred equity are at book value, and their returns are accounting yields
  (interest or dividends over beginning balances), not market returns; there is no tax
  adjustment.
- Property types are point-in-time: a REIT that changed its focus carries its current type
  throughout.
- The universe flag relies on the CUSIP format, so a few issuers outside the United States
  that have CUSIPs may be included.
- Listing and delisting quarters use partial-quarter stock returns.
- Firm counts in small property types are low in parts of the sample; check `n_firms`.

## References

- Ling, D. C., and Naranjo, A. (2015). Returns and information transmission dynamics in
  public and private real estate markets. *Real Estate Economics*, 43(1), 163–208.
  https://doi.org/10.1111/1540-6229.12069
- Ling, D. C., Wang, C., and Zhou, T. (2022). Asset productivity, local information
  diffusion, and commercial real estate returns. *Real Estate Economics*, 50(1), 89–121.
  https://doi.org/10.1111/1540-6229.12354
- FTSE Russell and Nareit. FTSE Nareit U.S. Real Estate Index Series, monthly history.
  https://www.reit.com
