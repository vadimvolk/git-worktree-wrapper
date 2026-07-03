# 0014 — PyPI Trusted Publishing (OIDC) for releases

The release workflow authenticates to PyPI via [Trusted Publishing][tp]
(OIDC), not via a long-lived API token stored in GitHub Secrets. PyPI
issues a short-lived token to the workflow run based on the repository,
the workflow file path, and the environment name; the workflow exchanges
it for credentials at upload time.

[tp]: https://docs.pypi.org/trusted-publishers/

## Considered Options

- **Long-lived PyPI API token in `PYPI_API_TOKEN` secret** — Rejected:
  shared secret that has to be rotated manually on contributor changes
  or suspected leaks, and that can be phished / exfiltrated from a
  compromised workflow. PyPI's 2023-era guidance explicitly steers new
  projects toward Trusted Publishing.
- **Local `twine upload` from a developer machine** — Rejected:
  bypasses the CI signal we get from a single tag push and couples
  releases to whoever happens to have a working `~/.pypirc`.

## Implementation Notes

- Configure a pending publisher on the `gww` PyPI project pointing at
  this repo, the `release.yml` workflow path, and the `pypi` GitHub
  Environment.
- The workflow reads `version` from `pyproject.toml` and refuses to
  publish if it does not equal the pushed tag's stripped `v` prefix —
  the tag is the trigger, the file is the source of truth.
- Create a `pypi` GitHub Environment with a required reviewer so a
  manual approval gates each publish. The OIDC token only succeeds
  when the run is targeting that environment, so an attacker who
  managed to push a `v*` tag still gets blocked at the environment
  approval step unless they also have approval rights.
- PyPI does not need an API token to exist at all; the workflow uses
  `pypa/gh-action-pypi-publish` (or equivalent) which handles the OIDC
  exchange natively.