"""Explainer: what 2, 3 and 4 DGX Sparks get over ConnectX-7. Usage: setups_visual.py OUT_DIR [OUT_DIR ...]"""
import math, os, sys
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

SURF, PANEL, INK, INK2, MUTED, GRID = "#1a1a19", "#222220", "#f0efec", "#c3c2b7", "#8d8c85", "#33332f"
OUT, IN, SW = "#3987e5", "#d95926", "#8b6fd6"
TAG = {"measured": "#199e70", "reported": "#c9a227", "expected": "#8d8c85"}

# Numbers. measured: our 2 Sparks (results/). reported: a 3-Spark ring (64 KB writes).
# expected: our per-cable number applied to a switch.
ONE_CABLE = 196      # Gb/s one direction, 1 cable both rails, measured
NCCL_1CABLE = 178    # NCCL all-reduce bus bw, measured
TWO_CABLE = 217      # one direction, 2 cables 4 rails, measured
RING_EACH = 185      # 3-Spark ring, per direction per Spark, reported
RING_BOTH = 370
ONE_CABLE_BOTH = 387 # both directions at once, added, 1 cable both rails, measured (ib_write_bw -b)
TWO_CABLE_BOTH = 393                  # same, 2 cables 4 rails, measured

plt.rcParams.update({"font.family": "DejaVu Sans", "text.color": INK})
fig = plt.figure(figsize=(16, 9), dpi=150)
fig.patch.set_facecolor(SURF)
ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(0, 160); ax.set_ylim(0, 90); ax.axis("off")


def rbox(x, y, w, h, fc, ec, lw=1.4, r=1.4, z=2):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle=f"round,pad=0,rounding_size={r}", fc=fc, ec=ec, lw=lw, zorder=z))


def spark(cx, cy, name, w=11, h=5.6):
    rbox(cx - w / 2, cy - h / 2, w, h, "#2c2c29", INK2, z=4)
    ax.text(cx, cy, name, ha="center", va="center", fontsize=12, weight="bold", zorder=5)


def arrow(x0, y0, x1, y1, c, lw=3.2):
    ax.annotate("", xy=(x1, y1), xytext=(x0, y0), zorder=3,
                arrowprops=dict(arrowstyle="-|>,head_length=0.7,head_width=0.4", color=c, lw=lw, shrinkA=0, shrinkB=0))


def num(x, y, text, c, fs=15, ha="center"):
    ax.text(x, y, text, ha=ha, va="center", fontsize=fs, weight="bold", color=c, zorder=6,
            bbox=dict(fc=PANEL, ec="none", pad=1.2))


def tag(x, y, kind):
    ax.text(x, y, kind, ha="center", va="center", fontsize=8.5, weight="bold", color=SURF, zorder=6,
            bbox=dict(boxstyle="round,pad=0.35", fc=TAG[kind], ec="none"))


def two_way(p, q, out_label, in_label, off=1.3, gap=7.5):
    """Two parallel arrows between Spark centres p and q: p->q (OUT colour) and q->p (IN colour)."""
    (x0, y0), (x1, y1) = p, q
    d = math.hypot(x1 - x0, y1 - y0); ux, uy = (x1 - x0) / d, (y1 - y0) / d; nx, ny = -uy, ux
    s = (x0 + ux * gap + nx * off, y0 + uy * gap + ny * off); e = (x1 - ux * gap + nx * off, y1 - uy * gap + ny * off)
    arrow(*s, *e, OUT)
    s2 = (x1 - ux * gap - nx * off, y1 - uy * gap - ny * off); e2 = (x0 + ux * gap - nx * off, y0 + uy * gap - ny * off)
    arrow(*s2, *e2, IN)
    return (x0 + x1) / 2, (y0 + y1) / 2, nx, ny


# --- header ---
ax.text(5, 84.5, "DGX Spark networking, in one picture", fontsize=24, weight="bold")
ax.text(5, 80, "Gb/s per Spark. Every Ethernet link sends and receives at the same time (full duplex).",
        fontsize=12.5, color=INK2)
for i, (k, what) in enumerate([("measured", "our 2 Sparks"), ("reported", "a 3-Spark ring"), ("expected", "not tested yet")]):
    tag(119, 85.5 - i * 3.6, k); ax.text(125, 85.5 - i * 3.6, what, fontsize=10, color=INK2, va="center")

# --- three panels ---
px = [5, 56.5, 108]; pw, py, ph = 47, 21, 54
titles = [("2 Sparks", "one cable, both rails"), ("3 Sparks, no switch", "a ring: two cables each"),
          ("4 Sparks + switch", "one cable each")]
for x, (t, sub) in zip(px, titles):
    rbox(x, py, pw, ph, PANEL, GRID, lw=1, z=1)
    ax.text(x + 2.5, py + ph - 4, t, fontsize=17, weight="bold")
    ax.text(x + 2.5, py + ph - 8, sub, fontsize=11.5, color=INK2)

# Panel 1: 2 Sparks, one cable
c = px[0] + pw / 2
A, B = (c - 14, 58), (c + 14, 58)
spark(*A, "Spark 1"); spark(*B, "Spark 2")
two_way(A, B, "", "", off=1.4)
num(c, 61.6, f"{ONE_CABLE} →", OUT); num(c, 54.4, f"← {ONE_CABLE}", IN)
tag(c, 49.4, "measured")
num(c, 46.0, f"= {ONE_CABLE_BOTH} both ways combined", INK, fs=14)
ax.text(px[0] + 2.5, 42.0, f"NCCL all-reduce: {NCCL_1CABLE} Gb/s", fontsize=12.5, weight="bold", color=TAG["measured"])
ax.text(px[0] + 2.5, 38.6, f"Add a 2nd cable: {TWO_CABLE} one way (+10%),\n{TWO_CABLE_BOTH} both ways. NCCL slightly slower.",
        fontsize=11, color=INK2, va="top")
ax.text(px[0] + 2.5, 29.5, "Set NCCL_IB_HCA to both rails of\nthe one cable, e.g. rocep1s0f1,roceP2p1s0f1",
        fontsize=10, color=MUTED, va="top", family="DejaVu Sans Mono")

# Panel 2: 3-Spark ring
c = px[1] + pw / 2
R = 11; cy = 50.5
pts = [(c + R * math.cos(math.radians(a)), cy + R * math.sin(math.radians(a))) for a in (90, 210, 330)]
for i in range(3):
    p, q = pts[i], pts[(i + 1) % 3]
    (x0, y0), (x1, y1) = p, q
    d = math.hypot(x1 - x0, y1 - y0); ux, uy = (x1 - x0) / d, (y1 - y0) / d
    arrow(x0 + ux * 7, y0 + uy * 7, x1 - ux * 7, y1 - uy * 7, OUT if i == 0 else INK2 if i == 1 else IN, 3)
for p, n in zip(pts, ["Spark A", "Spark B", "Spark C"]):
    spark(*p, n, w=10.5)
num((pts[0][0] + pts[1][0]) / 2 - 3.5, (pts[0][1] + pts[1][1]) / 2 + 1, f"{RING_EACH}", OUT, fs=13)
num((pts[2][0] + pts[0][0]) / 2 + 3.5, (pts[2][1] + pts[0][1]) / 2 + 1, f"{RING_EACH}", IN, fs=13)
ax.text(px[1] + 2.5, 37.5, f"Spark A sends {RING_EACH} on one cable\nand receives {RING_EACH} on the other:",
        fontsize=11.5, color=INK2, va="top")
num(px[1] + 2.5, 28.6, f"= {RING_BOTH} both ways combined", INK, fs=15, ha="left")
tag(px[1] + 41, 28.6, "reported")
ax.text(px[1] + 2.5, 24.4, f"Expected: sending alone still tops out near {TWO_CABLE}.", fontsize=10, color=MUTED)

# Panel 3: 4 Sparks on a switch
c = px[2] + pw / 2; cy = 52
rbox(c - 7, cy - 3, 14, 6, "#2a2440", SW, lw=1.8, z=4)
ax.text(c, cy, "Switch", ha="center", va="center", fontsize=12, weight="bold", zorder=5)
corners = [(c - 16, cy + 9.5), (c + 16, cy + 9.5), (c - 16, cy - 9.5), (c + 16, cy - 9.5)]
for i, p in enumerate(corners):
    q = (c - 6.5 if p[0] < c else c + 6.5, cy + (2 if p[1] > cy else -2))
    ax.plot([p[0] + (5.5 if p[0] < c else -5.5), q[0]], [p[1], q[1]], color=INK2, lw=3, zorder=3)
    spark(*p, f"Spark {i + 1}", w=10.5)
num(c, cy + 11.5, f"{ONE_CABLE} ⇄ {ONE_CABLE}", INK, fs=12.5)
num(c, cy - 11.5, "per Spark, each way", MUTED, fs=10)
num(px[2] + 2.5, 28.6, f"= ~{ONE_CABLE_BOTH} both ways combined", INK, fs=15, ha="left")
tag(px[2] + 41, 28.6, "expected")
tag(c, cy + 15.2, "expected")
ax.text(px[2] + 2.5, 37.5, "Each Spark still talks to the ring\nover one cable. Adding Sparks\ndoesn't need more cables per Spark.",
        fontsize=11.5, color=INK2, va="top")
ax.text(px[2] + 2.5, 24.4, "CRS812: 2× 200G + 2× 400G ports, likely room for 4.", fontsize=10, color=MUTED)

# --- rules strip ---
rules = [
    ("1", "One rail ≈ 108", "Each Spark's NIC sits on two PCIe\nx4 links, ~108 Gb/s each (~100 back)."),
    ("2", f"One cable ≈ {ONE_CABLE}", f"Use both rails of one cable.\nTwo cables only reach ~{TWO_CABLE}."),
    ("3", f"Both ways ≈ {ONE_CABLE_BOTH}", f"Send and receive at once on one\ncable: {ONE_CABLE_BOTH} combined, ~2× one way."),
]
rx = [5, 56.5, 108]
for x, (n, head, body) in zip(rx, rules):
    ax.add_patch(plt.Circle((x + 3, 13.2), 2.4, color=OUT, zorder=3))
    ax.text(x + 3, 13.2, n, ha="center", va="center", fontsize=13, weight="bold", zorder=4)
    ax.text(x + 7.5, 14.6, head, fontsize=14, weight="bold", va="center")
    ax.text(x + 7.5, 10.8, body, fontsize=10.5, color=INK2, va="top")
ax.text(5, 2.4, "ib_write_bw, RoCE v2, 1 MiB writes. NCCL 2.29.7 all-reduce bus bandwidth. 3-Spark ring numbers are from a shared chart (64 KB writes).",
        fontsize=8.5, color=MUTED)

for d in sys.argv[1:]:
    p = os.path.join(d, "spark-setups-explained.png")
    fig.savefig(p, facecolor=SURF); print(p)
