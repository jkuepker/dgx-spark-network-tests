#!/usr/bin/env bash
# Runs from a machine with ssh access to spark1 and spark2 (nothing else using their GPUs):
#   LOAD_CMD='<load command>' thermal/model_heat.sh [LOAD_SECONDS]
# Real model work, 1 cable vs 2 cables: Qwen3.8-Flash-Next TP=2 (qwen38-flash-next-cluster-recipe on spark1)
# under the same looped load, logging NIC/SoC/GPU temps, per-thread CPU and per-rail RDMA bytes.
#   LOAD_CMD          run in a loop against the server; gets $URL, $MODEL and $LABEL in its environment.
#                     Any OpenAI-API benchmark works; the published run used 1k + 8k prompts, 512 output
#                     tokens, 2 reps each, then 4 concurrent streams.
#   PAUSE_CONTAINERS  containers stopped on both Sparks for the test and started again after (default: none).
#   RESTORE_URLS      URLs that must answer before the script exits (default: none).
#   A: NCCL_IB_HCA=rocep1s0f1,roceP2p1s0f1                          (1 cable, both PCIe links)
#   B: NCCL_IB_HCA=rocep1s0f1,roceP2p1s0f1,rocep1s0f0,roceP2p1s0f0  (2 cables, 4 rails)
# The recipe's own RoCE all-reduce (small messages, i.e. decode) uses the first 2 HCAs in both phases.
set -u
: "${LOAD_CMD:?set LOAD_CMD to the load command, see the header}"
PAUSE_CONTAINERS=${PAUSE_CONTAINERS:-}; RESTORE_URLS=${RESTORE_URLS:-}
here=$(cd "$(dirname "$0")/.." && pwd)
load_s=${1:-900}; idle_s=180; cool_s=300
out="$here/results/$(date +%F)-model-heat"; mkdir -p "$out"
R=/tmp/model-heat; REC='~/code/qwen38-flash-next-cluster-recipe'
URL=${URL:-http://spark1:8000/v1}; MODEL=Qwen/Qwen3.8-Flash-Next
log() { echo "$(date +%H:%M:%S) $*" | tee -a "$out/run.log"; }
mark() { echo "$(date +%s.%N),$1,$2" >> "$out/phases.csv"; }
counters() {  # counters LABEL: per-rail RDMA bytes on both boxes (port_*_data counts 4-byte words)
  for h in spark1 spark2; do
    ssh $h 'for d in /sys/class/infiniband/*; do echo "$(basename $d),$(cat $d/ports/1/counters/port_xmit_data),$(cat $d/ports/1/counters/port_rcv_data)"; done' \
      | sed "s/^/$1,$h,/" >> "$out/rdma-counters.csv"
  done
}
restore() {
  log "restore: stop cluster, put recipe files back, start paused containers"
  ssh spark1 "cd $REC && ./stop.sh >/dev/null 2>&1; mv -f cluster.env.heat-bak cluster.env 2>/dev/null; mv -f recipe.yaml.heat-bak recipe.yaml 2>/dev/null; true"
  for h in spark1 spark2; do
    ssh $h "pkill -f $R/temps_logger.sh; pkill -f $R/threads.sh; true"
    scp -q "$h:$R/temps.csv" "$out/temps-$h.csv"; scp -q "$h:$R/threads.log" "$out/threads-$h.log"
    for c in $PAUSE_CONTAINERS; do ssh $h "docker start $c >/dev/null && echo started $c" | sed "s/^/  $h: /"; done
  done
  for u in $RESTORE_URLS; do  # wait until each restored service answers
    for _ in $(seq 1 120); do curl -sf -m 5 "$u" >/dev/null && { log "  up: $u"; break; }; sleep 10; done
  done
}
trap restore EXIT

echo "ts,event,phase" > "$out/phases.csv"; echo "label,host,dev,xmit_words,rcv_words" > "$out/rdma-counters.csv"
log "stop paused containers: ${PAUSE_CONTAINERS:-none}"
for h in spark1 spark2; do for c in $PAUSE_CONTAINERS; do ssh $h "docker stop $c >/dev/null && echo stopped $c" | sed "s/^/  $h: /"; done; done
for h in spark1 spark2; do
  ssh $h "rm -rf $R && mkdir -p $R"; scp -q "$here/thermal/temps_logger.sh" "$h:$R/"
  ssh $h "cat > $R/threads.sh" <<'EOF'
#!/bin/bash
# every ~10 s: the 15 busiest threads over a 1 s window
while true; do echo "== $(date +%s)"; top -H -b -n2 -d1 -w 220 | awk '/^top -/{f++} f==2' | sed -n 7,22p; sleep 9; done
EOF
  ssh $h "chmod +x $R/*.sh; nohup $R/temps_logger.sh $R/temps.csv 2 >/dev/null 2>&1 & nohup $R/threads.sh > $R/threads.log 2>&1 &"
done
ssh spark1 "cd $REC && cp cluster.env cluster.env.heat-bak && cp recipe.yaml recipe.yaml.heat-bak && sed -i 's/^\(\s*ib_links:\s*\)2/\11/' recipe.yaml && grep -n ib_links recipe.yaml" | tee -a "$out/run.log"
log "settle 120 s, nothing running"; mark start idle; sleep 120; mark end idle

for phase in A:rocep1s0f1,roceP2p1s0f1 B:rocep1s0f1,roceP2p1s0f1,rocep1s0f0,roceP2p1s0f0; do
  p=${phase%%:*}; hca=${phase#*:}; name="model-$p-$(echo "$hca" | tr ',' '\n' | wc -l | tr -d ' ')rails"
  log "== $name: NCCL_IB_HCA=$hca"
  ssh spark1 "cd $REC && cp cluster.env.heat-bak cluster.env && sed -i 's/^HEAD_HCA=.*/HEAD_HCA=$hca/; s/^WORKER_HCA=.*/WORKER_HCA=$hca/' cluster.env && grep _HCA cluster.env"
  mark start "$name-boot"
  if ! ssh spark1 "cd $REC && ./run.sh" > "$out/boot-$p.log" 2>&1; then log "boot $p FAILED, see boot-$p.log"; tail -30 "$out/boot-$p.log"; exit 1; fi
  mark end "$name-boot"
  ssh spark1 'docker logs qwen38-flash-next-cluster 2>&1 | grep -iE "RoCEnante|NET/IB|NCCL_IB_HCA|dual rail"' | tail -8 | tee -a "$out/run.log"
  ssh spark1 "docker inspect qwen38-flash-next-cluster --format '{{range .Config.Env}}{{println .}}{{end}}' | grep NCCL_IB_HCA" | tee -a "$out/run.log"
  log "loaded, idle ${idle_s}s"; mark start "$name-idle"; sleep $idle_s; mark end "$name-idle"
  counters "$name-before"; mark start "$name-load"; t0=$(date +%s); i=0
  while [ $(( $(date +%s) - t0 )) -lt "$load_s" ]; do
    i=$((i + 1))
    URL=$URL MODEL=$MODEL LABEL="heat-$name-$i" bash -c "$LOAD_CMD" >> "$out/load-$p.log" 2>&1 \
      || { log "load iteration $i failed"; tail -5 "$out/load-$p.log"; sleep 10; }
  done
  mark end "$name-load"; counters "$name-after"; log "$name: $i load iterations"
  ssh spark1 "cd $REC && ./stop.sh" >/dev/null 2>&1
  log "cooldown ${cool_s}s"; mark start cooldown; sleep $cool_s; mark end cooldown
done
log "HEAT_DONE"
