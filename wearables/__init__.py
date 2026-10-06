"""OddHobb reusable wearables + props engine.

Public API:
    AssetRegistry
    analyse_target
    compose
    build_variant (normal Python -> launches Blender)
"""
from .manifest import AssetRegistry, AssetSpec
from .runner import build_variant

__all__ = ["AssetRegistry", "AssetSpec", "build_variant"]
__version__ = "0.1.0"
