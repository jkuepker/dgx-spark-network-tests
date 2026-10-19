"""Build tweet charts from results.log (bench.sh output). Usage: charts.py RESULTS_LOG OUT_DIR"""
import re, sys, os
from collections import defaultdict
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

log, out = sys.argv[1], os.path.expanduser(sys.argv[2])

# Dark-mode tokens from the reference palette
SURF, INK, INK2, MUTED, GRID = "#1a1a19", "#f0efec", "#c3c2b7", "#8d8c85", "#33332f"
HALF_A, HALF_B = "#3987e5", "#d95926"  # PCIe half A (0000:01) / half B (0002:01)
REF = "#c3c2b7"

runs = defaultdict(list)  # label -> list of dict(dev->bw)
for line in open(log):
    m = re.match(r"(\S+) run \d+: (.*)  TOTAL=([\d.]+)", line)
    if not m:
        continue
    devs = dict(kv.split("=") for kv in m.group(2).split())
    runs[m.group(1)].append({k: float(v) for k, v in devs.items()})

def best(label):
    rs = runs[label]
    return max(rs, key=lambda d: sum(d.values()))

def halves(d):
    a = sum(v for k, v in d.items() if k.startswith("rocep1s0"))
    b = sum(v for k, v in d.items() if k.startswith("roceP2p1s0"))
    return a, b

cases = [
    ("switch-1half", "1 cable via CRS812\n1 interface only"),
    ("switch-cable", "1 cable via CRS812\nboth PCIe halves"),
    ("direct-cable", "1 cable direct\nboth PCIe halves"),
    ("both-cables", "2 cables\n(switch + direct)"),
]
cases = [c for c in cases if runs.get(c[0])]

plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 13, "text.color": INK,
    "axes.edgecolor": GRID, "axes.labelcolor": INK2,
    "xtick.color": INK2, "ytick.color": MUTED,
})

def style(ax, fig):
    fig.patch.set_facecolor(SURF); ax.set_facecolor(SURF)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.yaxis.grid(True, color=GRID, lw=0.8); ax.set_axisbelow(True)
    ax.tick_params(length=0)

# --- Chart 1: max total bandwidth, stacked by PCIe half ---
fig, ax = plt.subplots(figsize=(12, 6.75), dpi=150)
style(ax, fig)
x = range(len(cases)); w = 0.56; gap = 0.6  # 2px-ish surface gap between segments
for i, (key, name) in enumerate(cases):
    a, b = halves(best(key))
    ax.bar(i, a - gap / 2, w, color=HALF_A, edgecolor=SURF, linewidth=1.5)
    if b:
        ax.bar(i, b - gap / 2, w, bottom=a + gap / 2, color=HALF_B, edgecolor=SURF, linewidth=1.5)
    tot = a + b
    ax.text(i, tot + 4, f"{tot:.1f} Gb/s", ha="center", va="bottom", fontsize=16, fontweight="bold", color=INK)
ax.axhline(200, color=REF, lw=1.2, ls=(0, (4, 3)))
ax.text(-0.28, 202, "200 GbE port line rate", ha="left", va="bottom", fontsize=11, color=INK2)
ax.set_xticks(list(x)); ax.set_xticklabels([n for _, n in cases], fontsize=12.5, color=INK)
ax.set_ylim(0, 240); ax.set_ylabel("RDMA write bandwidth, Gb/s")
ax.legend(handles=[Patch(color=HALF_A, label="PCIe Gen5 x4 half A (0000:01)"),
                   Patch(color=HALF_B, label="PCIe Gen5 x4 half B (0002:01)")],
          loc="upper left", frameon=False, fontsize=11.5, labelcolor=INK2)
fig.suptitle("DGX Spark ↔ DGX Spark: a 2nd cable is +10%, not 2×", x=0.07, y=0.965, ha="left", fontsize=20, fontweight="bold", color=INK)
ax.set_title("Max over runs · RDMA ib_write_bw, 1 MiB msgs, 4 QPs/stream, 10 s · each PCIe x4 half caps at ~108 Gb/s",
             loc="left", fontsize=11.5, color=MUTED, pad=12)
fig.subplots_adjust(left=0.07, right=0.98, bottom=0.12, top=0.86)
p1 = os.path.join(out, "spark-cx7-max-bandwidth.png"); fig.savefig(p1, facecolor=SURF); plt.close(fig)

# --- Chart 2: every run, per case (consistency) ---
fig, ax = plt.subplots(figsize=(12, 6.75), dpi=150)
style(ax, fig)
for i, (key, name) in enumerate(cases):
    tots = [sum(d.values()) for d in runs[key]]
    n = len(tots)
    xs = [i + (j - (n - 1) / 2) * 0.07 for j in range(n)]
    ax.scatter(xs, tots, s=70, color=HALF_A, edgecolor=SURF, linewidth=2, zorder=3)
    above = min(tots) > 200
    ax.text(i, max(tots) + 7 if above else min(tots) - 7, f"max {max(tots):.1f} · min {min(tots):.1f}", ha="center", va="bottom" if above else "top", fontsize=11, color=INK2)
ax.axhline(200, color=REF, lw=1.2, ls=(0, (4, 3)))
ax.text(-0.4, 202, "200 GbE line rate", ha="left", va="bottom", fontsize=11, color=INK2)
ax.set_xticks(list(x)); ax.set_xticklabels([n for _, n in cases], fontsize=12.5, color=INK)
ax.set_xlim(-0.5, len(cases) - 0.3); ax.set_ylim(0, 240); ax.set_ylabel("Total Gb/s per run")
fig.suptitle("Every run, total bandwidth", x=0.07, y=0.965, ha="left", fontsize=20, fontweight="bold", color=INK)
ax.set_title("Each dot = one 10 s ib_write_bw run, spark1 → spark2", loc="left", fontsize=11.5, color=MUTED, pad=12)
fig.subplots_adjust(left=0.07, right=0.98, bottom=0.12, top=0.86)
p2 = os.path.join(out, "spark-cx7-all-runs.png"); fig.savefig(p2, facecolor=SURF); plt.close(fig)
print(p1); print(p2)
