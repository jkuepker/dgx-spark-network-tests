"""NCCL all-reduce bandwidth vs message size, per cable setup. Usage: nccl_chart.py NCCL_LOG OUT_DIR [OUT_DIR ...]"""
import os, re, sys
from collections import defaultdict
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

SURF, INK, INK2, MUTED, GRID = "#1a1a19", "#f0efec", "#c3c2b7", "#8d8c85", "#33332f"
SETUPS = [  # key, label, color (categorical slots 1-4, dark), label y-nudge in Gb/s
    ("switch-1hca", "1 cable, 1 RDMA device", "#3987e5", 0),
    ("switch-cable", "1 cable via CRS812, both halves", "#d95926", -4),
    ("direct-cable", "1 cable direct, both halves", "#199e70", 9),
    ("both-cables", "2 cables, 4 RDMA devices", "#c98500", -9),
]

best = defaultdict(dict)  # setup -> size -> max busbw GB/s over runs
for line in open(sys.argv[1]):
    m = re.match(r"(\S+) run\d+ RESULT size=(\d+) lat_us=[\d.]+ busbw_GBps=([\d.]+)", line)
    if m:
        s, size, bw = m.group(1), int(m.group(2)), float(m.group(3))
        best[s][size] = max(best[s].get(size, 0), bw)

plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 12.5, "text.color": INK,
                     "xtick.color": MUTED, "ytick.color": MUTED, "axes.labelcolor": INK2})
fig, ax = plt.subplots(figsize=(12, 6.75), dpi=150)
fig.patch.set_facecolor(SURF); ax.set_facecolor(SURF)
for s in ("top", "right", "left"):
    ax.spines[s].set_visible(False)
ax.spines["bottom"].set_color(GRID)
ax.yaxis.grid(True, color=GRID, lw=0.8); ax.set_axisbelow(True); ax.tick_params(length=0)

for key, label, color, nudge in SETUPS:
    pts = sorted(best[key].items())
    x = [p[0] for p in pts]; y = [p[1] * 8 for p in pts]
    ax.plot(x, y, color=color, lw=2, marker="o", ms=8, mec=SURF, mew=2, label=label)
    ax.text(x[-1] * 1.25, y[-1] + nudge, f"{y[-1]:.0f}", va="center", fontsize=13, fontweight="bold", color=INK)
ax.axhline(200, color=INK2, lw=1.2, ls=(0, (4, 3)))
ax.text(4096, 203, "200 GbE line rate", va="bottom", fontsize=11, color=INK2)
ax.set_xscale("log", base=2)
ticks = sorted(best[SETUPS[0][0]])
ax.set_xticks(ticks)
ax.set_xticklabels(["" if t == (256 << 20) else f"{t >> 10} KB" if t < (1 << 20) else f"{t >> 20} MB" for t in ticks])
ax.set_xlim(ticks[0] / 1.5, ticks[-1] * 2.6)
ax.set_ylim(0, 230); ax.set_ylabel("All-reduce bus bandwidth, Gb/s"); ax.set_xlabel("message size")
ax.legend(loc="lower right", frameon=False, labelcolor=INK2, fontsize=11.5)
fig.suptitle("NCCL across 2 Sparks: a 2nd cable doesn't help", x=0.07, y=0.965, ha="left",
             fontsize=20, fontweight="bold", color=INK)
fig.text(0.07, 0.905, "torch all-reduce bf16, NCCL 2.29.7, max of 3 runs · both PCIe halves double it; 4 devices is slightly slower · 4 KB latency ~16-18 µs everywhere",
         fontsize=11, color=MUTED)
fig.subplots_adjust(left=0.07, right=0.97, bottom=0.1, top=0.86)
for o in sys.argv[2:]:
    p = os.path.join(os.path.expanduser(o), "spark-nccl-allreduce.png"); fig.savefig(p, facecolor=SURF); print(p)
