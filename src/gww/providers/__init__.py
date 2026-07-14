"""Provider reference defaults for ``gww clean``.

Each module under ``gww/providers/`` exposes the kind's name, a sensible
default ``host_patterns`` list, and a default ``merged`` command template.
These are **reference starting points** (ADR-0019): users copy the relevant
fields into their ``config.yml`` and the ``gww init config`` template
includes them commented out. They are NOT auto-applied — ``resolve_provider``
only matches against user-declared entries.

Module layout:

* :mod:`gww.providers.base` — the :class:`Provider` dataclass and the
  host-pattern matching primitive shared by every kind.
* :mod:`gww.providers.github` — GitHub defaults (``gh pr list``).
* :mod:`gww.providers.gitlab` — GitLab defaults (``glab mr list``).
* :mod:`gww.providers.gitea` — Gitea defaults (``tea pulls list | jq -e``).
"""

from __future__ import annotations

from gww.providers.base import Provider, match_provider
from gww.providers.gitea import GiteaProvider
from gww.providers.github import GitHubProvider
from gww.providers.gitlab import GitLabProvider


def known_providers() -> list[Provider]:
    """Return the list of provider reference defaults.

    Used by ``gww init config`` to enumerate the kinds whose defaults can
    be uncommented into the config. Order is arbitrary — the resolution
    algorithm tests the user's declared entries in config order, not the
    order here.

    Returns:
        List of reference :class:`Provider` instances.
    """
    return [GitHubProvider(), GitLabProvider(), GiteaProvider()]


__all__ = [
    "GiteaProvider",
    "GitHubProvider",
    "GitLabProvider",
    "Provider",
    "known_providers",
    "match_provider",
]