#!/usr/bin/env python3
"""Integrity checks for the published data files (Python standard library only).

    python scripts/check_data.py

Exits with status 1 and a list of problems if any check fails.
"""
import csv
import math
import os
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
DATA = os.path.join(ROOT, "data")
FIRST, LAST = (1993, 1), (2025, 4)
CORE = {"Office", "Multifamily", "Industrial", "Shopping Center", "Regional Mall", "Other Retail"}
MIN_FIRMS = 3
SERIES = ["vw_unlev", "ew_unlev", "vw_lev", "ew_lev"]
WIDE = ["year", "quarter", "quarter_end"] + [f"{s}_{g}" for s in SERIES for g in ("all", "core", "noncore")] \
       + ["n_all", "n_core", "n_noncore"]
LONG = ["year", "quarter", "quarter_end", "property_type", "core", "n_firms"] + SERIES
SUMMARY = ["group", "weighting", "series", "period_start", "period_end", "n_quarters",
           "mean_qtr", "sd_qtr", "ann_return", "ann_volatility", "min_qtr", "max_qtr"]
IDENTIFIERS = {"cusip", "permno", "permco", "ticker", "snlkey", "gvkey", "name", "conm", "issuernm"}
# Value-weighted Core/Non-core cells for 1993Q1 need firm-level weights that were not
# available when the 2026-09 vintage was assembled; they may be blank (see CHANGELOG.md).
ALLOWED_BLANK = {(1993, 1): {"vw_lev_core", "vw_unlev_noncore", "vw_lev_noncore"}}
QEND = {1: "03-31", 2: "06-30", 3: "09-30", 4: "12-31"}

problems = []


def fail(msg):
    problems.append(msg)


def read(name):
    with open(os.path.join(DATA, name), newline="") as f:
        rows = list(csv.reader(f))
    return rows[0], rows[1:]


def num(v):
    return None if v == "" else float(v)


def quarters():
    y, q = FIRST
    while (y, q) <= LAST:
        yield y, q
        y, q = (y, q + 1) if q < 4 else (y + 1, 1)


# ---------------------------------------------------------------- wide file
head, rows = read("reit_return_indices.csv")
if head != WIDE:
    fail(f"reit_return_indices.csv: unexpected columns {head}")
wide = {}
for r in rows:
    d = dict(zip(head, r))
    key = (int(d["year"]), int(d["quarter"]))
    if key in wide:
        fail(f"duplicate quarter {key}")
    wide[key] = d
if list(wide) != list(quarters()):
    fail(f"reit_return_indices.csv: quarters are not exactly {FIRST}..{LAST} in order")
for (y, q), d in wide.items():
    if d["quarter_end"] != f"{y:04d}-{QEND[q]}":
        fail(f"{y}Q{q}: quarter_end {d['quarter_end']}")
    for c in WIDE[3:-3]:
        v = num(d[c])
        if v is None:
            if c not in ALLOWED_BLANK.get((y, q), set()):
                fail(f"{y}Q{q}: {c} is blank")
        elif not abs(v) < 100:
            fail(f"{y}Q{q}: {c}={v} out of range")
    n = {k: int(d[f"n_{k}"]) for k in ("all", "core", "noncore")}
    if min(n.values()) < MIN_FIRMS or n["all"] != n["core"] + n["noncore"]:
        fail(f"{y}Q{q}: firm counts {n}")

# ---------------------------------------------------------------- property-type file
head, rows = read("reit_returns_by_property_type.csv")
if head != LONG:
    fail(f"reit_returns_by_property_type.csv: unexpected columns {head}")
seen, sums = set(), {}
for r in rows:
    d = dict(zip(head, r))
    y, q, ty, n = int(d["year"]), int(d["quarter"]), d["property_type"], int(d["n_firms"])
    if (ty, y, q) in seen:
        fail(f"duplicate row {ty} {y}Q{q}")
    seen.add((ty, y, q))
    if (y, q) not in wide or d["quarter_end"] != f"{y:04d}-{QEND[q]}":
        fail(f"{ty} {y}Q{q}: bad date")
    if int(d["core"]) != int(ty in CORE):
        fail(f"{ty}: core flag {d['core']}")
    if n < 1:
        fail(f"{ty} {y}Q{q}: n_firms {n}")
    vals = [num(d[s]) for s in SERIES]
    if n < MIN_FIRMS and any(v is not None for v in vals):
        fail(f"{ty} {y}Q{q}: fewer than {MIN_FIRMS} firms but returns published")
    if n >= MIN_FIRMS and any(v is None for v in vals):
        fail(f"{ty} {y}Q{q}: returns missing")
    if any(v is not None and not abs(v) < 100 for v in vals):
        fail(f"{ty} {y}Q{q}: return out of range")
    s = sums.setdefault((y, q), {"all": 0, "core": 0, "ew_all": 0.0, "complete": True})
    s["all"] += n
    s["core"] += n * (ty in CORE)
    if vals[1] is None:
        s["complete"] = False
    else:
        s["ew_all"] += n * vals[1]
for key, d in wide.items():
    s = sums.get(key)
    if not s or s["all"] != int(d["n_all"]) or s["core"] != int(d["n_core"]):
        fail(f"{key}: property-type counts do not add up to the All/Core counts")
    elif s["complete"] and abs(s["ew_all"] / s["all"] - float(d["ew_unlev_all"])) > 1e-5:
        fail(f"{key}: equal-weighted All differs from the firm-weighted property types")

# ---------------------------------------------------------------- summary statistics
head, rows = read("summary_statistics.csv")
if head != SUMMARY:
    fail(f"summary_statistics.csv: unexpected columns {head}")
lookup = {}
for (y, q), d in wide.items():
    for c in WIDE[3:-3]:
        lookup.setdefault(c, {})[(y, q)] = num(d[c])
tags = {"All": "all", "Core": "core", "Non-core": "noncore"}
checked = 0
for r in rows:
    d = dict(zip(head, r))
    if d["group"] not in tags:
        continue
    col = f"{d['weighting'].lower()}_{'unlev' if d['series'] == 'unlevered' else 'lev'}_{tags[d['group']]}"
    lo = (int(d["period_start"][:4]), int(d["period_start"][-1]))
    hi = (int(d["period_end"][:4]), int(d["period_end"][-1]))
    xs = [v for k, v in lookup[col].items() if lo <= k <= hi and v is not None]
    mean = sum(xs) / len(xs)
    sd = math.sqrt(sum((x - mean) ** 2 for x in xs) / (len(xs) - 1))
    ann = (math.prod(1 + x / 100 for x in xs) ** (4 / len(xs)) - 1) * 100
    if int(d["n_quarters"]) != len(xs) or max(abs(mean - float(d["mean_qtr"])), abs(sd - float(d["sd_qtr"])),
                                               abs(ann - float(d["ann_return"]))) > 2e-6:
        fail(f"summary_statistics.csv: {d['group']} {d['weighting']} {d['series']} "
             f"{d['period_start']}-{d['period_end']} does not recompute")
    checked += 1

# ---------------------------------------------------------------- no identifiers anywhere
for name in ("reit_return_indices.csv", "reit_returns_by_property_type.csv", "summary_statistics.csv"):
    cols = {c.lower() for c in read(name)[0]}
    if cols & IDENTIFIERS:
        fail(f"{name}: identifier columns {cols & IDENTIFIERS}")

if problems:
    print(f"FAILED: {len(problems)} problem(s)")
    for p in problems[:50]:
        print("  -", p)
    sys.exit(1)
blank = sum(1 for k, cols in ALLOWED_BLANK.items() for c in cols if num(wide[k][c]) is None)
print(f"OK: {len(wide)} quarters, {len(seen)} property-type rows, {checked} summary rows recomputed"
      + (f"; {blank} pending 1993Q1 cell(s) blank" if blank else ""))
