"""Chart: a 2nd cable doubles network capacity, not the PCIe lanes. Usage: lanes_chart.py OUT_DIR [OUT_DIR ...]"""
import os, sys
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

SURF, INK, INK2, MUTED, GRID = "#1a1a19", "#f0efec", "#c3c2b7", "#8d8c85", "#33332f"
NET, PCIE, GOT = "#3987e5", "#d95926", "#199e70"  # categorical slots 1-3, dark mode

# PCIe Gen5: 32 GT/s per lane, 128b/130b encoding; GB10 -> ConnectX-7 is 2 x4 links
PCIE_RAW = 2 * 4 * 32 * 128 / 130
data = {  # measured max, ib_write_bw, results/2026-10-18-results.log
    "1 cable": dict(net=200, pcie=PCIE_RAW, got=196.1, netl="1 × 200 GbE port", pciel="8 PCIe lanes"),
    "2 cables": dict(net=400, pcie=PCIE_RAW, got=216.6, netl="2 × 200 GbE ports", pciel="still 8 PCIe lanes"),
}

plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 13, "text.color": INK,
                     "xtick.color": INK2, "ytick.color": MUTED, "axes.labelcolor": INK2})
fig, ax = plt.subplots(figsize=(12, 6.75), dpi=150)
fig.patch.set_facecolor(SURF); ax.set_facecolor(SURF)
for s in ("top", "right", "left"):
    ax.spines[s].set_visible(False)
ax.spines["bottom"].set_color(GRID)
ax.yaxis.grid(True, color=GRID, lw=0.8); ax.set_axisbelow(True); ax.tick_params(length=0)

w, gap = 0.26, 0.02
for gi, (name, d) in enumerate(data.items()):
    bars = [(d["net"], NET, d["netl"]), (d["pcie"], PCIE, d["pciel"]), (d["got"], GOT, "measured")]
    for bi, (v, c, sub) in enumerate(bars):
        x = gi + (bi - 1) * (w + gap)
        ax.bar(x, v, w, color=c, edgecolor=SURF, linewidth=1.5)
        ax.text(x, v + 6, f"{v:.0f}", ha="center", va="bottom", fontsize=16, fontweight="bold", color=INK)
        ax.text(x, v + 30, sub, ha="center", va="bottom", fontsize=10.5, color=INK2)
ax.set_xticks([0, 1]); ax.set_xticklabels(list(data), fontsize=15, color=INK)
ax.set_ylim(0, 470); ax.set_ylabel("Gb/s")
ax.legend(handles=[plt.Rectangle((0, 0), 1, 1, color=c) for c in (NET, PCIE, GOT)],
          labels=["Network capacity (cables)", "PCIe link NIC ↔ GB10 (2× Gen5 x4, raw)", "Achieved RDMA, spark1 → spark2"],
          loc="upper left", frameon=False, fontsize=11.5, labelcolor=INK2)
fig.suptitle("A 2nd cable doubles the network lanes, not the PCIe lanes", x=0.07, y=0.965, ha="left",
             fontsize=20, fontweight="bold", color=INK)
ax.set_title("DGX Spark ConnectX-7 hangs off GB10 by 2× PCIe Gen5 x4. One cable already uses both. Result: +10%, not 2×",
             loc="left", fontsize=11.5, color=MUTED, pad=12)
fig.subplots_adjust(left=0.07, right=0.98, bottom=0.1, top=0.86)
for out in sys.argv[1:]:
    p = os.path.join(os.path.expanduser(out), "spark-cx7-lanes.png")
    fig.savefig(p, facecolor=SURF); print(p)
