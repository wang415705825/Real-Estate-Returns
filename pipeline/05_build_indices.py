#!/usr/bin/env python3
"""
05_build_indices.py  —  Build the public quarterly REIT return indices from the
firm-quarter panel written by 04_unlevered_returns.do (UnlevRet_qtr.dta).

Usage:
    python 05_build_indices.py --data-dir /path/to/work [--out-dir ../data]

Universe : S&P Global US & elected equity REITs matched to CRSP (us_cusip & elected_yes).
Groups   : All, Core (Office, Multifamily, Industrial, Shopping Center, Regional Mall,
           Other Retail), Non-core (all other types), and each S&P property type.
Weights  : equal-weighted (EW) and value-weighted (VW) by prior-quarter market cap.
Series   : levered (CRSP total equity return) and unlevered (LN2015 WACC de-levering),
           both in percent per calendar quarter, 1993Q1 onward.

Outputs (in --out-dir):
  reit_return_indices.csv            All / Core / Non-core, wide, one row per quarter
  reit_returns_by_property_type.csv  one row per property type x quarter; the four
                                     returns are left blank when fewer than 3 firms

Derived from the production script 11_levered_indices.py: idx() is unchanged; this
version adds the Core/Non-core groups, the small-cell rule, and the public-file
writers, and omits the project-internal tables and figure.
"""
import argparse
import csv
import os
import numpy as np, pandas as pd, pyreadstat

FIRST_YEAR = 1993    # 1992Q4 is pulled only as the lagged-market-cap pad quarter
CORE_TYPES = ["Office", "Multifamily", "Industrial",
              "Shopping Center", "Regional Mall", "Other Retail"]
MIN_FIRMS = 3        # property-type cells with fewer firms are published blank
WIDE_GROUPS = [("All", "all"), ("Core", "core"), ("Non-core", "noncore")]
SERIES = ["vw_unlev", "ew_unlev", "vw_lev", "ew_lev"]
QUARTER_END = {1: "03-31", 2: "06-30", 3: "09-30", 4: "12-31"}


def load_panel(path):
    df, _ = pyreadstat.read_dta(path)
    df = df[(df.us_cusip == 1) & (df.elected_yes == 1)].copy()         # equity-REIT universe
    # levered return to percent (re is a fraction); UnlevRet already percent
    df["lev"] = df.re * 100.0
    df["unlev"] = df.UnlevRet
    df["qi"] = df.year.astype(int) * 4 + (df.quarter.astype(int) - 1)
    df = df.sort_values(["snlkey", "qi"])
    df["Lmcap"] = np.where(df.groupby("snlkey").qi.shift(1) == df.qi - 1, df.groupby("snlkey").mcap.shift(1), np.nan)
    return df[df.year >= FIRST_YEAR].copy()   # drop the pad quarter (kept above only for 1993Q1's Lmcap)


def idx(sub):
    """EW & VW (lagged mcap) mean of lev & unlev for a firm-qtr subset, by quarter."""
    s = sub.dropna(subset=["lev", "unlev"])
    out = s.groupby("qi").agg(ew_lev=("lev", "mean"), ew_unlev=("unlev", "mean"), n=("lev", "size")).reset_index()
    v = s.dropna(subset=["Lmcap"]); v = v[v.Lmcap > 0]
    vw = v.groupby("qi").apply(lambda x: pd.Series({
        "vw_lev": np.average(x.lev, weights=x.Lmcap), "vw_unlev": np.average(x.unlev, weights=x.Lmcap)}),
        include_groups=False).reset_index()
    return out.merge(vw, on="qi", how="left")


def build(df):
    """Long frame: qi, group, n, n_vw, ew_lev, ew_unlev, vw_lev, vw_unlev."""
    panels = {"All": df,
              "Core": df[df.ptype.isin(CORE_TYPES)],
              "Non-core": df[~df.ptype.isin(CORE_TYPES)]}
    for ty in sorted(df.ptype.dropna().unique()):
        panels[ty] = df[df.ptype == ty]
    rows = []
    for name, sub in panels.items():
        g = idx(sub)
        v = sub.dropna(subset=["lev", "unlev", "Lmcap"])
        g = g.merge(v[v.Lmcap > 0].groupby("qi").size().rename("n_vw").reset_index(), on="qi", how="left")
        g["group"] = name
        rows.append(g)
    return pd.concat(rows, ignore_index=True)


def _fmt(v):
    """Fixed 6 decimals; blank if missing; never '-0.000000'."""
    if pd.isna(v):
        return ""
    s = f"{float(v):.6f}"
    return "0.000000" if s == "-0.000000" else s


def _date_cols(qi):
    y, q = int(qi) // 4, int(qi) % 4 + 1
    return [y, q, f"{y:04d}-{QUARTER_END[q]}"]


def write_outputs(long, out_dir):
    """Write the two public CSVs from a long frame with columns
    qi, group, n, ew_lev, ew_unlev, vw_lev, vw_unlev."""
    os.makedirs(out_dir, exist_ok=True)
    long = long[long.qi // 4 >= FIRST_YEAR]
    by = {g: d.set_index("qi") for g, d in long.groupby("group")}

    # 1) All / Core / Non-core, wide
    header = ["year", "quarter", "quarter_end"]
    header += [f"{s}_{tag}" for s in SERIES for _, tag in WIDE_GROUPS]
    header += [f"n_{tag}" for _, tag in WIDE_GROUPS]
    with open(os.path.join(out_dir, "reit_return_indices.csv"), "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(header)
        for qi in sorted(by["All"].index):
            row = _date_cols(qi)
            row += [_fmt(by[g][s].get(qi, np.nan)) for s in SERIES for g, _ in WIDE_GROUPS]
            row += [int(by[g]["n"].get(qi, 0)) for g, _ in WIDE_GROUPS]
            w.writerow(row)

    # 2) by S&P property type, long, small cells blanked
    types = sorted(g for g in by if g not in dict(WIDE_GROUPS))
    with open(os.path.join(out_dir, "reit_returns_by_property_type.csv"), "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["year", "quarter", "quarter_end", "property_type", "core", "n_firms"] + SERIES)
        for ty in types:
            d = by[ty]
            for qi in sorted(d.index):
                n = int(d.at[qi, "n"])
                vals = [_fmt(d.at[qi, s]) if n >= MIN_FIRMS else "" for s in SERIES]
                w.writerow(_date_cols(qi) + [ty, int(ty in CORE_TYPES), n] + vals)


def main():
    ap = argparse.ArgumentParser(description="Build the public REIT return index files.")
    ap.add_argument("--data-dir", required=True,
                    help="working directory containing UnlevRet_qtr.dta from 04_unlevered_returns.do")
    ap.add_argument("--out-dir", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data"),
                    help="where to write the public CSVs (default: the repository's data/ folder)")
    args = ap.parse_args()

    df = load_panel(os.path.join(args.data_dir, "UnlevRet_qtr.dta"))
    long = build(df)
    write_outputs(long, args.out_dir)

    usable = df[df.unlev.notna()]
    print(f"sample: {usable.snlkey.nunique()} REITs, {len(usable)} firm-quarters with a valid unlevered return")
    print(f"groups: {long.group.nunique()} | quarters: {long.qi.nunique()} "
          f"({long.qi.min() // 4}Q{long.qi.min() % 4 + 1}-{long.qi.max() // 4}Q{long.qi.max() % 4 + 1})")
    thin = long[~long.group.isin(dict(WIDE_GROUPS)) & (long.n < MIN_FIRMS)]
    print(f"property-type cells blanked (n < {MIN_FIRMS}): {len(thin)}")
    fewer = long[long.n_vw.fillna(0) < long.n]
    print(f"group-quarters where the VW sample has fewer firms than n: {len(fewer)}")
    print("WROTE ->", os.path.abspath(args.out_dir))


if __name__ == "__main__":
    main()
