#!/bin/bash
# usage: tile.sh <script.py> <i> <n>  -- one strip; when i==n-1... stitch via stitch.py
cd /workspace/projects/791a7153-8d05-4c9b-b767-8f281ad46eb0/etsy_samples
command -v blender >/dev/null || { sudo apt-get update -qq && sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq blender python3-numpy; } >/dev/null 2>&1
python3 -c "import cv2,PIL" 2>/dev/null || pip install -q opencv-python-headless pillow >/dev/null 2>&1
echo "$(date +%T) start $1 tile $2/$3" >> done.txt
TILE=$2/$3 blender -b --python $1 > logs_${1}_t$2.log 2>&1
echo "$(date +%T) done $1 tile $2/$3" >> done.txt
grep -E "RENDERED|Error" logs_${1}_t$2.log | tail -2
