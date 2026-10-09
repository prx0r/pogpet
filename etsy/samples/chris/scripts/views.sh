#!/bin/bash
# usage: views.sh <script.py> [views csv]
cd /workspace/projects/791a7153-8d05-4c9b-b767-8f281ad46eb0/etsy_samples
command -v blender >/dev/null || { sudo apt-get update -qq && sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq blender python3-numpy; } >/dev/null 2>&1
python3 -c "import cv2,PIL" 2>/dev/null || pip install -q opencv-python-headless pillow >/dev/null 2>&1
echo "$(date +%T) start views $1 ${2:-all}" >> done.txt
VIEWS=${2:-auto} blender -b --python $1 > logs_views_$1.log 2>&1
echo "$(date +%T) done views $1" >> done.txt
grep -E "^VIEW|Error" logs_views_$1.log | tail -6
