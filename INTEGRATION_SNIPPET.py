# Example backend-side integration (normal Python, no bpy import)
from wearables.runner import build_variant


def build_brick_party_variant(src_glb: str, out_glb: str):
    return build_variant(
        input_glb=src_glb,
        output_glb=out_glb,
        items=["golf_club@hand_right", "candle@hand_left"],
        hardware=["cake_topper_spikes"],
        asset_root="data/assets/wearables",
        repo_root=".",
    )
