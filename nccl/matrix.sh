#!/usr/bin/env bash
# Runs from a machine with ssh access to spark1 and spark2 (nothing else running on them): nccl/matrix.sh [RUNS]
# For each cable setup, launches both ranks and prints rank 0's RESULT lines tagged with the setup.
# REVERSE=1 puts rank 0 (and the rendezvous) on spark2.
set -u
if [ "${REVERSE:-0}" = 1 ]; then r0=spark2 r1=spark1 master=10.100.152.3
else r0=spark1 r1=spark2 master=10.100.152.1; fi
runs=${1:-3}
cd "$(dirname "$0")"
for h in spark1 spark2; do ssh $h mkdir -p nccl-dgxnet && scp -q ar_sweep.py run_rank.sh $h:nccl-dgxnet/; done
setups=(
  "switch-1hca rocep1s0f1"
  "switch-cable rocep1s0f1,roceP2p1s0f1"
  "direct-cable rocep1s0f0,roceP2p1s0f0"
  "both-cables rocep1s0f0,roceP2p1s0f0,rocep1s0f1,roceP2p1s0f1"
)
port=29600
for r in $(seq 1 "$runs"); do
  for s in "${setups[@]}"; do
    name=${s%% *}; hcas=${s#* }; port=$((port + 1))
    ssh $r1 "bash nccl-dgxnet/run_rank.sh 1 $hcas $port $master" >/tmp/nccl-dgxnet-r1.$$ 2>&1 &
    ssh $r0 "bash nccl-dgxnet/run_rank.sh 0 $hcas $port $master" | sed "s/^/$name run$r /"
    wait
    grep -E "WARN|rror" /tmp/nccl-dgxnet-r1.$$ | sed "s/^/$name run$r rank1: /"
  done
done
rm -f /tmp/nccl-dgxnet-r1.$$
for h in spark1 spark2; do ssh $h rm -rf nccl-dgxnet; done
echo MATRIX_DONE
