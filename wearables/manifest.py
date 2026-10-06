from __future__ import annotations

import json
import shutil
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

KINDS = {"headwear", "garment", "prop", "hardware"}


class ManifestError(ValueError):
    pass


@dataclass
class AssetSpec:
    id: str
    kind: str
    root: Path
    label: str = ""
    file: str = ""
    variants: dict[str, str] = field(default_factory=dict)
    sockets: list[str] = field(default_factory=list)
    fit: dict[str, Any] = field(default_factory=dict)
    quality: dict[str, Any] = field(default_factory=dict)
    source: dict[str, Any] = field(default_factory=dict)
    generator: str = ""
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_path(cls, path: Path) -> "AssetSpec":
        doc = json.loads(path.read_text())
        aid = str(doc.get("id") or path.parent.name).strip()
        kind = str(doc.get("kind") or "").strip().lower()
        if not aid:
            raise ManifestError(f"missing id: {path}")
        if kind not in KINDS:
            raise ManifestError(f"{aid}: kind must be one of {sorted(KINDS)}")
        return cls(
            id=aid,
            kind=kind,
            root=path.parent,
            label=str(doc.get("label") or aid.replace("_", " ").title()),
            file=str(doc.get("file") or ""),
            variants={str(k): str(v) for k, v in (doc.get("variants") or {}).items()},
            sockets=[str(x) for x in (doc.get("sockets") or [])],
            fit=dict(doc.get("fit") or {}),
            quality=dict(doc.get("quality") or {}),
            source=dict(doc.get("source") or {}),
            generator=str(doc.get("generator") or ""),
            raw=doc,
        )

    def file_for(self, body_class: str) -> Path | None:
        rel = self.variants.get(body_class) or self.variants.get("default") or self.file
        if not rel:
            return None
        p = Path(rel)
        return p if p.is_absolute() else self.root / p


class AssetRegistry:
    def __init__(self, root: str | Path):
        self.root = Path(root)
        self._cache: dict[str, AssetSpec] = {}

    def scan(self) -> dict[str, AssetSpec]:
        out: dict[str, AssetSpec] = {}
        if not self.root.exists():
            return out
        for path in sorted(self.root.glob("*/asset.json")):
            spec = AssetSpec.from_path(path)
            if spec.id in out:
                raise ManifestError(f"duplicate asset id {spec.id}")
            out[spec.id] = spec
        self._cache = out
        return out

    def get(self, asset_id: str) -> AssetSpec:
        if not self._cache:
            self.scan()
        try:
            return self._cache[asset_id]
        except KeyError as e:
            raise ManifestError(f"unknown asset {asset_id!r}; have {', '.join(sorted(self._cache))}") from e

    def ids(self) -> list[str]:
        return sorted(self.scan())


def install_asset(*, asset_root: str | Path, asset_id: str, kind: str,
                  glb: str | Path | None = None, glb_url: str = "",
                  manifest: dict[str, Any] | None = None) -> Path:
    """Install one externally sourced GLB into the reusable library.

    Meshy is deliberately treated as a source, not a runtime dependency. Download
    once, record provenance, then all fitting is local Blender work.
    """
    if kind not in KINDS:
        raise ManifestError(f"invalid kind {kind}")
    dst = Path(asset_root) / asset_id
    dst.mkdir(parents=True, exist_ok=True)
    out_glb = dst / "master.glb"
    if glb:
        shutil.copy2(Path(glb), out_glb)
    elif glb_url:
        req = urllib.request.Request(glb_url, headers={"User-Agent": "OddHobbWearables/0.1"})
        with urllib.request.urlopen(req, timeout=120) as r:
            out_glb.write_bytes(r.read())
    doc = dict(manifest or {})
    doc.setdefault("id", asset_id)
    doc.setdefault("kind", kind)
    if out_glb.exists():
        doc.setdefault("file", "master.glb")
    (dst / "asset.json").write_text(json.dumps(doc, indent=2) + "\n")
    return dst
