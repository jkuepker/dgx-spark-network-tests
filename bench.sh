#!/usr/bin/env bash
# Usage: bench.sh LABEL RUNS DEV:SERVER_IP [DEV:SERVER_IP ...]
# Runs concurrent ib_write_bw streams spark1 (client) -> spark2 (server), one per device.
# REVERSE=1 sends spark2 -> spark1 instead (SERVER_IP is then spark1's address).
# Prints per-stream and summed Gb/s for each run.
# EVENT=1 uses ib_send_bw -e (sleep on CQ events instead of busy-polling a core per stream);
# perftest 6.20's ib_write_bw has no event mode.
# BIDIR=1 adds -b: both directions on each stream; the reported Gb/s is the sum of both.
set -u
if [ "${EVENT:-0}" = 1 ]; then tool=ib_send_bw; ev=-e; else tool=ib_write_bw; ev=; fi
# spark2's perftest 6.20 runs on both ends; spark1 uses a temp copy (version mismatch, see README)
if [ "${REVERSE:-0}" = 1 ]; then
  srv=spark1; srv_bin="~/tmp-perftest/${tool}_620 $ev"; cli=spark2; cli_bin="$tool $ev"
else
  srv=spark2; srv_bin="$tool $ev"; cli=spark1; cli_bin="~/tmp-perftest/${tool}_620 $ev"
fi
label=$1; runs=$2; shift 2
dur=${DUR:-10}; qps=${QPS:-4}
# event mode can't run for a duration (-D), so size an iteration count from the measured
# per-stream rate (108 / 98 / 54 Gb/s for 1 / 2 / 4 streams) to last about DUR seconds
if [ -n "$ev" ]; then
  case $# in 1) gbps=108;; 2) gbps=98;; *) gbps=54;; esac
  # -n counts per QP, so split the stream's messages across its QPs
  len="-n $((dur * gbps * 1000000000 / 8 / 1048576 / qps))"; tmo=$((dur * 2 + 30))
else
  len="-D $dur"; tmo=$((dur + 30))
fi
[ "${BIDIR:-0}" = 1 ] && len="$len -b"
for r in $(seq 1 "$runs"); do
  port=18515; pids=(); outs=()
  for pair in "$@"; do
    dev=${pair%%:*}
    ssh $srv "pkill -x 'ib_(write|send)_bw(_620)?'; true" >/dev/null 2>&1
  done
  i=0
  for pair in "$@"; do
    dev=${pair%%:*}
    ssh $srv "timeout $tmo $srv_bin -d $dev -x 3 -p $((port+i)) -q $qps -s 1048576 $len --report_gbits -F >/dev/null 2>&1 &" &
    i=$((i+1))
  done
  wait; sleep 2
  # runs of 60 s or more: also read the sender's port_xmit_data counters (4-byte words, wire bytes
  # incl. headers) 15 s after start and 15 s before the planned end, for a steady-state rate that
  # doesn't depend on perftest printing a result
  ctr=
  if [ "$dur" -ge 60 ]; then
    ctr=$(mktemp); rd='date +%s.%N'
    for pair in "$@"; do rd="$rd; cat /sys/class/infiniband/${pair%%:*}/ports/1/counters/port_xmit_data"; done
    ssh $cli "sleep 15; $rd; sleep $((dur - 30)); $rd" >"$ctr" 2>&1 &
    ctrpid=$!
  fi
  i=0
  for pair in "$@"; do
    dev=${pair%%:*}; ip=${pair#*:}
    out=$(mktemp); outs+=("$out")
    ssh $cli "timeout $tmo $cli_bin -d $dev -x 3 -p $((port+i)) -q $qps -s 1048576 $len --report_gbits -F $ip" >"$out" 2>&1 &
    pids+=($!); i=$((i+1))
  done
  for p in "${pids[@]}"; do wait "$p"; done
  sum=0; line="$label run $r:"
  i=0
  for pair in "$@"; do
    bw=$(awk '$1==1048576 {print $4}' "${outs[$i]}" | tail -1)
    [ -z "$bw" ] && { bw=0; echo "  [$pair] no result:"; tail -5 "${outs[$i]}"; }
    line="$line ${pair%%:*}=$bw"
    sum=$(echo "$sum + $bw" | bc)
    i=$((i+1))
  done
  echo "$line  TOTAL=$sum Gb/s"
  if [ -n "$ctr" ]; then
    wait "$ctrpid"
    devs=(); for pair in "$@"; do devs+=("${pair%%:*}"); done
    awk -v n=$# -v names="${devs[*]}" -v label="$label run $r" '
      { v[NR] = $1 }
      END {
        split(names, d, " "); dt = v[n + 2] - v[1]; tot = 0; line = "  counters " label ":"
        for (i = 1; i <= n; i++) { g = (v[n + 2 + i] - v[1 + i]) * 32 / dt / 1e9; tot += g; line = line sprintf(" %s=%.2f", d[i], g) }
        printf "%s  TOTAL=%.2f Gb/s wire, over %.0f s\n", line, tot, dt
      }' "$ctr"
    rm -f "$ctr"
  fi
  rm -f "${outs[@]}"
  sleep 2
done
