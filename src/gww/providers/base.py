"""Host-pattern matching primitive for ``gww clean``.

Resolution in :func:`match_provider` iterates the user-declared
``providers:`` entries only; if no entry matches the source's origin
host, ``match_provider`` returns ``None`` and ``gww clean --merged`` falls
back to ``git branch --merged <default>`` (ADR-0019).
"""

from __future__ import annotations

import re
from typing import Optional

from gww.config.validator import ProviderConfig


def match_provider(
    providers: dict[str, ProviderConfig],
    host: str,
) -> Optional[ProviderConfig]:
    """Find the first configured provider whose patterns match ``host``.

    Iterates ``providers`` in insertion (config) order, testing each
    declared ``host_patterns[i]`` against ``host`` with :func:`re.fullmatch`.
    The first matching pattern wins; the function then returns the
    associated :class:`ProviderConfig`. Returns ``None`` when no pattern
    matches — :func:`gww.cli.commands.clean` treats that as "no provider
    resolvable" and falls back to the git-merged filter (ADR-0015).

    Args:
        providers: User-declared ``providers:`` block from the validated
            config. Iteration order matches config order (ruamel.yaml
            preserves it).
        host: Origin hostname of the source repository (e.g.
            ``"github.com"``).

    Returns:
        Matching :class:`ProviderConfig`, or ``None`` if no pattern in any
        provider matches.
    """
    for provider in providers.values():
        for pattern in provider.host_patterns:
            if re.fullmatch(pattern, host):
                return provider
    return None


__all__ = ["match_provider"]