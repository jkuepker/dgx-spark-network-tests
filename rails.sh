#!/usr/bin/env bash
# Runs from a machine with ssh access to spark1 and spark2 (nothing else running on them): ./rails.sh [RUNS]
# Every cage/rail combination, spark1 -> spark2, to show the total follows PCIe links, not cables.
# REVERSE=1 sends spark2 -> spark1 (passed through to bench.sh). BIDIR=1 adds -b (both ways).
# Rails: rocep1s0f0 = cage 0 / link A, roceP2p1s0f0 = cage 0 / link B,
#        rocep1s0f1 = cage 1 / link A, roceP2p1s0f1 = cage 1 / link B.
set -u
here=$(cd "$(dirname "$0")" && pwd); runs=${1:-3}
# receiver addresses: spark2's by default, spark1's when REVERSE=1
if [ "${REVERSE:-0}" = 1 ]; then
  c0a=rocep1s0f0:10.100.154.1; c0b=roceP2p1s0f0:10.100.155.1
  c1a=rocep1s0f1:10.100.152.1; c1b=roceP2p1s0f1:10.100.153.1
else
  c0a=rocep1s0f0:10.100.154.2; c0b=roceP2p1s0f0:10.100.155.2
  c1a=rocep1s0f1:10.100.152.3; c1b=roceP2p1s0f1:10.100.153.2
fi
ssh spark1 mkdir -p tmp-perftest && scp -q spark2:/usr/bin/ib_write_bw spark1:tmp-perftest/ib_write_bw_620
"$here/bench.sh" "1cage-1rail-linkA"          "$runs" $c0a
"$here/bench.sh" "1cage-1rail-linkB"          "$runs" $c0b
"$here/bench.sh" "1cage-2rails-linkA+B"       "$runs" $c0a $c0b
"$here/bench.sh" "2cages-2rails-sameLinkA"    "$runs" $c0a $c1a
"$here/bench.sh" "2cages-2rails-linkA+B"      "$runs" $c0a $c1b
"$here/bench.sh" "2cages-3rails"              "$runs" $c0a $c0b $c1a
"$here/bench.sh" "2cages-4rails"              "$runs" $c0a $c0b $c1a $c1b
ssh spark1 rm -rf tmp-perftest
echo RAILS_DONE
