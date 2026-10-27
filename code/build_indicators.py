"""Cybercities: build the indicator table for the 40 largest US metros.

Reads the raw downloads, computes each indicator, and writes indicators.csv
(one row per metro). Run: python build_indicators.py <raw_folder>
"""
import glob, os, sys, zipfile
import pandas as pd

RAW = sys.argv[1]
OUT = "data"
GEO = "metropolitan statistical area/micropolitan statistical area"


def num(s):
    return pd.to_numeric(s.astype(str).str.replace(",", ""), errors="coerce")


metros = pd.read_csv(f"{OUT}/metros_top40.csv", dtype={"cbsa_code": str})
codes = set(metros["cbsa_code"])
ind = metros[["rank", "metro", "cbsa_code", "pop_2025", "growth_2020_2025_pct"]].copy()

# ---------------------------------------------------------------- ACS 2024
acs = pd.read_csv(f"{RAW}/acs_2024.csv", dtype=str).rename(columns={GEO: "cbsa_code"})
acs = acs[acs["cbsa_code"].isin(codes)].copy()
for c in acs.columns:
    if c.startswith("B"):
        acs[c] = num(acs[c])
commuters = acs["B08301_001E"] - acs["B08301_021E"]          # workers minus work-from-home
acs["pop_2024"] = acs["B01003_001E"]
acs["transit_walk_share"] = (acs["B08301_010E"] + acs["B08301_019E"]) / commuters * 100
acs["commute_minutes"] = acs["B08013_001E"] / commuters
acs["gini"] = acs["B19083_001E"]
rent_base = acs["B25070_001E"] - acs["B25070_011E"]           # renters where burden is computable
acs["rent_burden_share"] = acs[["B25070_007E", "B25070_008E", "B25070_009E", "B25070_010E"]].sum(axis=1) / rent_base * 100
ind = ind.merge(acs[["cbsa_code", "pop_2024", "transit_walk_share", "commute_minutes", "gini", "rent_burden_share"]],
                on="cbsa_code", how="left")

# ------------------------------------------------- NTD 2024: rail + built-up density
ntd = pd.read_csv(f"{RAW}/ntd_by_mode.csv", dtype=str)
ntd = ntd[(ntd["Report Year"] == "2024") & (ntd["Time Period"] == "Annual Total")].copy()
ntd["drm"] = num(ntd["Directional Route Miles"])

# Principal urbanized area (2020 Census) of each metro, as named in the NTD
PRINCIPAL_UZA = {
    "35620": "New York--Jersey City--Newark, NY--NJ", "31080": "Los Angeles--Long Beach--Anaheim, CA",
    "16980": "Chicago, IL--IN", "19100": "Dallas--Fort Worth--Arlington, TX", "26420": "Houston, TX",
    "12060": "Atlanta, GA", "47900": "Washington--Arlington, DC--VA--MD", "33100": "Miami--Fort Lauderdale, FL",
    "37980": "Philadelphia, PA--NJ--DE--MD", "38060": "Phoenix--Mesa--Scottsdale, AZ", "14460": "Boston, MA--NH",
    "40140": "Riverside--San Bernardino, CA", "41860": "San Francisco--Oakland, CA", "19820": "Detroit, MI",
    "42660": "Seattle--Tacoma, WA", "33460": "Minneapolis--St. Paul, MN", "45300": "Tampa--St. Petersburg, FL",
    "41740": "San Diego, CA", "19740": "Denver--Aurora, CO", "36740": "Orlando, FL", "16740": "Charlotte, NC--SC",
    "12580": "Baltimore, MD", "41180": "St. Louis, MO--IL", "41700": "San Antonio, TX", "12420": "Austin, TX",
    "38900": "Portland, OR--WA", "40900": "Sacramento, CA", "38300": "Pittsburgh, PA",
    "29820": "Las Vegas--Henderson--Paradise, NV", "17140": "Cincinnati, OH--KY", "28140": "Kansas City, MO--KS",
    "18140": "Columbus, OH", "26900": "Indianapolis, IN", "34980": "Nashville-Davidson, TN", "17410": "Cleveland, OH",
    "41940": "San Jose, CA", "47260": "Virginia Beach--Norfolk, VA", "27260": "Jacksonville, FL",
    "39300": "Providence, RI--MA", "39580": "Raleigh, NC",
}
# Secondary urbanized areas inside a metro that run rail service
EXTRA_RAIL_UZA = {"Denton--Lewisville, TX": "19100"}

uza = ntd[["UZA Name", "UZA Population", "UZA Area Sq Miles"]].drop_duplicates("UZA Name").copy()
uza["uza_density"] = num(uza["UZA Population"]) / num(uza["UZA Area Sq Miles"])
dens = pd.DataFrame({"cbsa_code": list(PRINCIPAL_UZA), "UZA Name": list(PRINCIPAL_UZA.values())}).merge(uza, on="UZA Name", how="left")
ind = ind.merge(dens[["cbsa_code", "UZA Name", "uza_density"]].rename(columns={"UZA Name": "principal_uza"}),
                on="cbsa_code", how="left")

RAIL = ["HR", "LR", "CR", "SR", "YR", "MG"]   # heavy, light, commuter, streetcar, hybrid rail, automated guideway
rail = ntd[ntd["Mode"].isin(RAIL)].groupby("UZA Name")["drm"].sum()
uza_to_cbsa = {v: k for k, v in PRINCIPAL_UZA.items()} | EXTRA_RAIL_UZA
rail_cbsa = rail.rename(index=uza_to_cbsa)
rail_cbsa = rail_cbsa[rail_cbsa.index.isin(codes)].groupby(level=0).sum()
ind["rail_route_miles"] = ind["cbsa_code"].map(rail_cbsa).fillna(0)
ind["rail_miles_per_100k"] = ind["rail_route_miles"] / ind["pop_2024"] * 100_000

# ------------------------------------------------------------------ CBP 2023
cbp = pd.read_csv(f"{RAW}/cbp_2023.csv", dtype=str)
# Cleveland's code changed in 2023 (17460 -> 17410), so it was fetched separately with the new code
if os.path.exists(f"{RAW}/cbp_cleveland.csv"):
    cbp = pd.concat([cbp, pd.read_csv(f"{RAW}/cbp_cleveland.csv", dtype=str)], ignore_index=True)
cbp = cbp.rename(columns={GEO: "cbsa_code"})
cbp["ESTAB"], cbp["EMP"] = num(cbp["ESTAB"]), num(cbp["EMP"])
total = cbp[cbp["NAICS2017"] == "00"].set_index("cbsa_code")
ind["establishments"] = ind["cbsa_code"].map(total["ESTAB"])
ind["employment_cbp"] = ind["cbsa_code"].map(total["EMP"])
ind["businesses_per_1000"] = ind["establishments"] / ind["pop_2024"] * 1000

six = cbp[cbp["NAICS2017"].str.fullmatch(r"\d{6}") & (cbp["ESTAB"] > 0)]
ind["distinct_industries"] = ind["cbsa_code"].map(six.groupby("cbsa_code")["NAICS2017"].nunique())

AMENITY = ["44-45", "722", "812"]          # retail, food and drink, personal services
amen = cbp[cbp["NAICS2017"].isin(AMENITY)].groupby("cbsa_code")["ESTAB"].sum()
ind["amenity_estab"] = ind["cbsa_code"].map(amen)
# Per resident, not per square mile: a per-area version was 0.94 correlated with density (double counting)
ind["amenities_per_1000"] = ind["amenity_estab"] / ind["pop_2024"] * 1000

TECH = ["3341", "3342", "3344", "5112", "5182", "519130", "5415"]
tech = cbp[cbp["NAICS2017"].isin(TECH)]
ind["tech_industry_emp"] = ind["cbsa_code"].map(tech.groupby("cbsa_code")["EMP"].sum())
ind["tech_industry_share"] = ind["tech_industry_emp"] / ind["employment_cbp"] * 100
suppressed = tech[(tech["EMP"] == 0) & (tech["ESTAB"] > 0)]

# ------------------------------------------- BFS: business applications by county
bfs = pd.read_excel(f"{RAW}/bfs_county_apps_annual.xlsx", header=2, dtype=str)
bfs["fips"] = bfs["state_fips"].str.zfill(2) + bfs["county_fips"].str.zfill(3)
lst = pd.read_excel(f"{RAW}/list1_2023.xlsx", header=2, dtype=str).dropna(subset=["FIPS County Code"])
lst["fips"] = lst["FIPS State Code"].str.zfill(2) + lst["FIPS County Code"].str.zfill(3)
county_cbsa = lst[lst["CBSA Code"].isin(codes)][["fips", "CBSA Code"]]
b = county_cbsa.merge(bfs, on="fips", how="left")
years = ["BA2023", "BA2024", "BA2025"]
for y in years:
    b[y] = num(b[y])
apps = b.groupby("CBSA Code")[years].sum(min_count=1).mean(axis=1)
ind["new_business_apps_per_1000"] = ind["cbsa_code"].map(apps) / ind["pop_2024"] * 1000
missing_counties = b[b["BA2025"].isna()]



# --------------------------------------------- BLS OEWS May 2025: tech occupations
oews_zip = glob.glob(f"{RAW}/*oesm25ma*.zip")
if oews_zip:
    z = zipfile.ZipFile(oews_zip[0])
    name = [n for n in z.namelist() if "MSA" in n.upper() and n.endswith(".xlsx")][0]
    oe = pd.read_excel(z.open(name), dtype=str)
    oe.columns = oe.columns.str.upper()
    oe = oe[oe["OCC_CODE"].isin(["00-0000", "15-0000"])].copy()
    oe["TOT_EMP"] = num(oe["TOT_EMP"])
    piv = oe.pivot_table(index="AREA", columns="OCC_CODE", values="TOT_EMP", aggfunc="sum")
    share = piv["15-0000"] / piv["00-0000"] * 100
    ind["tech_occ_share"] = ind["cbsa_code"].map(share)
    print("OEWS areas matched:", ind["tech_occ_share"].notna().sum(), "| unmatched:",
          ind.loc[ind["tech_occ_share"].isna(), "metro"].tolist())

# ------------------------------------------------ BEA 2024: county GDP summed to metros
bea_file = f"{RAW}/bea_county_gdp.csv"
if os.path.exists(bea_file):
    bea = pd.read_csv(bea_file, dtype=str)
    bea = bea[bea["LineCode"].str.strip() == "3"].copy()       # current-dollar GDP, thousands of dollars
    bea["gdp"] = num(bea["2024"])
    gdp_by_fips = bea.set_index("GeoFIPS")["gdp"]
    cc = lst[lst["CBSA Code"].isin(codes)][["fips", "CBSA Code", "County/County Equivalent"]].copy()
    cc["gdp"] = cc["fips"].map(gdp_by_fips)
    # BEA merges most Virginia independent cities into combination areas (codes 519xx); map those by name
    combos = bea[bea["GeoFIPS"].str.startswith("519")]
    for _, row in combos.iterrows():
        parts = [p.strip() for p in row["GeoName"].replace(", VA*", "").replace(", VA", "").replace("+", ",").split(",")]
        hits = cc[(cc["fips"].str.startswith("51")) & cc["County/County Equivalent"].str.replace(" County", "").str.replace(" city", " City").isin(parts)]
        if len(hits):
            first = hits.index[0]
            cc.loc[hits.index, "gdp"] = 0.0
            cc.loc[first, "gdp"] = row["gdp"]
    gdp = cc.groupby("CBSA Code")["gdp"].sum(min_count=1)
    ind["gdp_total"] = ind["cbsa_code"].map(gdp) * 1000
    ind["gdp_per_capita"] = ind["gdp_total"] / ind["pop_2024"]
    unmatched = cc[cc["gdp"].isna()]
    print("BEA counties without GDP:", len(unmatched), unmatched[["fips", "County/County Equivalent"]].values.tolist()[:25])

complete = all(c in ind and ind[c].notna().all() for c in ["tech_occ_share", "gdp_total", "distinct_industries"])
ind.to_csv(f"{OUT}/indicators.csv" if complete else f"{OUT}/indicators_partial.csv", index=False)
print("Complete indicator table:", complete)

# ------------------------------------------------------------------ checks
pd.set_option("display.width", 250)
show = ["metro", "transit_walk_share", "commute_minutes", "rail_miles_per_100k", "uza_density",
        "amenities_per_1000", "distinct_industries", "businesses_per_1000", "tech_industry_share",
        "new_business_apps_per_1000", "gini", "rent_burden_share"]
print(ind[show].round(2).to_string(index=False))
print("\nMissing values per column:\n", ind[show].isna().sum()[lambda s: s > 0])
print("\nSuppressed tech-industry employment cells:", len(suppressed))
if len(suppressed):
    print(suppressed[["cbsa_code", "NAICS2017", "ESTAB", "EMP"]].to_string(index=False))
print("Counties without BFS data:", len(missing_counties), missing_counties["fips"].tolist()[:20])
print("Metro counties matched:", len(county_cbsa), "| metros:", county_cbsa["CBSA Code"].nunique())
