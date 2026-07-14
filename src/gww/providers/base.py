"""Provider dataclass and host-pattern matching primitives.

A :class:`Provider` carries the kind's name, the default list of
``host_patterns`` (regex strings), and the default ``merged`` command
template that ``gww clean`` will evaluate per worktree when a user copies
this kind's defaults into their config.

These are **reference defaults** (ADR-0019) — they document what the
user-declared block in ``config.yml`` should look like, but they are never
applied on the user's behalf. Resolution in :func:`match_provider` iterates
the user-declared entries only; if no entry matches the source's origin
host, ``match_provider`` returns ``None`` and ``gww clean --merged`` falls
back to ``git branch --merged <default>``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from gww.config.validator import ProviderConfig


@dataclass
class Provider:
    """Reference default for one provider kind.

    Each subclass (or instance built from config) carries the kind name,
    a default list of host-pattern regex strings, and the default
    ``merged`` command template.

    Attributes:
        kind: Provider kind identifier (``"github"``, ``"gitlab"``,
            ``"gitea"``). Matches the key under ``providers:`` in the
            user-facing config.
        host_patterns: Default regex strings to match against the source's
            origin host. First match wins (ADR-0019).
        merged: Default command template evaluated per worktree by
            ``gww clean``. Exit 0 means "an MR/PR for this branch is in
            the merged state".
    """

    kind: str
    host_patterns: list[str] = field(default_factory=list)
    merged: str = ""


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


__all__ = ["Provider", "match_provider"]