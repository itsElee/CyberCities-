"""Cybercities: score, rank, and stress-test the cyberpunk index.

Input: indicators.csv (one row per metro). Output: results CSVs printed summary.
Run: python score.py <indicators.csv>
"""
import sys
import numpy as np
import pandas as pd

SRC = sys.argv[1]
OUT = "data"
rng = np.random.default_rng(2026)          # fixed seed so the results are reproducible

# pillar -> {indicator: (direction, weight inside the pillar)}
PILLARS = {
    "tech": {"tech_occ_share": (+1, 1), "tech_industry_share": (+1, 1)},
    "efficiency": {"transit_walk_share": (+1, 1), "commute_minutes": (-1, 1), "rail_miles_per_100k": (+1, 1),
                   "amenities_per_1000": (+1, 1), "uza_density": (+1, 2)},
    "depth": {"distinct_industries": (+1, 1), "businesses_per_1000": (+1, 1),
              "gdp_total": (+1, 1), "gdp_per_capita": (+1, 1)},
    "pressure": {"growth_2020_2025_pct": (+1, 1), "new_business_apps_per_1000": (+1, 1),
                 "gini": (+1, 1), "rent_burden_share": (+1, 1)},
}
BASE_W = {"tech": 0.30, "efficiency": 0.25, "depth": 0.20, "pressure": 0.25}
SKEW_LIMIT = 1.5   # indicators more lopsided than this get log-transformed so one extreme city can't dominate

df = pd.read_csv(SRC, dtype={"cbsa_code": str})
present = {p: {k: v for k, v in d.items() if k in df.columns and df[k].notna().all()} for p, d in PILLARS.items()}
skipped = [k for p, d in PILLARS.items() for k in d if k not in present[p]]
df["short"] = df["metro"].str.split(r"[-,]").str[0]
all_ind = [k for d in present.values() for k in d]
LOG = [k for k in all_ind if df[k].skew() > SKEW_LIMIT]


def zscores(frame, indicators):
    z = pd.DataFrame(index=frame.index)
    for p, d in indicators.items():
        for k, (sign, _) in d.items():
            x = frame[k].astype(float)
            if k in LOG:
                x = np.log1p(x)
            z[k] = sign * (x - x.mean()) / x.std()
    return z


def pillar_scores(z, indicators):
    out = pd.DataFrame(index=z.index)
    for p, d in indicators.items():
        if not d:
            continue
        w = pd.Series({k: wt for k, (_, wt) in d.items()})
        out[p] = (z[w.index] * w).sum(axis=1) / w.sum()
    return out


def index_from(pillars, weights):
    w = pd.Series(weights)[pillars.columns]
    return (pillars * w).sum(axis=1) / w.sum()


z = zscores(df, present)
pil = pillar_scores(z, present)
df = df.join(pil)
df["index"] = index_from(pil, BASE_W)
df["rank_index"] = df["index"].rank(ascending=False, method="min").astype(int)

# ------------------------------------------------ stability test 1: random weights
def rank_draws(alpha, n=1000):
    cols = list(pil.columns)
    W = rng.dirichlet(alpha, size=n)
    scores = pil[cols].to_numpy() @ W.T                     # metros x draws
    return pd.DataFrame(scores).rank(ascending=False, method="min")


cols = list(pil.columns)
near = rank_draws(np.array([BASE_W[c] for c in cols]) * 20)   # weights near our choice (about +/-8 points)
anyw = rank_draws(np.ones(len(cols)))                          # any weights at all
for name, R in [("near", near), ("any", anyw)]:
    df[f"{name}_median_rank"] = R.median(axis=1).to_numpy()
    df[f"{name}_p05"] = R.quantile(0.05, axis=1).to_numpy()
    df[f"{name}_p95"] = R.quantile(0.95, axis=1).to_numpy()
    df[f"{name}_top5_pct"] = (R <= 5).mean(axis=1).to_numpy() * 100
    df[f"{name}_top10_pct"] = (R <= 10).mean(axis=1).to_numpy() * 100

# ------------------------------------------- stability test 2: drop one indicator
drops = []
for p, d in present.items():
    for k in d:
        reduced = {pp: {kk: vv for kk, vv in dd.items() if kk != k} for pp, dd in present.items()}
        reduced = {pp: dd for pp, dd in reduced.items() if dd}
        zz = zscores(df, reduced)
        r = index_from(pillar_scores(zz, reduced), BASE_W).rank(ascending=False, method="min")
        top10 = df["rank_index"] <= 10
        drops.append({"dropped": k,
                      "spearman_vs_base": df["rank_index"].corr(r, method="spearman"),
                      "top10_still_top10": int(((r <= 10) & top10).sum()),
                      "max_shift_in_top10": int((r[top10] - df.loc[top10, "rank_index"]).abs().max()),
                      "new_number_1": df.loc[r.idxmin(), "short"]})
drops = pd.DataFrame(drops)

# ------------------------------------------------------------------- outputs
df.sort_values("rank_index").to_csv(f"{OUT}/results.csv", index=False)
drops.to_csv(f"{OUT}/drop_one_indicator.csv", index=False)
corr = df[[k for d in present.values() for k in d]].corr(method="spearman")
corr.to_csv(f"{OUT}/indicator_correlations.csv")

pd.set_option("display.width", 250)
print("Indicators used:", sum(len(d) for d in present.values()), "| skipped (missing):", skipped)
print("Log-transformed:", LOG)
print("Skewness:", df[[k for d in present.values() for k in d]].skew().round(1).to_dict())
show = ["rank_index", "short", "index"] + cols + ["near_p05", "near_p95", "any_p05", "any_p95", "any_top10_pct"]
print(df.sort_values("rank_index")[show].round(2).to_string(index=False))
print("\nDrop-one-indicator test:\n", drops.round(3).to_string(index=False))
hi = corr.where(np.triu(np.ones(corr.shape, bool), 1)).stack()
print("\nStrongest indicator correlations:\n", hi.abs().sort_values(ascending=False).head(6).round(2))
