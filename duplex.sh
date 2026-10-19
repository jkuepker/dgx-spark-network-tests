#!/usr/bin/env bash
# Runs from a machine with ssh access to spark1 and spark2 (nothing else running on them): ./duplex.sh [RUNS]
# Both directions at once between the two Sparks:
#   two-cable: spark1 -> spark2 on the direct cable while spark2 -> spark1 on the switch cable
#   one-cable: ib_write_bw -b on both rails of the switch cable
set -u
here=$(cd "$(dirname "$0")" && pwd); runs=${1:-3}
ssh spark1 mkdir -p tmp-perftest && scp -q spark2:/usr/bin/ib_write_bw spark1:tmp-perftest/ib_write_bw_620
total() { sed -n 's/.*TOTAL=\([0-9.]*\).*/\1/p' "$1"; }
for r in $(seq 1 "$runs"); do
  fwd=$(mktemp); rev=$(mktemp)
  "$here/bench.sh" "two-cable run $r spark1->spark2 (direct)" 1 rocep1s0f0:10.100.154.2 roceP2p1s0f0:10.100.155.2 >"$fwd" &
  REVERSE=1 "$here/bench.sh" "two-cable run $r spark2->spark1 (switch)" 1 rocep1s0f1:10.100.152.1 roceP2p1s0f1:10.100.153.1 >"$rev" &
  wait
  cat "$fwd" "$rev"
  echo "two-cable run $r: BOTH-WAYS TOTAL=$(echo "$(total "$fwd") + $(total "$rev")" | bc) Gb/s"
  rm -f "$fwd" "$rev"; sleep 3
done
BIDIR=1 "$here/bench.sh" one-cable-bidir "$runs" rocep1s0f1:10.100.152.3 roceP2p1s0f1:10.100.153.2
ssh spark1 rm -rf tmp-perftest
echo DUPLEX_DONE
