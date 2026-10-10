#!/usr/bin/env bash
# One command per product: prep -> repair -> pack -> PREFLIGHT GATE -> listing renders.
# usage: ./run_product.sh <source.glb> <name> <height_mm> [faces=150000] [process=wjp]
set -euo pipefail
SRC=$1; NAME=$2; H=$3; TF=${4:-150000}; PROC=${5:-wjp}
HERE=$(cd "$(dirname "$0")" && pwd); OUT=$HERE/work/$NAME/h$H; mkdir -p $OUT
which blender >/dev/null || sudo apt-get install -y -qq blender python3-numpy
python3 -c "import trimesh" 2>/dev/null || pip install -q trimesh pillow numpy
blender -b --python $HERE/bl_prep.py -- "$SRC" $H $TF $OUT 2>&1 | grep -E "P3D|PREP_DONE|Error" || true
cp $OUT/model.obj $OUT/model_prep.obj
python3 $HERE/repair_uv.py $OUT/model_prep.obj $OUT/model.obj
python3 $HERE/pack_jlc.py $OUT "$SRC" $NAME-$H
echo "== PREFLIGHT =="; 
if ! python3 $HERE/preflight.py $OUT/$NAME-$H-jlc.zip --process $PROC --target-h $H --prep $OUT/prep_report.json --json $OUT/preflight.json; then
  echo "PREFLIGHT FAILED: do not upload to JLC"; exit 1; fi
rm -rf $OUT/zipcheck && mkdir $OUT/zipcheck && (cd $OUT/zipcheck && unzip -q ../$NAME-$H-jlc.zip)
mkdir -p $OUT/listing
blender -b --python $HERE/bl_listing.py -- $OUT/zipcheck $OUT/listing/$NAME 1600 48 2>&1 | grep -E "RENDERED|Error" || true
echo "DONE: $OUT/$NAME-$H-jlc.zip + listing/ + preflight.json -> now fill products/<SKU>.json"
