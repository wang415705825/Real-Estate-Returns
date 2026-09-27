#!/usr/bin/env python3
"""
02_wrds_pull.py  —  Pull the REIT-side WRDS data for the de-levering pipeline.

Usage:
    export WRDS_USERNAME=<your WRDS username>   # optional; otherwise wrds prompts
    python 02_wrds_pull.py --data-dir /path/to/work

CRSP source = CIZ tables (crsp.msf_v2 / crsp.stocknames_v2): the legacy SIZ
crsp.msf is frozen at 2024Q4; CIZ runs to 2025Q4. In CIZ, mthret already
includes delisting returns, so no separate msedelist merge is needed.

Universe: S&P Global US & elected REITs (spg_companies.dta) -> 8-char CUSIP set.
Linkage : by CUSIP (no CRSP-Ziman or CRSP/Compustat Merged link table required).

Pulls:
  crsp.stocknames_v2 -> permno<->cusip/ticker history       -> crsp_stocknames.dta
  crsp.msf_v2        -> monthly returns (delisting-incl)     -> crsp_msf.dta
  comp.fundq         -> quarterly fundamentals (backfill)    -> comp_fundq.dta
  comp.funda         -> annual fundamentals (backfill)       -> comp_funda.dta

Public copy of the production script (03_wrds_pull.py); only path and
credential handling differ.
"""
import argparse
import os
import wrds, pyreadstat

ap = argparse.ArgumentParser(description="Pull CRSP CIZ and Compustat data from WRDS.")
ap.add_argument("--data-dir", required=True,
                help="working directory for licensed intermediate files "
                     "(must contain spg_companies.dta from 01_import_spg.py)")
D = os.path.join(ap.parse_args().data_dir, "")

# ----------------------------------------------------------------------------------
# SAMPLE WINDOW. The published indices run 1993Q1-2025Q4 (the Ling & Naranjo 2015
# window). START bounds the CRSP/Compustat pull; everything downstream inherits it.
#
# We pull from 1992Q4 (one quarter of PAD) so that 1993Q1 has a lagged-market-cap weight
# for the value-weighted indices; the pad quarter is dropped by 05_build_indices.py.
#
# TO CHANGE THE WINDOW (e.g. start 1990): set START to one quarter before the new first
# quarter, set SAMPLE_FLOOR_YEAR (and FIRST_YEAR in 05_build_indices.py), and re-run
# 02 -> 03 -> 04 -> 05. Pre-1993 REIT counts get thin (noisier estimates).
# ----------------------------------------------------------------------------------
START      = "1992-10-01"   # 1993Q1 start (LN2015 window) + 1 quarter pad for the lagged-mcap weight
SAMPLE_FLOOR_YEAR = 1993    # analysis floor the downstream scripts use (the pad quarter is dropped)
CRSP_END   = "2025-12-31"   # crsp.msf_v2 currency
COMP_END   = "2026-06-30"   # comp.fundq runs ahead; index still gated by returns

_user = os.environ.get("WRDS_USERNAME")
db = wrds.Connection(wrds_username=_user) if _user else wrds.Connection()

# ---- universe: 8-char CUSIPs of US & elected S&P REITs ----
comp, _ = pyreadstat.read_dta(D + "spg_companies.dta")
comp["c8"] = comp.cusip.str[:8]
cusips = sorted(set(comp[(comp.us_cusip == 1) & (comp.elected_yes == 1)].c8.dropna()))
cl = ",".join("'" + c + "'" for c in cusips)
print(f"universe: {len(cusips)} CUSIPs")

# ---- 1) CIZ stocknames: CUSIP -> permno ----
sn = db.raw_sql(f"""
    select permno, cusip, cusip9, ticker, issuernm, namedt, nameenddt
    from crsp.stocknames_v2
    where cusip in ({cl}) or substr(cusip9,1,8) in ({cl})
""")
permnos = sorted(set(sn.permno.dropna().astype(int)))
pl = ",".join(str(p) for p in permnos)
print(f"stocknames_v2: {len(sn)} rows, {len(permnos)} permnos")

# ---- 2) CIZ monthly returns (mthret includes delisting) ----
msf = db.raw_sql(f"""
    select permno, mthcaldt as date, mthret as ret, mthretx as retx,
           mthprc as prc, shrout, mthcap, ticker, sharetype, securitytype
    from crsp.msf_v2
    where permno in ({pl}) and mthcaldt between '{START}' and '{CRSP_END}'
""")
print(f"msf_v2: {len(msf)} rows | {msf.date.max()} max date")

# ---- 3) Compustat quarterly (standard screen) ----
fundq = db.raw_sql(f"""
    select gvkey, datadate, fyearq, fqtr, cusip, conm,
           dlcq, dlttq, dvpq, pstkq, xintq, prccq, cshoq, atq, ceqq
    from comp.fundq
    where substr(cusip,1,8) in ({cl}) and datadate between '{START}' and '{COMP_END}'
      and indfmt='INDL' and datafmt='STD' and popsrc='D' and consol='C'
""")
# ---- 4) Compustat annual (backfill) ----
funda = db.raw_sql(f"""
    select gvkey, datadate, fyear, cusip, conm,
           dlc, dltt, dvp, pstkl, xint
    from comp.funda
    where substr(cusip,1,8) in ({cl}) and datadate between '{START}' and '{COMP_END}'
      and indfmt='INDL' and datafmt='STD' and popsrc='D' and consol='C'
""")
print(f"fundq: {len(fundq)} rows, {fundq.gvkey.nunique()} gvkeys, max {fundq.datadate.max()} | "
      f"funda: {len(funda)} rows")

db.close()

# ---- save ----
for name, df in [("crsp_stocknames", sn), ("crsp_msf", msf),
                 ("comp_fundq", fundq), ("comp_funda", funda)]:
    for c in df.columns:
        if df[c].dtype == object:
            df[c] = df[c].astype("string")
    df.to_stata(D + name + ".dta", write_index=False, version=118)
    print(f"WROTE {name}.dta ({len(df)} rows)")
