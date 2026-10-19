#!/usr/bin/env bash
# Runs from a machine with ssh access to spark1 and spark2 (nothing else running on them): thermal/heat_source.sh OUT_DIR
# Where does the sender's heat come from? Logs temps on both Sparks through: idle, busy-poll
# RDMA (ib_write_bw), the same traffic in event mode (ib_send_bw -e), 4 spinning cores with no
# traffic, and a sustained NCCL all-reduce. Each soak is SOAK s with COOL s cooldowns.
# Phase markers go to OUT_DIR/phases.csv, perftest and port-counter rates to soak-results.log,
# the NCCL soak to nccl-soak.log. REVERSE=1 makes spark2 the sender and NCCL rank 0.
set -u
out=$1; mkdir -p "$out"
here=$(cd "$(dirname "$0")" && pwd)
SOAK=${SOAK:-180}; COOL=${COOL:-90}; IDLE=${IDLE:-60}

mark() { echo "$(date +%s.%N),$1,$2" >> "$out/phases.csv"; }
echo "ts,event,phase" > "$out/phases.csv"

# spark1 needs spark2's perftest 6.20 (version mismatch, see README)
ssh spark1 mkdir -p tmp-perftest
for t in ib_write_bw ib_send_bw; do scp -q spark2:/usr/bin/$t spark1:tmp-perftest/${t}_620; done
for h in spark1 spark2; do
  ssh $h mkdir -p nccl-dgxnet && scp -q "$here/../nccl/ar_soak.py" "$here/../nccl/run_rank.sh" $h:nccl-dgxnet/
done
if [ "${REVERSE:-0}" = 1 ]; then
  sender=spark2; r0=spark2; r1=spark1; master=10.100.152.3
  sa=10.100.152.1 sb=10.100.153.1 da=10.100.154.1 db=10.100.155.1
else
  sender=spark1; r0=spark1; r1=spark2; master=10.100.152.1
  sa=10.100.152.3 sb=10.100.153.2 da=10.100.154.2 db=10.100.155.2
fi
export REVERSE=${REVERSE:-0}
cable="rocep1s0f1:$sa roceP2p1s0f1:$sb"
both="rocep1s0f0:$da roceP2p1s0f0:$db rocep1s0f1:$sa roceP2p1s0f1:$sb"

for h in spark1 spark2; do
  scp -q "$here/temps_logger.sh" $h:/tmp/temps_logger.sh
  ssh $h "nohup bash /tmp/temps_logger.sh /tmp/temps.csv 2 >/dev/null 2>&1 & echo \$! > /tmp/temps_logger.pid"
done

cool() { mark start cooldown; sleep "$COOL"; mark end cooldown; }
mark start idle; sleep "$IDLE"; mark end idle

soak() {  # phase EVENT pairs...
  local phase=$1 ev=$2; shift 2
  mark start "$phase"
  EVENT=$ev DUR=$SOAK "$here/../bench.sh" "soak-$phase" 1 "$@" | tee -a "$out/soak-results.log"
  mark end "$phase"
  cool
}
soak poll-switch-cable 0 $cable
soak event-switch-cable 1 $cable
soak poll-both-cables 0 $both
soak event-both-cables 1 $both

mark start cpu-spin-4core
ssh $sender "for i in 1 2 3 4; do timeout $SOAK sh -c 'while :; do :; done' & done; wait"
mark end cpu-spin-4core
cool

mark start nccl-soak-switch-cable
hcas=rocep1s0f1,roceP2p1s0f1
ssh $r1 "SCRIPT=ar_soak.py SOAK=$SOAK TMO=$((SOAK + 220)) bash nccl-dgxnet/run_rank.sh 1 $hcas 29700 $master" >"$out/nccl-soak-rank1.tmp" 2>&1 &
ssh $r0 "SCRIPT=ar_soak.py SOAK=$SOAK TMO=$((SOAK + 220)) bash nccl-dgxnet/run_rank.sh 0 $hcas 29700 $master" | tee "$out/nccl-soak.log"
wait
grep -E "WARN|rror" "$out/nccl-soak-rank1.tmp" | sed 's/^/rank1: /' | tee -a "$out/nccl-soak.log"
rm -f "$out/nccl-soak-rank1.tmp"
mark end nccl-soak-switch-cable
cool

for h in spark1 spark2; do
  ssh $h 'kill $(cat /tmp/temps_logger.pid); rm -f /tmp/temps_logger.pid /tmp/temps_logger.sh'
  scp -q $h:/tmp/temps.csv "$out/temps-$h.csv" && ssh $h rm -f /tmp/temps.csv
  ssh $h rm -rf nccl-dgxnet
done
ssh spark1 rm -rf tmp-perftest
echo HEAT_DONE
