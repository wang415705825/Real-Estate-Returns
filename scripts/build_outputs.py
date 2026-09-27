#!/usr/bin/env python3
"""Build every derived output from the published CSVs (public data only):

    data/summary_statistics.csv      annualized statistics by group, weighting, series, period
    data/REIT_Return_Indices.xlsx    Excel copy of the CSVs with a notes sheet
    figures/*.png                    README figures, light and dark variants
    README.md                        the statistics table between the stats markers

Run from anywhere:  python scripts/build_outputs.py
Re-running on unchanged CSVs reproduces byte-identical files.
"""
import io
import os
import re
import zipfile
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FixedLocator, FuncFormatter, MultipleLocator
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
DATA, FIGS = os.path.join(ROOT, "data"), os.path.join(ROOT, "figures")
LEGACY = os.path.join(ROOT, "legacy", "2021-04", "Unlevered Return Indices.xlsx")
VINTAGE = "2026-09"
STAMP = "2026-09-01T00:00:00Z"          # fixed file timestamp for reproducible xlsx builds

GROUPS = [("All", "all", "All equity REITs"), ("Core", "core", "Core"), ("Non-core", "noncore", "Non-core")]
WEIGHTS = [("VW", "vw", "value-weighted"), ("EW", "ew", "equal-weighted")]
SERIES = [("unlevered", "unlev"), ("levered", "lev")]
PERIODS = [((1993, 1), (2025, 4)), ((1993, 1), (2012, 4)), ((2013, 1), (2025, 4))]

# Chart tokens: reference palette (slot 1 blue = unlevered, slot 2 orange = levered),
# validated for both modes with the dataviz palette checker.
THEMES = {
    "light": dict(surface="#fcfcfb", ink="#0b0b0b", ink2="#52514e", muted="#898781",
                  grid="#e1e0d9", axis="#c3c2b7", unlev="#2a78d6", lev="#eb6834"),
    "dark": dict(surface="#1a1a19", ink="#ffffff", ink2="#c3c2b7", muted="#898781",
                 grid="#2c2c2a", axis="#383835", unlev="#3987e5", lev="#d95926"),
}


# ----------------------------------------------------------------------------- data
def load():
    idx = pd.read_csv(os.path.join(DATA, "reit_return_indices.csv"))
    bytype = pd.read_csv(os.path.join(DATA, "reit_returns_by_property_type.csv"))
    return idx, bytype


def qlabel(yq):
    return f"{yq[0]}Q{yq[1]}"


def in_period(df, p):
    k = df.year * 4 + df.quarter
    return df[(k >= p[0][0] * 4 + p[0][1]) & (k <= p[1][0] * 4 + p[1][1])]


def stats(s):
    s = s.dropna()
    if s.empty:
        return None
    return dict(n_quarters=len(s), mean_qtr=s.mean(), sd_qtr=s.std(),
                ann_return=((1 + s / 100).prod() ** (4 / len(s)) - 1) * 100,
                ann_volatility=s.std() * 2, min_qtr=s.min(), max_qtr=s.max())


def summary(idx, bytype):
    rows = []
    for p in PERIODS:
        full = len(in_period(idx, p))
        sub = in_period(idx, p)
        for g, tag, _ in GROUPS:
            for w, wtag, _ in WEIGHTS:
                for sname, stag in SERIES:
                    st = stats(sub[f"{wtag}_{stag}_{tag}"])
                    if st:
                        rows.append(dict(group=g, weighting=w, series=sname, period_start=qlabel(p[0]),
                                         period_end=qlabel(p[1]), **st))
        # property types: only where every quarter of the period is published
        for ty, d in bytype.groupby("property_type"):
            d = in_period(d, p)
            if len(d) != full or d[["vw_unlev", "ew_unlev", "vw_lev", "ew_lev"]].isna().any().any():
                continue
            for w, wtag, _ in WEIGHTS:
                for sname, stag in SERIES:
                    rows.append(dict(group=ty, weighting=w, series=sname, period_start=qlabel(p[0]),
                                     period_end=qlabel(p[1]), **stats(d[f"{wtag}_{stag}"])))
    out = pd.DataFrame(rows)
    num = ["mean_qtr", "sd_qtr", "ann_return", "ann_volatility", "min_qtr", "max_qtr"]
    out[num] = out[num].round(6)
    out.to_csv(os.path.join(DATA, "summary_statistics.csv"), index=False, float_format="%.6f", lineterminator="\n")
    return out


# ----------------------------------------------------------------------------- README table
def readme_table(sm, idx):
    full = sm[(sm.period_start == "1993Q1") & (sm.period_end == "2025Q4")]
    nfull = len(idx)
    lines = ["| Series, 1993Q1–2025Q4 | Unlevered: return | Unlevered: volatility | Levered: return | Levered: volatility |",
             "|---|---:|---:|---:|---:|"]
    flagged = False
    for g, _, gname in GROUPS:
        for w, _, wname in WEIGHTS:
            cells = []
            for sname, _ in SERIES:
                r = full[(full.group == g) & (full.weighting == w) & (full.series == sname)].iloc[0]
                mark = "†" if r.n_quarters < nfull else ""
                flagged |= bool(mark)
                cells += [f"{r.ann_return:.2f}%{mark}", f"{r.ann_volatility:.2f}%{mark}"]
            lines.append(f"| {gname}, {wname} | " + " | ".join(cells) + " |")
    lines.append("")
    lines.append("Annualized geometric mean return and annualized volatility (quarterly standard deviation × 2), "
                 "computed from the published CSV; more periods in [`data/summary_statistics.csv`](data/summary_statistics.csv).")
    if flagged:
        lines.append("")
        lines.append("† Computed over the available quarters: the 1993Q1 value of this series is not yet "
                     "published (see [CHANGELOG.md](CHANGELOG.md)).")
    return "\n".join(lines)


def update_readme(table):
    path = os.path.join(ROOT, "README.md")
    if not os.path.exists(path):
        print(table)
        return
    text = open(path, encoding="utf-8").read()
    new = re.sub(r"(<!-- stats:start -->\n).*?(<!-- stats:end -->)",
                 lambda m: m.group(1) + table + "\n" + m.group(2), text, flags=re.S)
    if new != text:
        open(path, "w", encoding="utf-8", newline="\n").write(new)


# ----------------------------------------------------------------------------- workbook
NOTES = [
    ("Unlevered and levered U.S. equity REIT return indices", True),
    (f"Vintage {VINTAGE}. Quarterly, 1993Q1–2025Q4. https://github.com/wang415705825/Real-Estate-Returns", False),
    ("", False),
    ("Contents", True),
    ("Indices: all equity REITs, Core and Non-core; value-weighted (vw) and equal-weighted (ew); "
     "unlevered (unlev) and levered (lev) total returns; n = number of REITs.", False),
    ("By property type: the same four series for each S&P Global property type. Returns are left blank "
     "when fewer than 3 REITs are available (n_firms is always reported).", False),
    ("Summary statistics: annualized geometric returns and volatilities (quarterly SD x 2).", False),
    ("", False),
    ("Definitions", True),
    ("Returns are nominal total returns in percent per calendar quarter (not annualized).", False),
    ("Levered return: the REIT's CRSP total stock return, including dividends and delisting returns.", False),
    ("Unlevered return: the weighted average of the returns to equity, debt and preferred stock, with weights "
     "equal to each claim's share of total capital at the end of the prior quarter "
     "(Ling and Naranjo, 2015, Real Estate Economics).", False),
    ("Value weights: market capitalization at the end of the prior quarter.", False),
    ("Core: Office, Multifamily, Industrial, Shopping Center, Regional Mall and Other Retail REITs. "
     "Non-core: all other property types.", False),
    ("Universe: equity REITs in S&P Global Market Intelligence with U.S. REIT status, matched to CRSP by CUSIP.", False),
    ("", False),
    ("Sources", True),
    ("Compiled from CRSP (CIZ format) and Compustat via WRDS, and S&P Global Market Intelligence, "
     "retrieved in mid-2026. No vendor data are included; only aggregate index returns.", False),
    ("", False),
    ("Citation", True),
    ("Ling, D. C., Wang, C., and Zhou, T. (2022). Asset productivity, local information diffusion, and "
     "commercial real estate returns. Real Estate Economics, 50(1), 89-121. https://doi.org/10.1111/1540-6229.12354", False),
    ("Ling, D. C., and Naranjo, A. (2015). Returns and information transmission dynamics in public and private "
     "real estate markets. Real Estate Economics, 43(1), 163-208. https://doi.org/10.1111/1540-6229.12069", False),
    ("", False),
    ("License", True),
    ("Data and documentation: Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0). "
     "Questions: open an issue at https://github.com/wang415705825/Real-Estate-Returns/issues", False),
]


def _sheet_from_csv(wb, title, path, int_cols=()):
    ws = wb.create_sheet(title)
    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    ws.append(list(df.columns))
    for cell in ws[1]:
        cell.font = Font(bold=True)
    for row in df.itertuples(index=False):
        out = []
        for col, v in zip(df.columns, row):
            if v == "":
                out.append(None)
            elif col in int_cols:
                out.append(int(v))
            else:
                try:
                    out.append(float(v))
                except ValueError:
                    out.append(v)
        ws.append(out)
    for j, col in enumerate(df.columns, start=1):
        letter = ws.cell(row=1, column=j).column_letter
        ws.column_dimensions[letter].width = max(10, min(24, len(col) + 2))
        if col not in int_cols:
            for c in ws[letter][1:]:
                if isinstance(c.value, float):
                    c.number_format = "0.0000"
    ws.freeze_panes = "A2"


def workbook():
    wb = Workbook()
    ws = wb.active
    ws.title = "Notes"
    ws.column_dimensions["A"].width = 120
    for r, (text, bold) in enumerate(NOTES, start=1):
        c = ws.cell(row=r, column=1, value=text or None)
        c.font = Font(bold=bold, size=13 if r == 1 else 11)
        c.alignment = Alignment(wrap_text=True, vertical="top")
    ints = {"year", "quarter", "n_all", "n_core", "n_noncore", "n_firms", "core", "n_quarters"}
    _sheet_from_csv(wb, "Indices", os.path.join(DATA, "reit_return_indices.csv"), ints)
    _sheet_from_csv(wb, "By property type", os.path.join(DATA, "reit_returns_by_property_type.csv"), ints)
    _sheet_from_csv(wb, "Summary statistics", os.path.join(DATA, "summary_statistics.csv"), ints)
    wb.properties.creator = "Real-Estate-Returns"
    wb.properties.title = "Unlevered and levered U.S. equity REIT return indices"
    path = os.path.join(DATA, "REIT_Return_Indices.xlsx")
    buf = io.BytesIO()
    wb.save(buf)
    _write_normalized_zip(buf.getvalue(), path)


def _write_normalized_zip(raw, path):
    """Rewrite an xlsx with fixed timestamps so identical content gives identical bytes."""
    src = zipfile.ZipFile(io.BytesIO(raw))
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as out:
        for info in src.infolist():
            data = src.read(info.filename)
            if info.filename == "docProps/core.xml":
                data = re.sub(rb"(<dcterms:(created|modified)[^>]*>)[^<]*(</dcterms:)",
                              lambda m: m.group(1) + STAMP.encode() + m.group(3), data)
            zi = zipfile.ZipInfo(info.filename, date_time=(2026, 9, 1, 0, 0, 0))
            zi.compress_type = zipfile.ZIP_DEFLATED
            zi.external_attr = info.external_attr
            out.writestr(zi, data)


# ----------------------------------------------------------------------------- figures
def _style(ax, t, ygrid=True, xgrid=False):
    ax.set_facecolor(t["surface"])
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(t["axis"])
    ax.spines["bottom"].set_linewidth(0.75)
    ax.tick_params(colors=t["muted"], labelsize=9, length=0, pad=6)
    ax.grid(False)
    if ygrid:
        ax.yaxis.grid(True, color=t["grid"], linewidth=0.75, linestyle="-")
    if xgrid:
        ax.xaxis.grid(True, color=t["grid"], linewidth=0.75, linestyle="-")
    ax.set_axisbelow(True)


def _titles(fig, t, title, subtitle):
    fig.text(0.012, 0.975, title, ha="left", va="top", fontsize=13, fontweight="bold", color=t["ink"])
    fig.text(0.012, 0.915, subtitle, ha="left", va="top", fontsize=9.5, color=t["ink2"])


def _legend(ax, t, handles, labels, loc="upper left", **kw):
    leg = ax.legend(handles, labels, loc=loc, frameon=False, fontsize=9, handlelength=1.6, **kw)
    for txt in leg.get_texts():
        txt.set_color(t["ink2"])
    return leg


def _save(fig, name, mode):
    suffix = "" if mode == "light" else "-dark"
    fig.savefig(os.path.join(FIGS, f"{name}{suffix}.png"), dpi=200, facecolor=fig.get_facecolor(),
                metadata={"Software": None})
    plt.close(fig)


def fig_cumulative(idx, mode):
    t = THEMES[mode]
    x = idx.year + idx.quarter / 4.0                      # quarter-end position; 1993.0 = end of 1992Q4
    fig, ax = plt.subplots(figsize=(8, 4.6), facecolor=t["surface"])
    fig.subplots_adjust(left=0.08, right=0.82, top=0.83, bottom=0.10)
    _style(ax, t)
    handles = []
    for key, col, lab in [("unlev", "vw_unlev_all", "Unlevered"), ("lev", "vw_lev_all", "Levered")]:
        level = np.r_[1.0, (1 + idx[col] / 100).cumprod().values]
        xx = np.r_[1993.0, x.values]
        (h,) = ax.plot(xx, level, color=t[key], linewidth=1.5, solid_joinstyle="round", solid_capstyle="round")
        ax.plot(xx[-1], level[-1], "o", color=t[key], markersize=6, markeredgecolor=t["surface"], markeredgewidth=1.5)
        ax.annotate(f"{lab}  ${level[-1]:.2f}", (xx[-1], level[-1]), xytext=(8, 0), textcoords="offset points",
                    va="center", fontsize=9, color=t["ink2"])
        handles.append((h, lab))
    ax.set_yscale("log")
    ax.yaxis.set_major_locator(FixedLocator([1, 2, 5, 10, 20]))
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"${v:g}"))
    ax.yaxis.set_minor_locator(FixedLocator([]))
    ax.set_ylim(0.85, 27)
    ax.set_xlim(1992.5, 2026.3)
    ax.xaxis.set_major_locator(FixedLocator(list(range(1995, 2026, 5))))
    _legend(ax, t, [h for h, _ in handles], [lab for _, lab in handles])
    _titles(fig, t, "Growth of $1 in U.S. equity REITs, 1993–2025",
            "Value-weighted, all equity REITs; quarterly total returns compounded; log scale")
    _save(fig, "cumulative_returns", mode)


def fig_ln2015(idx, mode):
    t = THEMES[mode]
    ws = load_workbook(LEGACY, read_only=True, data_only=True)["UnlevRet"]
    ln = {(int(r[0]), int(r[1])): float(r[2]) for r in ws.iter_rows(min_row=10, max_col=3, values_only=True)
          if r[0] is not None and r[2] is not None}
    ours = idx.set_index(["year", "quarter"]).vw_unlev_core
    m = pd.DataFrame({"ln": pd.Series(ln), "ours": ours}).dropna()
    fig, ax = plt.subplots(figsize=(6.2, 6.0), facecolor=t["surface"])
    fig.subplots_adjust(left=0.13, right=0.96, top=0.84, bottom=0.11)
    _style(ax, t, ygrid=True, xgrid=True)
    lim = (-24, 18)
    ax.plot(lim, lim, color=t["muted"], linewidth=1.0, zorder=1)
    ax.scatter(m.ln, m.ours, s=36, color=t["unlev"], edgecolors=t["surface"], linewidths=1.2, zorder=3)
    ax.set_xlim(lim); ax.set_ylim(lim); ax.set_aspect("equal")
    ax.xaxis.set_major_locator(MultipleLocator(10)); ax.yaxis.set_major_locator(MultipleLocator(10))
    ax.set_xlabel("Ling & Naranjo (2015), % per quarter", fontsize=9.5, color=t["ink2"], labelpad=8)
    ax.set_ylabel("This dataset, % per quarter", fontsize=9.5, color=t["ink2"], labelpad=6)
    ax.text(0.04, 0.95, f"Correlation {m.ours.corr(m.ln):.3f}\n{len(m)} quarters, 1993Q1–2012Q4",
            transform=ax.transAxes, va="top", fontsize=9, color=t["ink2"])
    _titles(fig, t, "Validation against Ling & Naranjo (2015)",
            "Value-weighted unlevered core REIT return; one dot per quarter, gray line = equality")
    _save(fig, "validation_ln2015", mode)


def fig_property_types(sm, mode):
    t = THEMES[mode]
    full = sm[(sm.period_start == "1993Q1") & (sm.period_end == "2025Q4") & (sm.weighting == "VW")]
    groups = [g for g in full.group.unique() if g not in ("Core", "Non-core")]
    d = (full[full.group.isin(groups)].pivot(index="group", columns="series", values="ann_return")
         .sort_values("unlevered"))
    labels = ["All equity REITs" if g == "All" else g for g in d.index]
    fig, ax = plt.subplots(figsize=(8, 0.46 * len(d) + 1.9), facecolor=t["surface"])
    fig.subplots_adjust(left=0.22, right=0.97, top=1 - 0.95 / (0.46 * len(d) + 1.9), bottom=0.12)
    _style(ax, t, ygrid=False, xgrid=True)
    y = np.arange(len(d))
    ax.hlines(y, d.unlevered, d.levered, color=t["muted"], linewidth=1.5, zorder=1)
    hu = ax.scatter(d.unlevered, y, s=90, color=t["unlev"], edgecolors=t["surface"], linewidths=1.5, zorder=3)
    hl = ax.scatter(d.levered, y, s=34, color=t["lev"], edgecolors=t["surface"], linewidths=1.5, zorder=3)
    ax.set_yticks(y, labels, fontsize=9, color=t["ink2"])
    ax.tick_params(axis="y", colors=t["ink2"])
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:g}%"))
    ax.xaxis.set_major_locator(MultipleLocator(2))
    lo, hi = np.floor(d.min().min() - 1), np.ceil(d.max().max() + 1)
    ax.set_xlim(lo, hi)
    ax.set_ylim(-0.6, len(d) - 0.4)
    if "All" in d.index:
        i = list(d.index).index("All")
        for col, off, ha in [("unlevered", -9, "right"), ("levered", 9, "left")]:
            ax.annotate(f"{d.loc['All', col]:.2f}%", (d.loc["All", col], i), xytext=(off, 0),
                        textcoords="offset points", ha=ha, va="center", fontsize=8.5, color=t["ink2"])
    _legend(ax, t, [hu, hl], ["Unlevered", "Levered"], loc="lower right")
    _titles(fig, t, "Annualized returns by property type, 1993–2025",
            "Value-weighted; property types with at least 3 REITs in every quarter")
    _save(fig, "property_type_returns", mode)


def main():
    idx, bytype = load()
    sm = summary(idx, bytype)
    update_readme(readme_table(sm, idx))
    workbook()
    os.makedirs(FIGS, exist_ok=True)
    plt.rcParams.update({"font.family": "DejaVu Sans", "svg.hashsalt": "rer", "path.simplify": False})
    for mode in THEMES:
        fig_cumulative(idx, mode)
        fig_ln2015(idx, mode)
        fig_property_types(sm, mode)
    print("wrote data/summary_statistics.csv, data/REIT_Return_Indices.xlsx, figures/*.png")


if __name__ == "__main__":
    main()
