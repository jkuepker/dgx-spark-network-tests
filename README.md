# DGX Spark network tests

RDMA bandwidth between spark1 (spark-4e77) and spark2 (spark-fa00) over ConnectX-7.

## Results (2026-10-18)

`ib_write_bw`, 1 MiB messages, 4 QPs per stream, 10 s per run, spark1 → spark2.

| Combination | Max Gb/s | Runs |
|---|---|---|
| 1 cable via CRS812, both PCIe halves | 196.08 | 5 |
| 1 cable direct, both PCIe halves | 196.08 | 5 |
| 2 cables (switch + direct) | 216.61 | 5 |
| 1 cable, 1 interface only | 107.8 | 3 |

One cable is capped by the 200 GbE port. Two cables are capped by PCIe: each Gen5 x4 half tops out at ~108 Gb/s.
Raw log: `results/2026-10-18-results.log`. Charts: `charts/`.

## NCCL all-reduce (2026-10-18)

torch all-reduce, bf16, NCCL 2.29.7 (MiaAI kit image), 4 KB–512 MB, max of 3 runs. `NCCL_IB_HCA` picks the devices.

| Setup | Max bus bw | 4 KB latency |
|---|---|---|
| 1 cable, 1 RDMA device | 11.8 GB/s (94 Gb/s) | 18 µs |
| 1 cable via CRS812, both halves | 22.2 GB/s (178 Gb/s) | 18 µs |
| 1 cable direct, both halves | 22.2 GB/s (178 Gb/s) | 16 µs |
| 2 cables, 4 devices | 21.2 GB/s (170 Gb/s) | 16 µs |

Listing both PCIe halves in `NCCL_IB_HCA` doubles NCCL bandwidth. A 2nd cable does not help NCCL, and 4 devices is slightly slower.
Log: `results/2026-10-18-thermal/nccl-results.log`. Chart: `charts/spark-nccl-allreduce.png`.

## Temperatures (2026-10-18)

3-min sustained RDMA soak per setup (spark1 sends, spark2 receives), 90 s cooldowns, 2 s sampling.
Sensors: ConnectX-7 on-chip `mlx5` hwmon, max ACPI thermal zone, GPU temp and power. Transceiver temps need root (`ethtool -m`), so they are not included.

| Setup | spark1 NIC rise | spark2 NIC rise |
|---|---|---|
| 1 interface | +3.1 °C | +1.1 °C |
| switch cable | +5.1 °C | +1.5 °C |
| direct cable | +4.2 °C | +1.7 °C |
| 2 cables | +9.7 °C (still climbing at 3 min, peak 61 °C) | +1.1 °C |

The sending side heats up. The receiving side barely moves.
Cables were plugged in for the whole run, so the idle heat of a plugged-in 2nd cable or transceiver is not measured.
Data: `results/2026-10-18-thermal/`. Charts: `charts/spark-cx7-thermal-*.png`. Run: `thermal/thermal_run.sh results/<dir>`, chart with `thermal/thermal_charts.py`.

### Reversed run: the heat is the benchmark's CPU polling, not the network

`REVERSE=1 thermal/thermal_run.sh` makes spark2 the sender. It adds two event-mode soaks (`ib_send_bw -e`, no busy-poll)
and a 4-core CPU spin with no traffic. Peak temps on spark2, the sender:

| Soak | SoC max | NIC max |
|---|---|---|
| idle | 43.8 °C | 47 °C |
| 2 cables, `ib_write_bw` (4 cores busy-polling) | 75.7 °C | 57 °C |
| 2 cables, event mode, same ~200 Gb/s for 397 s | 46.0 °C | 50 °C |
| 4 spinning cores, no traffic | 72.3 °C | 55 °C |

The heat follows the sender (spark1 stayed flat while receiving), and almost all of it is the perftest client spinning a core per stream.
Full-rate traffic alone adds about +2 °C SoC and +3 °C NIC. The event soaks ran ~390 s instead of 180 s because perftest's `-n` counts per QP (fixed in `bench.sh` since);
their rate was read from `port_xmit_data` counters (50.1 Gb/s per rail). NCCL is the same in both directions (max 177.4 vs 176.9 Gb/s via the switch, 178.0 vs 178.7 direct).
Data: `results/2026-10-18-thermal-reverse/`.

## Cable and rail combinations (2026-10-19)

`./rails.sh 3`, `BIDIR=1 ./rails.sh 3` and `./duplex.sh 3`. spark1 -> spark2 unless noted, best of 3 runs, Gb/s.
Both ways = `ib_write_bw -b`, sending and receiving at the same time, added together.

| Cables | Rails | PCIe links | One way | Both ways |
|---|---|---|---|---|
| 1 | 1 | A | 108.3 | 197.7 |
| 2 | 2, both on link A | A | 108.0 | 196.3 |
| 1 | 2 | A + B | 196.1 | 387.3 |
| 2 | 2, one per cable | A + B | 203.7 | 366.8 |
| 2 | 3 (A, A, B) | A + B, unbalanced | 152.9 | 283.2 |
| 2 | 4 | A + B | 216.6 | 393.2 |
| 2, one cable each way | 4 | A + B | | 387.2 (196.1 + 191.2) |

Data: `results/2026-10-18-rails-duplex.log` (one way, duplex), `results/2026-10-19-rails-bidir.log` (both ways).

Two cables on the same PCIe link get exactly one link's worth. One cable already does ~387 total when sending and receiving at once; 2 cables with 4 rails add 1.5% (393).
spark2 -> spark1 is a little slower on one rail (99.6) and on 4 rails (197.6), not on 1 cable (196.1).
Charts: `charts/spark-cx7-rail-combos.png`, `charts/spark-cx7-architecture.png` (`arch_diagram.py`), `charts/spark-setups-explained.png` (`setups_visual.py`).

## Follow-up: both directions, heat source, NCCL soak (2026-10-19)

`./rails.sh 3` and `REVERSE=1 ./rails.sh 3` (now with a link-B single rail), best of 3, one way, Gb/s:

| Rails | spark1 -> spark2 | spark2 -> spark1 |
|---|---|---|
| 1, link A | 108.33 | 99.63 |
| 1, link B | 108.33 | 99.61 |
| 2, both on link A | 108.01 | 99.49 |
| 2, one cable (A + B) | 196.08 | 196.08 |
| 2, one per cable (A + B) | 203.75 | 182.00 |
| 3 (A, B, A) | 152.67 | 135.94 |
| 4 | 216.60 | 197.72 |

spark2 -> spark1 caps each PCIe link at ~99.6 instead of ~108.3. One cable with both rails (98 per rail, port-limited) is unaffected. Both Sparks run kernel 6.17.0-1029-nvidia. Cause not found.
Data: `results/2026-10-19-rails-oneway-fwd.log`, `results/2026-10-19-rails-oneway-rev.log`.

`thermal/heat_source.sh` (and `REVERSE=1`): busy-poll vs event mode at the same rate, 4-core spin, 3-min NCCL soak (`nccl/ar_soak.py`, 256 MB).
`bench.sh` now also prints the sender's `port_xmit_data` rate (wire bytes, ~1.4% above perftest) for runs of 60 s or more, and event mode prints its result again.
Sender peaks: busy-poll 4 rails 78.4 / 81.9 °C SoC, event mode same traffic 48.9 / 46.7 °C, 4-core spin 74.2 / 73.4 °C (spark1 / spark2 sending; idle 46.0 / 46.8 °C).
The NCCL soak (175.2 / 175.8 Gb/s bus bw, NCCL 2.29.7) heats both Sparks to 67-69 °C SoC, 57-60 °C NIC.
Data: `results/2026-10-19-heat-fwd/`, `results/2026-10-19-heat-rev/`.

## Real model work: 2 rails vs 4 rails (2026-10-19)

`thermal/model_heat.sh 900`: Qwen3.8-Flash-Next TP=2 over both Sparks (qwen38-flash-next-cluster-recipe,
`myllmbox/qwen38-flash-next-cluster-vllm:v5.2`), the same looped load (streamed OpenAI-API requests: 1k + 8k prompts, 512 out, then 4 streams at once)
for 15 min per setup, 21-22 iterations each. Only `NCCL_IB_HCA` changes: A = `rocep1s0f1,roceP2p1s0f1` (1 cable),
B = all 4 rails (2 cables). Temperatures over the load window; tok/s are medians over all iterations.

| | A: 1 cable, 2 rails | B: 2 cables, 4 rails |
|---|---|---|
| spark1 SoC, peak / mean °C | 92.6 / 81.7 | 93.5 / 81.8 |
| spark1 NIC, peak / mean °C | 69 / 65.6 | 70 / 65.9 |
| spark2 SoC, peak / mean °C | 92.7 / 77.3 | 92.5 / 78.0 |
| spark2 NIC, peak / mean °C | 66 / 63.0 | 66 / 63.5 |
| GPU power, mean (each Spark) | ~40 W | ~40 W |
| Decode, 4 streams aggregate | 186.0 tok/s | 181.3 tok/s |
| Decode, 1 stream, 8k prompt | 79.1 tok/s | 81.6 tok/s |
| Prefill, 8k prompt | 4,283 tok/s | 4,280 tok/s |
| TTFT, 8k prompt | 1.93 s | 1.93 s |

No difference beyond run-to-run noise. Average RDMA traffic was ~4 Gb/s each way, ~2% of one cable. B spread its bytes over
all 4 rails, but the recipe's RoCEnante all-reduce (messages up to 2 MB, i.e. decode) opened only the first 2 HCAs in both
setups; only NCCL (above 2 MB) used 4. The same vLLM threads were busy in both setups. SoC heat under load comes from compute
(idle 44 °C, load 92 °C peak), not from the cables.
Data: `results/2026-10-19-model-heat/` (temps, phases, per-rail `rdma-counters.csv`, busiest threads, boot logs,
and per-iteration speed results in `load-A.csv` / `load-B.csv`).

## Cabling

| Port | Path | spark1 | spark2 | RoCE devices |
|---|---|---|---|---|
| f0 | direct cable | 10.100.154.1 / .155.1 | 10.100.154.2 / .155.2 | rocep1s0f0, roceP2p1s0f0 |
| f1 | via MikroTik CRS812 | 10.100.152.1 / .153.1 | 10.100.152.3 / .153.2 | rocep1s0f1, roceP2p1s0f1 |

Each physical port has two netdevs, one per PCIe Gen5 x4 half (`0000:01` and `0002:01`). RoCEv2/IPv4 is GID index 3.

## Re-running

perftest versions must match on both ends. spark1 has 6.28 (DOCA) and spark2 has 6.20 (Ubuntu). A 6.20 server crashes ("buffer overflow detected") when a 6.28 client connects.
`bench.sh` runs the client from `~/tmp-perftest/ib_write_bw_620` on spark1, which is a copy of spark2's binary. That copy was deleted after the run, so restore it first:

```bash
ssh spark1 mkdir -p tmp-perftest && scp spark2:/usr/bin/ib_write_bw spark1:tmp-perftest/ib_write_bw_620
```

Alternatively, install the DOCA perftest on spark2 and drop the path from `bench.sh`.

Make sure nothing else is using the Sparks' GPUs or network, then run the matrix:

```bash
./matrix.sh | tee results/$(date +%F)-results.log
uv run --with matplotlib python charts.py results/<file>.log charts/
```
