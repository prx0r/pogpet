# Final production rig pass

The current package is enough to ship the MVP at full-character/pose level. To get genuinely high-end wing flutter, blinking, mouth shapes and pointing without visual seams, make one final neutral master.

## Required repaint

Create a 1600×1600 transparent neutral front/three-quarter Bartholomew with:

- head/helmet with empty eye sockets
- torso with no arms painted into it
- abdomen separated at the thorax joint
- no wings
- no antennae
- no cape
- no mouth

Then register every detachable sprite on that exact same 1600×1600 canvas. **Do not tight-crop these production rig layers.** Alignment should be implicit because every file shares identical dimensions and origin.

Recommended production layers:

```text
00_body_base
01_abdomen
02_eye_left
03_eye_right
04_mouth
05_antenna_left
06_antenna_right
07_arm_left
08_arm_right
09_wing_left_front
10_wing_left_back
11_wing_right_front
12_wing_right_back
13_cape_upper
14_cape_lower
```

For talking, use mouth replacements or viseme sprites rather than deforming the whole face.

## Suggested transform origins

- wings: root at thorax attachment point
- antennae: root at skull attachment point
- arms: root at shoulder
- cape: root at collar
- abdomen: root at thorax joint

This lets Motion/Rive/Spine create convincing secondary motion with very little complexity.
