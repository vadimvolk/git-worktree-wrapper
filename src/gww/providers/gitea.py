"""Gitea provider reference defaults for ``gww clean``.

Copies the default ``host_patterns`` and ``merged`` template from this
module into the ``providers:`` block of your ``config.yml`` to enable
Gitea PR-merged filtering:

.. code-block:: yaml

    providers:
      gitea:
        host_patterns: ['^codeberg\\.org$']
        merged: 'tea pulls list --head branch() --state closed --output json | jq -e "[.[] | select(.merged)] | length > 0"'

Gitea's ``tea`` CLI has no native ``--state merged`` filter, so the
default composes ``tea pulls list --state closed --output json`` with a
``jq -e`` selector over the ``.merged`` boolean. ``jq -e`` exits 0 iff
the filter is truthy, giving us the same exit-code-only contract as the
GitHub/GitLab defaults. The composed pipeline runs through the shell
with ``set -o pipefail`` so an upstream ``tea`` failure isn't hidden by
``jq`` exiting 0 on an empty stream.

This default is a best-effort guess — see ``docs/handoff-gww-clean-v2.md``
for the empirical-verification step that should be run before shipping
against an instance.
"""

from __future__ import annotations

from gww.providers.base import Provider


class GiteaProvider(Provider):
    """Gitea defaults — ``tea pulls list | jq -e select(.merged)``."""

    def __init__(self) -> None:
        super().__init__(
            kind="gitea",
            host_patterns=[r"^codeberg\.org$"],
            merged=(
                'tea pulls list --head branch() --state closed --output json '
                '| jq -e "[.[] | select(.merged)] | length > 0"'
            ),
        )


__all__ = ["GiteaProvider"]