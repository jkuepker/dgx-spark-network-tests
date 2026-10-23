"""Measured RDMA rates for every cable/direction combo, times FP8 / NVFP4 payload compression ratios
("BF16-equivalent" Gb/s). The wire rate does not change; only the bytes per value do.
uv run --with matplotlib python compression_chart.py results/2026-10-19-rails-oneway-fwd.log \
  results/2026-10-19-rails-oneway-rev.log results/2026-10-18-rails-duplex.log results/2026-10-19-rails-bidir.log charts/
"""
import os, re, sys
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

SURF, INK, INK2, MUTED, GRID = "#1a1a19", "#f0efec", "#c3c2b7", "#8d8c85", "#33332f"
WIRE, FP8, FP4 = "#3987e5", "#2a5d9c", "#1f3c63"  # measured, x2, x3.56: one hue, extrapolations recede

def best_of(path, pattern):
    return max(float(m[1]) for line in open(path) if (m := re.match(pattern, line)))

fwd, rev, duplex, bidir = sys.argv[1:5]
run = lambda label: rf"{re.escape(label)} run \d+: .*TOTAL=([\d.]+) Gb/s"
rows = [  # (section, setup, direction, measured Gb/s)
    ("One direction", "1 cable, 2 rails", "spark1 -> spark2", best_of(fwd, run("1cage-2rails-linkA+B"))),
    ("One direction", "1 cable, 2 rails", "spark2 -> spark1", best_of(rev, run("1cage-2rails-linkA+B"))),
    ("One direction", "2 cables, 4 rails", "spark1 -> spark2", best_of(fwd, run("2cages-4rails"))),
    ("One direction", "2 cables, 4 rails", "spark2 -> spark1", best_of(rev, run("2cages-4rails"))),
    ("Both directions at once", "1 cable, 2 rails", "ib_write_bw -b", best_of(duplex, run("one-cable-bidir"))),
    ("Both directions at once", "2 cables, 1 per direction", "2 rails each", best_of(duplex, r"two-cable run \d+: BOTH-WAYS TOTAL=([\d.]+)")),
    ("Both directions at once", "2 cables, 4 rails", "ib_write_bw -b", best_of(bidir, run("2cages-4rails"))),
]
NVFP4 = 16 / 4.5  # 4-bit values + one FP8 scale per 16 values = 4.5 bits/value

plt.rcParams.update({"font.family": "DejaVu Sans", "text.color": INK})
fig = plt.figure(figsize=(16, 10), dpi=150); fig.patch.set_facecolor(SURF)
ax = fig.add_axes([0.22, 0.08, 0.72, 0.71]); ax.set_facecolor(SURF)

y, h, prev = 0.0, 0.62, None
for section, setup, direction, v in rows:
    if section != prev:
        y += 0.5 if prev else 0
        ax.text(-0.215, y, section, transform=ax.get_yaxis_transform(), va="center", fontsize=15, weight="bold")
        y += 0.75; prev = section
    for k, c in ((NVFP4, FP4), (2, FP8), (1, WIRE)):  # longest first so the measured bar sits on top
        ax.barh(y, v * k, height=h, color=c, edgecolor=SURF, linewidth=2)
    ax.text(v - 8, y, f"{v:.0f}", va="center", ha="right", fontsize=12.5, color=INK, weight="bold")
    ax.text(2 * v - 8, y, f"{2 * v:,.0f}", va="center", ha="right", fontsize=12.5, color=INK)
    ax.text(NVFP4 * v + 10, y, f"{NVFP4 * v:,.0f}", va="center", fontsize=12.5, color=INK)
    ax.text(-0.012, y - 0.13, setup, transform=ax.get_yaxis_transform(), ha="right", va="center", fontsize=13.5)
    ax.text(-0.012, y + 0.2, direction, transform=ax.get_yaxis_transform(), ha="right", va="center", fontsize=10.5, color=INK2)
    y += 1

ax.invert_yaxis(); ax.set_xlim(0, 1520); ax.set_ylim(y - 0.3, -0.5)
for s in ("top", "right", "left"): ax.spines[s].set_visible(False)
ax.spines["bottom"].set_color(GRID); ax.tick_params(colors=MUTED, length=0, labelsize=11)
ax.set_yticks([]); ax.xaxis.grid(True, color=GRID, lw=0.8); ax.set_axisbelow(True)
ax.set_xlabel("Gb/s (BF16-equivalent for FP8 / NVFP4: measured wire rate x compression ratio). Best of 3 runs.", color=MUTED, fontsize=11)

fig.text(0.04, 0.935, "Compression multiplies the link you already have", fontsize=24, weight="bold")
fig.text(0.04, 0.893, "DGX Spark <-> DGX Spark, ConnectX-7 RoCE v2, ib_write_bw, 1 MiB writes. Only the bright bar is on the wire; "
         "FP8 / NVFP4 are lossy and just carry fewer bits per value.", fontsize=12, color=INK2)
for n, (c, label) in enumerate([(WIRE, "Measured on the wire (BF16)"), (FP8, "FP8, x2"), (FP4, "NVFP4, x3.56 (4.5 bits/value)")]):
    x = (0.04, 0.24, 0.34)[n]
    fig.patches.append(plt.Rectangle((x, 0.838), 0.012, 0.022, color=c, transform=fig.transFigure))
    fig.text(x + 0.017, 0.849, label, va="center", fontsize=12, color=INK2)

for d in sys.argv[5:]:
    p = os.path.join(d, "spark-cx7-compression-equivalent.png"); fig.savefig(p, facecolor=SURF); print(p)
