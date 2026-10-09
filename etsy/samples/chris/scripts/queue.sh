#!/bin/bash
# sequential final renders: append script names to queue.txt
cd /workspace/projects/791a7153-8d05-4c9b-b767-8f281ad46eb0/etsy_samples
touch queue.txt done.txt
while true; do
  while pgrep -f "blender -b --python r0.*_.*\.py$" >/dev/null || pgrep -f "python r01_golf_marker.py$" > /dev/null; do sleep 20; done
  s=$(head -1 queue.txt)
  if [ -z "$s" ]; then sleep 30; continue; fi
  sed -i '1d' queue.txt
  echo "$(date +%T) start $s" >> done.txt
  blender -b --python $s > logs_$s.log 2>&1
  echo "$(date +%T) done $s" >> done.txt
done
