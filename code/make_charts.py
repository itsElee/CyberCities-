"""Cybercities: the three figures for the write-up. Run after score.py."""
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap

OUT = "."
r = pd.read_csv("data/results.csv").sort_values("rank_index").reset_index(drop=True)

SURFACE, INK, INK2, MUTED, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#8a8984", "#e6e5e1"
BLUE, BLUE_LIGHT, ORANGE = "#2a78d6", "#9ec5f4", "#eb6834"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9, "text.color": INK,
                     "axes.edgecolor": GRID, "axes.labelcolor": INK2, "xtick.color": INK2,
                     "ytick.color": INK2, "figure.facecolor": SURFACE, "axes.facecolor": SURFACE})


def title(fig, main, sub):
    fig.text(0.02, 0.985, main, ha="left", va="top", fontsize=12.5, fontweight="bold", color=INK)
    fig.text(0.02, 0.95, sub, ha="left", va="top", fontsize=9, color=INK2)


# ------------------------------------------------- 1. rank with stability ranges
fig, ax = plt.subplots(figsize=(8, 10.5))
fig.subplots_adjust(left=0.2, right=0.96, top=0.88, bottom=0.07)
y = np.arange(len(r))
ax.hlines(y, r["any_p05"], r["any_p95"], color=BLUE_LIGHT, lw=2, capstyle="round", zorder=1)
ax.hlines(y, r["near_p05"], r["near_p95"], color=BLUE, lw=5, capstyle="round", zorder=2)
ax.scatter(r["rank_index"], y, s=42, color=INK, edgecolor=SURFACE, linewidth=1.5, zorder=3)
ax.set_yticks(y, r["short"])
ax.invert_yaxis()
ax.set_xlim(0.5, 40.5)
ax.set_xticks([1, 5, 10, 15, 20, 25, 30, 35, 40])
ax.xaxis.tick_top()
ax.set_xlabel("Rank (1 = most cyberpunk)", labelpad=8)
ax.xaxis.set_label_position("top")
ax.grid(axis="x", color=GRID, lw=0.8)
ax.set_axisbelow(True)
for s in ["right", "bottom", "left"]:
    ax.spines[s].set_visible(False)
ax.tick_params(length=0)
ax.axhspan(-0.5, 3.5, color="#f0efec", zorder=0)
title(fig, "Four metros stay near the top under most weightings; who is #1 depends on the weights",
      "Rank of each metro with the chosen weights, and its range when the pillar weights are randomized 1,000 times")
fig.text(0.2, 0.025, "●  rank with chosen weights      ━  90% range, weights near ours      ─  90% range, any weights",
         fontsize=8.5, color=INK2)
fig.savefig(f"figures/fig1_rank_stability.png", dpi=200)
plt.close(fig)

# -------------------------------------------------------- 2. pillar heatmap
P = ["tech", "efficiency", "depth", "pressure"]
labels = ["High tech", "Efficiency\n& access", "Economic\ndepth", "Pressure &\ninequality"]
cmap = LinearSegmentedColormap.from_list("div", ["#d03b3b", "#ec9a8f", "#f0efec", "#86b6ef", "#1c5cab"])
vals = r[P].clip(-2, 2).to_numpy()
fig, ax = plt.subplots(figsize=(6.6, 11))
fig.subplots_adjust(left=0.27, right=0.97, top=0.865, bottom=0.04)
ax.imshow(vals, cmap=cmap, vmin=-2, vmax=2, aspect="auto")
for i in range(vals.shape[0]):
    for j in range(vals.shape[1]):
        v = r[P].iloc[i, j]
        ax.text(j, i, f"{v:+.1f}".replace("-0.0", "0.0").replace("+0.0", "0.0"), ha="center", va="center", fontsize=7.5,
                color="#ffffff" if abs(v) > 1.2 else INK)
ax.set_xticks(range(4), labels, fontsize=8.5)
ax.xaxis.tick_top()
ax.set_yticks(range(len(r)), [f"{k}. {s}" for k, s in zip(r["rank_index"], r["short"])])
ax.set_xticks(np.arange(-.5, 4, 1), minor=True)
ax.set_yticks(np.arange(-.5, len(r), 1), minor=True)
ax.grid(which="minor", color=SURFACE, lw=2)
ax.tick_params(which="both", length=0)
for s in ax.spines.values():
    s.set_visible(False)
title(fig, "Why each metro ranks where it does",
      "Pillar scores in standard deviations from the 40-metro average (blue above, red below)")
fig.savefig(f"figures/fig2_pillar_profiles.png", dpi=200)
plt.close(fig)

# ---------------------------------------------------- 3. high tech vs low life
fig, ax = plt.subplots(figsize=(8, 6.4))
fig.subplots_adjust(left=0.09, right=0.97, top=0.84, bottom=0.1)
ax.axhline(0, color=MUTED, lw=0.8)
ax.axvline(0, color=MUTED, lw=0.8)
ax.fill_between([0, 3.6], 0, 2.4, color="#f9ece7", zorder=0)
ax.text(3.5, 2.3, "High tech AND high pressure", ha="right", va="top", fontsize=9, color=INK2, style="italic")
ax.scatter(r["tech"], r["pressure"], s=46, color=BLUE, edgecolor=SURFACE, linewidth=1.5, zorder=3)
aus = r["short"] == "Austin"
ax.scatter(r.loc[aus, "tech"], r.loc[aus, "pressure"], s=70, color=ORANGE, edgecolor=SURFACE, linewidth=1.5, zorder=4)
offsets = {"San Jose": (-6, 8), "San Francisco": (6, 4), "Seattle": (6, -10), "Washington": (6, 2),
           "Austin": (8, 4), "Raleigh": (6, 4), "Atlanta": (6, 5), "Dallas": (6, -11), "Miami": (6, 2),
           "Tampa": (6, 2), "Orlando": (-6, 6), "Houston": (6, -2), "New York": (-6, 6),
           "Riverside": (6, 2), "Las Vegas": (6, 2), "Pittsburgh": (6, -6)}
for _, row in r[r["short"].isin(offsets)].iterrows():
    dx, dy = offsets[row["short"]]
    ax.annotate(row["short"], (row["tech"], row["pressure"]), xytext=(dx, dy), textcoords="offset points",
                fontsize=8.5, color=INK, ha="right" if dx < 0 else "left")
ax.set_xlim(-2.3, 3.6)
ax.set_ylim(-1.3, 2.4)
ax.set_xlabel("High-tech pillar score (SD from average)")
ax.set_ylabel("Pressure & inequality pillar score (SD from average)")
ax.grid(color=GRID, lw=0.8)
ax.set_axisbelow(True)
for s in ["top", "right"]:
    ax.spines[s].set_visible(False)
ax.tick_params(length=0)
rho = r["tech"].corr(r["pressure"], method="spearman")
title(fig, "\"High tech, low life\" is rare: tech hubs and pressure cookers are different cities",
      f"Each dot is one of the 40 metros. Correlation between the two pillars: {rho:+.2f} (essentially none)")
fig.savefig(f"figures/fig3_tech_vs_pressure.png", dpi=200)
plt.close(fig)
print("charts written")
