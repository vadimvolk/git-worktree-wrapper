"""GitLab provider reference defaults for ``gww clean``.

Copies the default ``host_patterns`` and ``merged`` template from this
module into the ``providers:`` block of your ``config.yml`` to enable
GitLab MR-merged filtering:

.. code-block:: yaml

    providers:
      gitlab:
        host_patterns: ['^gitlab\\.com$']
        merged: 'glab mr list --source-branch branch() --state merged'

The exit-code contract is: 0 iff an MR for the rendered branch is in
the merged state. See ADR-0018 for the rationale and ADR-0019 for the
resolution model.
"""

from __future__ import annotations

from gww.providers.base import Provider


class GitLabProvider(Provider):
    """GitLab defaults — ``glab mr list --source-branch <branch> --state merged``.

    Uses ``--state merged`` directly; ``glab`` exits 0 with at least one
    matching row and exits 1 with an empty result, mirroring ``gh``'s
    behaviour for the merged-state question.
    """

    def __init__(self) -> None:
        super().__init__(
            kind="gitlab",
            host_patterns=[r"^gitlab\.com$"],
            merged="glab mr list --source-branch branch() --state merged",
        )


__all__ = ["GitLabProvider"]