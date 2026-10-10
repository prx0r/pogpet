"""Capability router. Templates ask for capabilities; providers satisfy them.

Fail-closed: no key, no call, no bill. Endpoints are fal queue models that take
reference images; verify each slug against fal's model page before going live.
"""
from __future__ import annotations
import json, os, time, urllib.request

ROUTES = {
    "identity_scene": [
        ("fal", "fal-ai/nano-banana/edit", lambda prompt, refs: {"prompt": prompt, "image_urls": refs, "num_images": 1}),
        ("fal", "fal-ai/bytedance/seedream/v4/edit", lambda prompt, refs: {"prompt": prompt, "image_urls": refs, "image_size": {"width": 2000, "height": 2800}}),
        ("fal", "fal-ai/flux-pro/kontext/max/multi", lambda prompt, refs: {"prompt": prompt, "image_urls": refs, "aspect_ratio": "5:7"}),
    ],
    "edit_fix": [
        ("fal", "fal-ai/nano-banana/edit", lambda prompt, refs: {"prompt": prompt, "image_urls": refs, "num_images": 1}),
    ],
    "upscale": [
        ("fal", "fal-ai/clarity-upscaler", lambda prompt, refs: {"image_url": refs[0], "upscale_factor": 2}),
        ("fal", "fal-ai/esrgan", lambda prompt, refs: {"image_url": refs[0], "scale": 2}),
    ],
}


class NoProvider(RuntimeError):
    pass


def _fal(model: str, payload: dict, timeout: int = 240) -> str:
    key = os.environ.get("FAL_KEY")
    if not key:
        raise NoProvider("FAL_KEY not set")
    hdr = {"Authorization": f"Key {key}", "Content-Type": "application/json"}
    req = urllib.request.Request(f"https://queue.fal.run/{model}", json.dumps(payload).encode(), hdr)
    sub = json.load(urllib.request.urlopen(req, timeout=60))
    t0 = time.time()
    while time.time() - t0 < timeout:
        st = json.load(urllib.request.urlopen(urllib.request.Request(sub["status_url"], headers=hdr), timeout=30))
        if st.get("status") == "COMPLETED":
            res = json.load(urllib.request.urlopen(urllib.request.Request(sub["response_url"], headers=hdr), timeout=60))
            imgs = res.get("images") or [res.get("image")]
            return imgs[0]["url"]
        time.sleep(2)
    raise TimeoutError(model)


def run(capability: str, prompt: str, refs: list[str]) -> dict:
    """Try each route in order. Returns {"url", "provider", "model"} for provenance."""
    errs = []
    for prov, model, build in ROUTES[capability]:
        try:
            url = _fal(model, build(prompt, refs))
            return {"url": url, "provider": prov, "model": model}
        except NoProvider:
            raise
        except Exception as e:  # next route
            errs.append(f"{model}: {e}")
    raise RuntimeError("; ".join(errs))
