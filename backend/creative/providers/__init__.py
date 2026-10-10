"""Provider adapters: import all modules so @register fires.

Any `from backend.creative.providers import router` (or this package)
registers every adapter. Adding a new adapter = add the module + import
it here. No silent unregistered routes.
"""
from __future__ import annotations

from . import alibaba  # noqa: F401
from . import fal  # noqa: F401
from . import higgsfield  # noqa: F401
from . import local  # noqa: F401
from . import mesh  # noqa: F401
from . import meta  # noqa: F401
from . import router  # noqa: F401
