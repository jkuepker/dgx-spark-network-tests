#!/usr/bin/env bash
# Runs from a machine with ssh access to spark1 and spark2 (nothing else running on them): thermal/thermal_run.sh OUT_DIR
# Logs temps on both Sparks while running: idle baseline, a sustained RDMA soak per cable
# setup (with cooldowns), then the NCCL sweep. Phase markers go to OUT_DIR/phases.csv.
# REVERSE=1 makes spark2 the RDMA sender and NCCL rank 0.
set -u
out=$1; mkdir -p "$out"
here=$(cd "$(dirname "$0")" && pwd)
SOAK=${SOAK:-180}; COOL=${COOL:-90}; IDLE=${IDLE:-60}

mark() { echo "$(date +%s.%N),$1,$2" >> "$out/phases.csv"; }
echo "ts,event,phase" > "$out/phases.csv"

# spark1 needs spark2's perftest 6.20 (version mismatch, see README)
ssh spark1 mkdir -p tmp-perftest
for t in ib_write_bw ib_send_bw; do scp -q spark2:/usr/bin/$t spark1:tmp-perftest/${t}_620; done
if [ "${REVERSE:-0}" = 1 ]; then sender=spark2; else sender=spark1; fi

for h in spark1 spark2; do
  scp -q "$here/temps_logger.sh" $h:/tmp/temps_logger.sh
  ssh $h "nohup bash /tmp/temps_logger.sh /tmp/temps.csv 2 >/dev/null 2>&1 & echo \$! > /tmp/temps_logger.pid"
done

mark start idle; sleep "$IDLE"; mark end idle
# receiver IPs per half: switch A, switch B, direct A, direct B
if [ "${REVERSE:-0}" = 1 ]; then sa=10.100.152.1 sb=10.100.153.1 da=10.100.154.1 db=10.100.155.1
else sa=10.100.152.3 sb=10.100.153.2 da=10.100.154.2 db=10.100.155.2; fi
export REVERSE=${REVERSE:-0}
soaks=(
  "switch-1half rocep1s0f1:$sa"
  "switch-cable rocep1s0f1:$sa roceP2p1s0f1:$sb"
  "direct-cable rocep1s0f0:$da roceP2p1s0f0:$db"
  "both-cables rocep1s0f0:$da roceP2p1s0f0:$db rocep1s0f1:$sa roceP2p1s0f1:$sb"
)
for s in "${soaks[@]}"; do
  read -r name pairs <<<"$s"
  mark start "rdma-$name"
  DUR=$SOAK "$here/../bench.sh" "soak-$name" 1 $pairs | tee -a "$out/soak-results.log"
  mark end "rdma-$name"
  mark start cooldown; sleep "$COOL"; mark end cooldown
done

# Heat source check: the same traffic with event-driven completions (no busy-poll),
# then the busy-poll alone (one spinning core per stream, no traffic).
for s in "${soaks[1]}" "${soaks[3]}"; do
  read -r name pairs <<<"$s"
  mark start "event-$name"
  EVENT=1 DUR=$SOAK "$here/../bench.sh" "soak-event-$name" 1 $pairs | tee -a "$out/soak-results.log"
  mark end "event-$name"
  mark start cooldown; sleep "$COOL"; mark end cooldown
done
mark start cpu-spin-4core
ssh $sender "for i in 1 2 3 4; do timeout $SOAK sh -c 'while :; do :; done' & done; wait"
mark end cpu-spin-4core
mark start cooldown; sleep "$COOL"; mark end cooldown

mark start nccl-sweep
"$here/../nccl/matrix.sh" 3 | tee "$out/nccl-results.log"
mark end nccl-sweep
sleep 30

for h in spark1 spark2; do
  ssh $h 'kill $(cat /tmp/temps_logger.pid); rm -f /tmp/temps_logger.pid /tmp/temps_logger.sh'
  scp -q $h:/tmp/temps.csv "$out/temps-$h.csv" && ssh $h rm -f /tmp/temps.csv
done
ssh spark1 rm -rf tmp-perftest
echo THERMAL_DONE
