"""Thermal charts from a thermal_run.sh output dir. Usage: thermal_charts.py RUN_DIR OUT_DIR [OUT_DIR ...]"""
import csv, os, sys
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

SURF, INK, INK2, MUTED, GRID = "#1a1a19", "#f0efec", "#c3c2b7", "#8d8c85", "#33332f"
S1, S2 = "#3987e5", "#d95926"  # spark1, spark2 (categorical slots 1-2, dark)
BAND = {"rdma": "#2a2a27", "nccl": "#24302b"}

run, outs = sys.argv[1], sys.argv[2:]

def load(path):
    with open(path) as f:
        rows = list(csv.DictReader(f))
    return rows

temps = {h: load(os.path.join(run, f"temps-{h}.csv")) for h in ("spark1", "spark2")}
phases, open_ = [], {}
for r in load(os.path.join(run, "phases.csv")):
    t = float(r["ts"])
    if r["event"] == "start":
        open_[r["phase"]] = t
    else:
        phases.append((r["phase"], open_.pop(r["phase"]), t))
t0 = phases[0][1]

def series(h, col):
    rows = temps[h]
    return [(float(r["ts"]) - t0) / 60 for r in rows], [float(r[col]) for r in rows]

def nic_col(h):
    return next(k for k in temps[h][0] if k.startswith("nic_"))

def mean_in(h, col, a, b):
    v = [float(r[col]) for r in temps[h] if a <= float(r["ts"]) <= b]
    return sum(v) / len(v) if v else float("nan")

plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 12.5, "text.color": INK,
                     "xtick.color": MUTED, "ytick.color": MUTED, "axes.labelcolor": INK2})

def style(ax):
    ax.set_facecolor(SURF)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.yaxis.grid(True, color=GRID, lw=0.8); ax.set_axisbelow(True); ax.tick_params(length=0)

SHORT = {"rdma-switch-1half": "1 iface", "rdma-switch-cable": "switch\ncable", "rdma-direct-cable": "direct\ncable",
         "rdma-both-cables": "2 cables", "nccl-sweep": "NCCL\nsweep"}

# --- Chart 1: time series, NIC temp (top) and GPU power (bottom), phases shaded ---
fig, (a1, a2) = plt.subplots(2, 1, figsize=(12, 6.75), dpi=150, sharex=True,
                             gridspec_kw=dict(height_ratios=[2, 1], hspace=0.12))
fig.patch.set_facecolor(SURF)
for ax in (a1, a2):
    style(ax)
    for name, a, b in phases:
        if name.startswith(("rdma", "nccl")):
            ax.axvspan((a - t0) / 60, (b - t0) / 60, color=BAND["nccl" if name.startswith("nccl") else "rdma"], lw=0)
for h, c in (("spark1", S1), ("spark2", S2)):
    x, y = series(h, nic_col(h)); a1.plot(x, y, color=c, lw=2, label=h)
    x, y = series(h, "gpu_w"); a2.plot(x, y, color=c, lw=2)
lo = min(min(series(h, nic_col(h))[1]) for h in temps); hi = max(max(series(h, nic_col(h))[1]) for h in temps)
a1.set_ylim(lo - 3, hi + 6)
for name, a, b in phases:
    if name in SHORT:
        a1.text((a + b) / 2 / 60 - t0 / 60, hi + 5.5, SHORT[name], ha="center", va="top", fontsize=10, color=INK2)
a1.set_ylabel("ConnectX-7 °C"); a2.set_ylabel("GPU W"); a2.set_xlabel("minutes")
a1.legend(loc="upper left", frameon=False, labelcolor=INK2)
fig.suptitle("NIC temperature during the cable tests", x=0.07, y=0.965, ha="left", fontsize=20, fontweight="bold", color=INK)
fig.text(0.07, 0.905, "Shaded = traffic (RDMA soaks 3 min each, then NCCL sweep). Gaps = idle/cooldown. On-chip mlx5 sensor; no transceiver temps without root.",
         fontsize=11, color=MUTED)
fig.subplots_adjust(left=0.07, right=0.98, bottom=0.09, top=0.86)
paths = [os.path.join(os.path.expanduser(o), "spark-cx7-thermal-timeline.png") for o in outs]
for p in paths: fig.savefig(p, facecolor=SURF)
plt.close(fig)

# --- Chart 2: NIC temp rise per RDMA soak (last 30 s of soak vs last 30 s before it) ---
soaks = [p for p in phases if p[0].startswith("rdma-")]
prev_end = {}
for i, p in enumerate(phases):
    if p[0].startswith("rdma-"):
        prev_end[p[0]] = phases[i - 1][2]
fig, ax = plt.subplots(figsize=(12, 6.75), dpi=150); fig.patch.set_facecolor(SURF); style(ax)
w = 0.36
for hi_, (h, c) in enumerate((("spark1", S1), ("spark2", S2))):
    col = nic_col(h)
    for i, (name, a, b) in enumerate(soaks):
        base = mean_in(h, col, prev_end[name] - 30, prev_end[name])
        hot = mean_in(h, col, b - 30, b)
        d = hot - base
        x = i + (hi_ - 0.5) * (w + 0.02)
        ax.bar(x, d, w, color=c, edgecolor=SURF, linewidth=1.5, label=h if i == 0 else None)
        ax.text(x, d + 0.08, f"+{d:.1f} °C", ha="center", va="bottom", fontsize=12.5, fontweight="bold", color=INK)
ax.set_xticks(range(len(soaks)))
ax.set_xticklabels([SHORT[n].replace("\n", " ") for n, _, _ in soaks], fontsize=13, color=INK)
ax.set_ylabel("NIC temp rise, °C"); ax.legend(handles=[plt.Rectangle((0,0),1,1,color=S1), plt.Rectangle((0,0),1,1,color=S2)], labels=["spark1 (sender)", "spark2 (receiver)"], loc="upper left", frameon=False, labelcolor=INK2)
ax.set_ylim(0, max(ax.get_ylim()[1], 1) * 1.15)
fig.suptitle("NIC heat from traffic, per cable setup", x=0.07, y=0.965, ha="left", fontsize=20, fontweight="bold", color=INK)
ax.set_title("Last 30 s of a 3-min RDMA soak minus the 30 s before it · spark1 sends, spark2 receives · 2-cable soak still climbing at 3 min",
             loc="left", fontsize=11.5, color=MUTED, pad=12)
fig.subplots_adjust(left=0.07, right=0.98, bottom=0.1, top=0.86)
for o in outs:
    p = os.path.join(os.path.expanduser(o), "spark-cx7-thermal-rise.png"); fig.savefig(p, facecolor=SURF); paths.append(p)
for p in paths: print(p)
