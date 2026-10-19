#!/bin/bash
# Runs on a Spark. Samples temps every INTERVAL seconds to OUTFILE (CSV) until killed.
# usage: temps_logger.sh OUTFILE [INTERVAL]
out=$1; iv=${2:-2}
nics=()
for d in /sys/class/hwmon/hwmon*; do
  [ "$(cat $d/name)" = mlx5 ] && nics+=("$d")
done
hdr="ts"
for d in "${nics[@]}"; do hdr="$hdr,nic_$(basename "$(readlink -f $d/device)")"; done
echo "$hdr,soc_max_c,gpu_c,gpu_w" > "$out"
while true; do
  line="$(date +%s.%N)"
  for d in "${nics[@]}"; do line="$line,$(( $(cat $d/temp1_input) / 1000 ))"; done
  soc=$(cat /sys/class/thermal/thermal_zone*/temp | sort -n | tail -1)
  gpu=$(nvidia-smi --query-gpu=temperature.gpu,power.draw --format=csv,noheader,nounits | tr -d ' ')
  echo "$line,$(awk "BEGIN{print $soc/1000}"),$gpu" >> "$out"
  sleep "$iv"
done
