#!/bin/bash
# Runs on a Spark. usage: run_rank.sh RANK HCA_LIST PORT [MASTER_IP]
# HCA_LIST is a comma list of RoCE devices, e.g. rocep1s0f0,roceP2p1s0f0
# SCRIPT=ar_soak.py (with SOAK, SIZE) runs the soak instead of the sweep; TMO is the docker timeout (s).
rank=$1; hcas=$2; port=$3; master=${4:-10.100.152.1}
img=ghcr.io/miaai-lab/deepseek-v4.1-flash-exl3-2x-dgx-sparks:2.9bpw
timeout ${TMO:-300} docker run --rm --name nccl-dgxnet-r$rank --gpus all --network host --ipc=host \
  --device /dev/infiniband --cap-add IPC_LOCK --ulimit memlock=-1 \
  -e RANK=$rank -e MASTER=$master -e PORT=$port -e SOAK=${SOAK:-180} -e SIZE=${SIZE:-268435456} \
  -e NCCL_DEBUG=WARN -e NCCL_IB_DISABLE=0 -e NCCL_IB_ROCE_VERSION_NUM=2 \
  -e NCCL_NET=IB -e NCCL_NET_PLUGIN=none -e NCCL_IB_MERGE_NICS=0 \
  -e NCCL_IB_HCA=$hcas -e NCCL_IB_GID_INDEX=3 \
  -e NCCL_SOCKET_IFNAME=enp1s0f1np1 -e GLOO_SOCKET_IFNAME=enp1s0f1np1 \
  -e NCCL_MAX_NCHANNELS=8 -e NCCL_BUFFSIZE=1048576 -e NCCL_PROTO=^LL128 \
  -v $HOME/nccl-dgxnet:/w:ro --entrypoint python3 $img /w/${SCRIPT:-ar_sweep.py} 2>&1 \
  | grep -E "RESULT|NCCL WARN|Error|error" | cut -c1-300
