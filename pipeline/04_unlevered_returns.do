********************************************************************************
* 04_unlevered_returns.do
* De-levering pipeline on refreshed data (S&P Global + WRDS), CUSIP/snlkey-keyed.
*
* Usage (from Stata, or batch: stata-mp -b do 04_unlevered_returns.do "/path/to/work"):
*   do 04_unlevered_returns.do "/path/to/work"
*
* INPUTS (<data-dir>):
*   spg_fin_qtr.dta / spg_fin_ann.dta  (01_import_spg.py)          - SNL financials ($M)
*   crsp_re_qtr.dta                    (03_build_crsp_comp_qtr.py) - quarterly re
*   comp_qtr.dta                       (03_...)                    - Compustat backfill
* OUTPUT:
*   UnlevRet_qtr.dta  - firm-quarter unlevered REIT returns (%), with classification
*
* WACC unlevering (LN2015 Eqs. 5/A1-A6):
*   UnlevRet = theta_e*re + theta_d*rd + theta_p*rp     (lagged cap-structure wts)
* Units: all money in $M (SNL converted in 01; Compustat native $M). re a fraction.
*
* Public copy of the production script (02_unlevered_spg.do); only the path
* handling in the marked block below differs.
********************************************************************************

clear all
set more off
* ---- path handling (public copy) ---------------------------------------------
args datadir
if `"`datadir'"' == "" {
    display as error "usage: do 04_unlevered_returns.do <data-dir>"
    exit 198
}
cd `"`datadir'"'
* ------------------------------------------------------------------------------

*-------------------------------------------------------------------------------
* Step 1: SNL quarterly financial panel
*-------------------------------------------------------------------------------
use "spg_fin_qtr.dta", clear
gen fdate = yq(year, quarter)
format fdate %tq
rename (TotalDebt TotalPreferredEquity MarketCapitalization) (bval lval mcap)
replace PreferredDividendsPaid = abs(PreferredDividendsPaid)        // reported signed
rename (InterestExpense PreferredDividendsPaid) (xint dvp)
duplicates drop snlkey fdate, force

*-------------------------------------------------------------------------------
* Step 2a: annual -> quarterly flow backfill (xint, dvp) when qtr missing
*-------------------------------------------------------------------------------
preserve
    use "spg_fin_ann.dta", clear
    keep snlkey year InterestExpense PreferredDividendsPaid
    replace PreferredDividendsPaid = abs(PreferredDividendsPaid)
    rename (InterestExpense PreferredDividendsPaid) (xint_a dvp_a)
    tempfile ann
    save `ann'
restore
merge m:1 snlkey year using `ann', keep(master match) nogen
replace xint = xint_a/4 if missing(xint) & !missing(xint_a)
replace dvp  = dvp_a/4  if missing(dvp)  & !missing(dvp_a)
drop xint_a dvp_a

*-------------------------------------------------------------------------------
* Step 2b: Compustat backfill (mcap, debt, preferred, flows) before weights
*-------------------------------------------------------------------------------
merge 1:1 snlkey year quarter using "comp_qtr.dta", keep(master match) nogen
replace mcap = mcap_cs if missing(mcap) & !missing(mcap_cs)
replace bval = debt_cs if missing(bval) & !missing(debt_cs)
replace lval = pref_cs if missing(lval) & !missing(pref_cs)
replace xint = xint_cs if missing(xint) & !missing(xint_cs)
replace dvp  = dvp_cs  if missing(dvp)  & !missing(dvp_cs)
drop mcap_cs debt_cs pref_cs xint_cs dvp_cs
* no preferred -> 0 (so theta_p==0 branch applies, not missing)
replace lval = 0 if missing(lval)
replace dvp  = 0 if missing(dvp)

*-------------------------------------------------------------------------------
* Step 3: returns on debt & preferred, lagged capital-structure weights
*-------------------------------------------------------------------------------
tsset snlkey fdate
gen rd = xint / L.bval
gen rp = dvp  / L.lval
replace rp = 0 if lval==0 | L.lval==0                  // no preferred -> no cost
gen TA      = mcap + bval + lval
gen theta_e = L.mcap / L.TA
gen theta_d = L.bval / L.TA
gen theta_p = L.lval / L.TA

*-------------------------------------------------------------------------------
* Step 4: merge equity return & compute unlevered return
*-------------------------------------------------------------------------------
merge 1:1 snlkey year quarter using "crsp_re_qtr.dta", keep(master match) nogen
tsset snlkey fdate

gen UnlevRet = theta_e*re + theta_d*rd + theta_p*rp
replace UnlevRet = theta_e*re + theta_d*rd if theta_p==0
replace UnlevRet = theta_e*re + theta_p*rp if theta_d==0
replace UnlevRet = theta_e*re              if theta_d==0 & theta_p==0
replace UnlevRet = UnlevRet*100                         // -> percent

label var re       "quarterly equity total return (fraction)"
label var UnlevRet "unlevered REIT return (%/qtr)"

* keep analysis rows: valid unlevered return + classification
keep snlkey cusip ticker ptype psub diversified us_cusip elected_yes ///
     year quarter fdate re rd rp theta_e theta_d theta_p ///
     bval lval mcap xint dvp UnlevRet
order snlkey ticker ptype fdate re UnlevRet
sort snlkey fdate
save "UnlevRet_qtr.dta", replace

*-------------------------------------------------------------------------------
* report
*-------------------------------------------------------------------------------
count
count if !missing(UnlevRet)
display as result "UnlevRet_qtr.dta written."
sum UnlevRet re if !missing(UnlevRet), detail
* leveraged vs unlevered, by core property type (quick face-validity)
preserve
    keep if !missing(UnlevRet) & us_cusip==1 & elected_yes==1
    collapse (mean) re UnlevRet (count) n=UnlevRet, by(ptype)
    replace re = re*100
    list ptype n re UnlevRet, sep(0) noobs
restore
