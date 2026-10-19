"""Chart: every cage/rail combination, one way and both directions at once. Best of runs.
Render: uv run --with matplotlib python rails_chart.py results/2026-10-18-rails-duplex.log results/2026-10-19-rails-bidir.log charts
Usage: rails_chart.py ONEWAY_LOG BIDIR_LOG OUT_DIR [OUT_DIR ...]
ONEWAY_LOG: rails.sh + duplex.sh output. BIDIR_LOG: BIDIR=1 rails.sh output (TOTAL = out + in)."""
import os, re, sys
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

SURF, PANEL, INK, INK2, MUTED, GRID = "#1a1a19", "#222220", "#f0efec", "#c3c2b7", "#8d8c85", "#33332f"
ONE, TWO, DUP = "#d95926", "#3987e5", "#199e70"  # 1 PCIe link, 2 PCIe links, both directions


def best_of(path):
    best = {}
    for line in open(path):
        m = re.match(r"(\S+) run \d+.*TOTAL=([\d.]+) Gb/s", line) or re.match(r"(two-cable) \d+: BOTH-WAYS TOTAL=([\d.]+)", line)
        if m:
            best[m[1]] = max(best.get(m[1], 0), float(m[2]))
    return best


one, both = best_of(sys.argv[1]), best_of(sys.argv[2])
rows = [  # key, cables, rails, PCIe links, colour
    ("1cage-1rail-linkA", "1 cable", "1 rail", "link A", ONE),
    ("2cages-2rails-sameLinkA", "2 cables", "2 rails", "both on link A", ONE),
    ("1cage-2rails-linkA+B", "1 cable", "2 rails", "links A + B", TWO),
    ("2cages-2rails-linkA+B", "2 cables", "2 rails", "links A + B", TWO),
    ("2cages-3rails", "2 cables", "3 rails", "A, A, B: unbalanced", TWO),
    ("2cages-4rails", "2 cables", "4 rails", "links A + B", TWO),
]
both["two-cable"] = one.get("two-cable", 0)

plt.rcParams.update({"font.family": "DejaVu Sans", "text.color": INK})
fig = plt.figure(figsize=(16, 9.5), dpi=150); fig.patch.set_facecolor(SURF)
ax = fig.add_axes([0.27, 0.11, 0.66, 0.73]); ax.set_facecolor(SURF)
H = 0.36
bars = []  # (y, value, colour, suffix)
for i, (key, cab, rails, links, c) in enumerate(rows):
    bars.append((i - H / 2, one.get(key, 0), c, " one way"))
    bars.append((i + H / 2, both.get(key, 0), DUP, " both ways"))
    ax.text(-0.39, i - 0.13, f"{cab} · {rails}", transform=ax.get_yaxis_transform(), fontsize=13.5, weight="bold", va="center")
    ax.text(-0.39, i + 0.2, links, transform=ax.get_yaxis_transform(), fontsize=11, color=INK2, va="center")
yl = len(rows) + 0.3
bars.append((yl, both["two-cable"], DUP, " both ways"))
ax.text(-0.39, yl - 0.13, "2 cables · one per direction", transform=ax.get_yaxis_transform(), fontsize=13.5, weight="bold", va="center")
ax.text(-0.39, yl + 0.2, "spark1 sends on one, spark2 on the other", transform=ax.get_yaxis_transform(), fontsize=11, color=INK2, va="center")
top = max(v for _, v, _, _ in bars) or 430
for yi, v, c, suf in bars:
    ax.barh(yi, v, color=c, height=H * 0.92)
    ax.text(v + 4, yi, f"{v:.0f}" if v else "pending", va="center", fontsize=14, weight="bold", color=INK if v else MUTED)
    ax.text(v + 4 + top * 0.055, yi, suf.strip(), va="center", fontsize=10, color=MUTED)
ax.invert_yaxis(); ax.set_xlim(0, top * 1.18)
for s in ("top", "right", "left"):
    ax.spines[s].set_visible(False)
ax.spines["bottom"].set_color(GRID); ax.tick_params(colors=MUTED, length=0, labelsize=11)
ax.set_yticks([]); ax.xaxis.grid(True, color=GRID, lw=0.8); ax.set_axisbelow(True)
ax.axvline(200, color=MUTED, lw=1, ls=":"); ax.text(201, -0.6, "one 200G cable, one way", fontsize=9.5, color=MUTED)
ax.set_xlabel("Gb/s, best of 3 runs", color=MUTED, fontsize=11)

fig.text(0.04, 0.935, "The PCIe links set the speed, not the cables", fontsize=24, weight="bold")
fig.text(0.04, 0.892, "spark1 → spark2. \"Both ways\" = sending + receiving at the same time, added together. "
         "ib_write_bw, RoCE v2, 1 MiB writes, 10 s runs.", fontsize=12.5, color=INK2)
for i, (c, t) in enumerate([(ONE, "one way, 1 PCIe x4 link"), (TWO, "one way, both PCIe x4 links"), (DUP, "both ways combined")]):
    fig.patches.append(plt.Rectangle((0.04 + i * 0.22, 0.035), 0.012, 0.022, color=c, transform=fig.transFigure))
    fig.text(0.057 + i * 0.22, 0.046, t, fontsize=11, color=INK2, va="center")

for d in sys.argv[3:]:
    p = os.path.join(d, "spark-cx7-rail-combos.png"); fig.savefig(p, facecolor=SURF); print(p)
