#!/usr/bin/env bash
cd "$(dirname "$0")"
export DUR=10
./bench.sh switch-1half 3 rocep1s0f1:10.100.152.3
./bench.sh direct-1half 3 rocep1s0f0:10.100.154.2
./bench.sh switch-cable 5 rocep1s0f1:10.100.152.3 roceP2p1s0f1:10.100.153.2
./bench.sh direct-cable 5 rocep1s0f0:10.100.154.2 roceP2p1s0f0:10.100.155.2
./bench.sh both-cables 5 rocep1s0f0:10.100.154.2 roceP2p1s0f0:10.100.155.2 rocep1s0f1:10.100.152.3 roceP2p1s0f1:10.100.153.2
echo MATRIX_DONE
