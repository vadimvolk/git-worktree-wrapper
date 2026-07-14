"""Provider host-pattern resolution for ``gww clean``.

The ``providers:`` block in ``config.yml`` maps a kind to its
``host_patterns`` and ``merged`` command template. Users declare these
themselves; nothing is auto-applied. :func:`match_provider` walks the
user-declared entries in config order and returns the first whose pattern
matches the source's origin host (ADR-0019). The ``gww init config``
template documents sensible starting points as commented-out defaults.
"""

from __future__ import annotations

from gww.providers.base import match_provider

__all__ = ["match_provider"]
