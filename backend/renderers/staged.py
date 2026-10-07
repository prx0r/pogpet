"""Staged renderers (cardgen.md §11): registered names, no providers yet.

identity_image_v1 → ai_models.py portraitrepaint/cardart lanes.
mesh_scene        → mesh + room binding (pogtown wedge).
talking_scene_v1  → lipsync lane (ai_models.py lipsync).
All three raise until a provider key + approval exists. Templates may list
them; the matcher only serves templates whose required renderers are live.
"""
from __future__ import annotations


class StagedRendererError(Exception):
    pass


def _staged(name: str) -> None:
    raise StagedRendererError(
        f"{name} is staged: needs a provider key + spend approval "
        "(see backend/ai_models.py). composite2d serves previews meanwhile.")


def identity_image(*args, **kwargs):
    _staged("identity_image_v1")


def mesh_scene(*args, **kwargs):
    _staged("mesh_scene")


def talking_scene(*args, **kwargs):
    _staged("talking_scene_v1")


LIVE = {"composite2d"}
