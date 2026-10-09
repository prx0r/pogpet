#!/bin/bash
cd /workspace/projects/791a7153-8d05-4c9b-b767-8f281ad46eb0/etsy_samples
for i in $(seq 1 56); do
  if [ ! -s queue.txt ] && ! pgrep -f "blender -b --python r0" >/dev/null && ! pgrep -f "blender -b --python r1" >/dev/null; then echo QUEUE_EMPTY; tail -12 done.txt; exit 0; fi
  sleep 10
done
echo STILL_RUNNING; tail -4 done.txt; cat queue.txt
