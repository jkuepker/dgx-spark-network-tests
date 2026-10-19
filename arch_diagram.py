"""Diagram: how one DGX Spark's ConnectX-7 hangs off the GB10 (2 PCIe x4 links, 4 functions, 2 cages).
Usage: arch_diagram.py OUT_DIR [OUT_DIR ...]"""
import os, sys
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

SURF, INK, INK2, MUTED, GRID = "#1a1a19", "#f0efec", "#c3c2b7", "#8d8c85", "#33332f"
LA, LB, CAGE, GOT, DUP = "#d95926", "#3987e5", "#8b6fd6", "#199e70", "#4cc9a0"  # link A, link B, cage, measured

plt.rcParams.update({"font.family": "DejaVu Sans", "text.color": INK})
fig = plt.figure(figsize=(14, 8.4), dpi=150)
fig.patch.set_facecolor(SURF)
ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(0, 140); ax.set_ylim(0, 84); ax.axis("off")


def box(x, y, w, h, title, sub="", edge=INK2, fill=SURF, fs=12, sfs=9.5, lw=1.6):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=1.2",
                                fc=fill, ec=edge, lw=lw, zorder=2))
    ty = y + h / 2 + (1.3 if sub else 0)
    ax.text(x + w / 2, ty, title, ha="center", va="center", fontsize=fs, weight="bold", zorder=3)
    if sub:
        ax.text(x + w / 2, y + h / 2 - 1.8, sub, ha="center", va="center", fontsize=sfs, color=INK2, zorder=3)


def line(x0, y0, x1, y1, c, lw=3):
    ax.plot([x0, x1], [y0, y1], color=c, lw=lw, solid_capstyle="round", zorder=1)


ax.text(4, 79.5, "DGX Spark: where the network bandwidth goes", fontsize=19, weight="bold")
ax.text(4, 75.6, "One Spark shown. Both Sparks are wired the same. Device names and PCIe addresses from /sys on spark1.",
        fontsize=10.5, color=MUTED)

# --- GB10 ---
box(4, 62, 86, 8, "GB10 SoC", "Grace CPU + Blackwell GPU, unified memory", fill="#24241f")

# --- two PCIe links ---
ax_, bx_ = 17, 63  # link box x
box(ax_ - 2, 49.5, 28, 7, "PCIe link A", "Gen5 x4  ·  0000:01:00", edge=LA)
box(bx_ - 2, 49.5, 28, 7, "PCIe link B", "Gen5 x4  ·  0002:01:00", edge=LB)
line(ax_ + 12, 62, ax_ + 12, 56.5, LA, 4); line(bx_ + 12, 62, bx_ + 12, 56.5, LB, 4)
ax.text(52, 59.2, "each link: 126 Gb/s raw  ·  ≈108 usable one way  ·  ≈198 both ways at once", ha="center", va="center",
        fontsize=9.5, color=INK2, bbox=dict(fc=SURF, ec="none", pad=2), zorder=3)

# --- ConnectX-7 with 4 functions ---
ax.add_patch(FancyBboxPatch((4, 19), 86, 25, boxstyle="round,pad=0,rounding_size=1.2",
                            fc="#202020", ec=MUTED, lw=1.2, ls="--", zorder=0))
ax.text(6, 41.6, "ConnectX-7  (4 PCIe functions = 4 RDMA devices = 4 \"rails\")", fontsize=10.5, color=INK2,
        zorder=3, bbox=dict(fc="#202020", ec="none", pad=1.5))
fx = [6, 26, 48, 68]; fw, fy, fh = 20, 30, 8
funcs = [("rocep1s0f0", ".0 on link A", LA), ("roceP2p1s0f0", ".0 on link B", LB),
         ("rocep1s0f1", ".1 on link A", LA), ("roceP2p1s0f1", ".1 on link B", LB)]
for x, (name, sub, c) in zip(fx, funcs):
    box(x, fy, fw, fh, name, sub, edge=c, fs=11, sfs=9)
# link -> function fan-out (the crossing is the point: each link feeds BOTH cages)
for x, c, src in [(fx[0], LA, ax_ + 12), (fx[2], LA, ax_ + 12), (fx[1], LB, bx_ + 12), (fx[3], LB, bx_ + 12)]:
    line(src, 49.5, x + fw / 2, fy + fh, c, 2.6)

# --- cages ---
box(6, 20.5, 40, 6.5, "Cage / port 0  ·  200 GbE QSFP", "enp1s0f0np0 + enP2p1s0f0np0", edge=CAGE, fs=11, sfs=9)
box(48, 20.5, 40, 6.5, "Cage / port 1  ·  200 GbE QSFP", "enp1s0f1np1 + enP2p1s0f1np1", edge=CAGE, fs=11, sfs=9)
for x in fx:
    line(x + fw / 2, fy, x + fw / 2, 27, CAGE, 2)

# --- cables ---
line(26, 20.5, 26, 11, INK2, 3); line(68, 20.5, 68, 11, INK2, 3)
box(10, 4, 32, 7, "Direct cable → spark2", "10.100.154.x / 10.100.155.x", fs=11, sfs=9)
box(52, 4, 32, 7, "MikroTik CRS812 → spark2", "10.100.152.x / 10.100.153.x", fs=11, sfs=9)

# --- right panel: bottleneck ladder ---
px = 96
ax.text(px, 69.5, "What caps each setup", fontsize=14, weight="bold")
ax.text(px, 66.4, "ib_write_bw, 1 MiB, measured, Gb/s", fontsize=9.5, color=MUTED)
ax.text(px + 31, 63.3, "one way", fontsize=9, color=MUTED, ha="right")
ax.text(px + 39.5, 63.3, "both ways", fontsize=9, color=DUP, ha="right")
BOTH4 = "393"  # 2 cages 4 rails, ib_write_bw -b, results/2026-10-19-rails-bidir.log
rows = [  # label, one way, both ways (out + in at once), why, colour
    ("1 rail", "108", "198", "one PCIe x4 link", LA),
    ("1 cage, 2 rails", "196", "387", "the 200 GbE cage", CAGE),
    ("2 cages, 4 rails", "217", BOTH4, "both x4 links (2 × ~108)", LB),
    ("NCCL, 1 cage 2 rails", "178", "", "all-reduce bus bw", GOT),
    ("NCCL, 2 cages 4 rails", "170", "", "more rails, same 2 links", GOT),
]
y = 59
for label, val, both, why, c in rows:
    ax.add_patch(FancyBboxPatch((px, y - 3.2), 41, 7.2, boxstyle="round,pad=0,rounding_size=1",
                                fc="#24241f", ec=GRID, lw=1))
    ax.add_patch(plt.Rectangle((px, y - 3.2), 0.9, 7.2, color=c))
    ax.text(px + 2.5, y + 1.3, label, fontsize=11, weight="bold", va="center")
    ax.text(px + 2.5, y - 1.5, why, fontsize=9.5, color=INK2, va="center")
    ax.text(px + 31, y, val, fontsize=17, weight="bold", ha="right", va="center", color=c)
    ax.text(px + 39.5, y, both or "—", fontsize=15 if both else 12, weight="bold", ha="right", va="center",
            color=DUP if both else MUTED)
    y -= 9
ax.text(px, y + 2.6, "Both ways = sending + receiving at the same time, added\n"
        "(ib_write_bw -b). NCCL all-reduce already runs both ways.", fontsize=9.5, color=INK2, va="top")
ax.text(px, 6.8, "Takeaway: the box has two PCIe x4 links,\nshared by both cages. A 2nd cable adds\n"
        "ports, not PCIe bandwidth.", fontsize=11, weight="bold", va="top", color=INK)

for d in sys.argv[1:]:
    p = os.path.join(d, "spark-cx7-architecture.png")
    fig.savefig(p, facecolor=SURF); print(p)
