"""GitHub provider reference defaults for ``gww clean``.

Copies the default ``host_patterns`` and ``merged`` template from this
module into the ``providers:`` block of your ``config.yml`` to enable
GitHub PR-merged filtering:

.. code-block:: yaml

    providers:
      github:
        host_patterns: ['^github\\.com$']
        merged: 'gh pr list --head branch() --state merged'

The exit-code contract is: 0 iff an MR/PR for the rendered branch is in
the merged state. See ADR-0018 for the rationale and ADR-0019 for the
resolution model.
"""

from __future__ import annotations

from gww.providers.base import Provider


class GitHubProvider(Provider):
    """GitHub defaults — ``gh pr list --head <branch> --state merged``.

    Uses ``--state merged`` (not ``closed``) so the exit code already
    encodes "merged PR exists" without any post-processing. See ADR-0018
    for why we do not need GitHub's ``mergedAt`` quirk here.
    """

    def __init__(self) -> None:
        super().__init__(
            kind="github",
            host_patterns=[r"^github\.com$"],
            merged="gh pr list --head branch() --state merged",
        )


__all__ = ["GitHubProvider"]