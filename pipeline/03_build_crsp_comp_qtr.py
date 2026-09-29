#!/usr/bin/env python3
"""
03_build_crsp_comp_qtr.py  —  Bridge CRSP & Compustat to the S&P Global (SNL) key
(snlkey) via CUSIP, and produce two snlkey x calendar-quarter files:

  crsp_re_qtr.dta  : re = quarterly equity total return (fraction), chain-linked
                     from CRSP monthly + delisting returns; n_months for coverage.
  comp_qtr.dta     : Compustat quarterly backfill -> mcap_cs, debt_cs, pref_cs,
                     xint_cs, dvp_cs (all $M), keyed snlkey x (year,quarter).

Usage:
    python 03_build_crsp_comp_qtr.py --data-dir /path/to/work

Alignment: CALENDAR quarters (S&P Global financials are reported by calendar
quarter; most REITs are Dec-FYE so this is exact). Linkage by CUSIP (no
CRSP-Ziman or CRSP/Compustat Merged link table required).

Public copy of the production script (04_build_crsp_comp_qtr.py); only path
handling differs.
"""
import argparse
import os
import numpy as np, pandas as pd, pyreadstat

ap = argparse.ArgumentParser(description="Build quarterly CRSP returns and Compustat backfill.")
ap.add_argument("--data-dir", required=True,
                help="working directory holding the outputs of 01_import_spg.py and 02_wrds_pull.py")
D = os.path.join(ap.parse_args().data_dir, "")


def rd(f):
    return pyreadstat.read_dta(D + f)[0]


# ---- CUSIP(8) -> snlkey map (from S&P Global companies) ----
comp = rd("spg_companies.dta")
comp["c8"] = comp.cusip.str[:8]
cu2snl = (comp.dropna(subset=["c8"])
          .drop_duplicates("c8").set_index("c8").snlkey.astype("int64").to_dict())

# ---- permno -> snlkey (via CIZ stocknames_v2 cusip, already 8-char) ----
sn = rd("crsp_stocknames.dta")
sn["c8"] = sn.cusip.astype("string").str[:8]
sn["snlkey"] = sn.c8.map(cu2snl)
# a permno may carry several ncusips over time; take its modal matched snlkey
p2snl = (sn.dropna(subset=["snlkey"])
         .groupby("permno").snlkey
         .agg(lambda s: s.value_counts().index[0]).astype("int64").to_dict())

# =====================  CRSP returns -> quarterly re  =====================
# CIZ msf_v2: mthret already includes delisting returns (no separate merge).
m = rd("crsp_msf.dta")
m["r"] = pd.to_numeric(m.ret, errors="coerce")
m["date"] = pd.to_datetime(m.date)
m["year"] = m.date.dt.year
m["quarter"] = m.date.dt.quarter
m["snlkey"] = m.permno.map(p2snl)
m = m.dropna(subset=["snlkey", "r"])

# chain-link within calendar quarter: re = prod(1+r)-1
g = m.groupby(["snlkey", "year", "quarter"])
re = g.apply(lambda x: np.prod(1 + x.r) - 1, include_groups=False).rename("re").reset_index()
re["n_months"] = g.size().values
re["snlkey"] = re.snlkey.astype("int64")
# if >1 permno maps to a snlkey-quarter, the groupby already pooled them by month;
# guard: keep quarters with 1-3 months (drop pathological pooled >3)
re = re[re.n_months <= 3].copy()

# =====================  Compustat quarterly backfill  =====================
fq = rd("comp_fundq.dta")
for c in ["dlttq", "dlcq", "dvpq", "pstkq", "xintq", "prccq", "cshoq"]:
    fq[c] = pd.to_numeric(fq[c], errors="coerce")
fq["c8"] = fq.cusip.str[:8]
fq["snlkey"] = fq.c8.map(cu2snl)
fq = fq.dropna(subset=["snlkey"])
fq["datadate"] = pd.to_datetime(fq.datadate)
fq["year"] = fq.datadate.dt.year
fq["quarter"] = fq.datadate.dt.quarter
fq["mcap_cs"] = fq.prccq * fq.cshoq                       # $M
fq["debt_cs"] = fq.dlttq.fillna(0) + fq.dlcq.fillna(0)    # $M
fq["pref_cs"] = fq.pstkq
fq["xint_cs"] = fq.xintq
fq["dvp_cs"] = fq.dvpq
cq = (fq.sort_values(["snlkey", "year", "quarter", "datadate"])
      .drop_duplicates(["snlkey", "year", "quarter"], keep="last")
      [["snlkey", "year", "quarter", "mcap_cs", "debt_cs", "pref_cs", "xint_cs", "dvp_cs"]])
cq["snlkey"] = cq.snlkey.astype("int64")

# ---- save ----
re.to_stata(D + "crsp_re_qtr.dta", write_index=False, version=118)
cq.to_stata(D + "comp_qtr.dta", write_index=False, version=118)
print(f"crsp_re_qtr.dta : {len(re)} snlkey-quarters | {re.snlkey.nunique()} REITs | "
      f"{int(re.year.min())}Q.. {int(re.year.max())}Q | full-qtr(n=3): {(re.n_months==3).mean():.2%}")
print(f"comp_qtr.dta    : {len(cq)} snlkey-quarters | {cq.snlkey.nunique()} REITs")
print(f"id maps: cusip->snlkey {len(cu2snl)} | permno->snlkey {len(p2snl)}")
# quick re sanity
print("re: mean %.4f median %.4f (quarterly)" % (re.re.mean(), re.re.median()))
