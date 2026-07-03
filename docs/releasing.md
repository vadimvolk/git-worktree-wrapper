# Releasing

How to cut a new release of `git-worktree-wrapper` (CLI command `gww`).

## Overview

Releases are cut by pushing a `vX.Y.Z` tag to GitHub. A workflow builds
the sdist and wheel, publishes to PyPI, and creates a GitHub Release
with auto-generated notes. See ADR-0014 for the authentication
mechanism (PyPI Trusted Publishing via OIDC).

## Pre-flight (one-time, before the first release)

These are manual setup steps that must be completed before the
release workflow will succeed. None of them are automated because they
require credentials and account-level decisions.

### 1. Create the `pypi` GitHub Environment

1. Repo → **Settings** → **Environments** → **New environment**.
2. Name: `pypi` (must match the `environment:` field in
   `.github/workflows/release.yml`).
3. Under **Deployment protection rules**, enable
   **Required reviewers** and add yourself.
4. Optionally add **Wait timer** (e.g. 0 minutes) — useful as a
     sanity pause.
5. Save.

The environment's required-reviewer check is the human gate. Even a
successful tag push is blocked at this step until you approve.

### 2. Register the Trusted Publisher on PyPI

1. Log in to [pypi.org](https://pypi.org/) and create the
   `git-worktree-wrapper` project if it doesn't already exist
   (the first upload will create it automatically, but pre-registering
   lets you configure the publisher ahead of time).
2. Project → **Publishing** → **Add a new pending publisher**:
   - **Owner**: `vadimvolk`
   - **Repository**: `git-worktree-wrapper`
   - **Workflow filename**: `release.yml`
   - **Environment name**: `pypi`
3. Save. PyPI will accept OIDC token exchanges from this workflow
   once a release runs.

### 3. Verify the test suite is green on `main`

The release workflow does **not** re-run CI — it trusts that the
tagged commit has already passed `CI` on the PR that landed it.
Confirm the badge is green before tagging.

## Cutting a release

### 1. Bump the version in `pyproject.toml`

Edit `pyproject.toml`:

```toml
[project]
name = "git-worktree-wrapper"
version = "X.Y.Z"   # ← bump this
```

Commit the change on a branch, push, get it reviewed and merged
into `main`.

### 2. Update `CHANGELOG.md`

Add a new section at the top under `## [Unreleased]` (or move the
existing `[Unreleased]` content into a dated `## [X.Y.Z] - YYYY-MM-DD`
section). Follow the [Keep a Changelog](https://keepachangelog.com/)
format already used in the file.

Commit on a branch, push, get it merged into `main`.

### 3. Tag the merge commit on `main`

```bash
git checkout main
git pull
git tag -a vX.Y.Z -m "Release vX.Y.Z"
git push origin vX.Y.Z
```

Annotated tag is recommended — `git tag` without `-a` works but
loses the tagger identity. The workflow reads the version from
`pyproject.toml`, not from the tag message, so this is purely about
provenance.

### 4. Approve the workflow run

1. Go to **Actions** → **Release** → the run triggered by the tag.
2. The job will be waiting on the `pypi` environment approval.
3. Review the build summary, then **Approve and deploy**.

### 5. Verify

- [ ] PyPI shows the new version:
      https://pypi.org/project/git-worktree-wrapper/#history
- [ ] GitHub Release exists with the sdist + wheel attached:
      https://github.com/vadimvolk/git-worktree-wrapper/releases/tag/vX.Y.Z
- [ ] `pip install --upgrade git-worktree-wrapper` (or
      `uv tool install --upgrade git-worktree-wrapper`) installs the
      new version.

## Versioning rules

- **Strict SemVer only.** The workflow rejects tags that are not
  `vX.Y.Z` (no `-rc1`, no `-alpha`, no `-post1`). Pre-release support
  is deliberately not implemented yet — see the handoff document for
  the rationale and the migration cost if it's added later.
- **Pre-1.0**: breaking changes are allowed in any `0.Y.Z` increment
  per SemVer §4. Treat the API as unstable until `1.0.0`.

## Troubleshooting

**Workflow fails on the version check.**
`pyproject.toml` version does not match the tag. Either retag with
the correct version, or fix `pyproject.toml`, commit, and re-tag.

**Workflow fails on the PyPI publish step.**
Check that the Trusted Publisher is registered with the exact
workflow filename (`release.yml`, including the `.yml` extension) and
the exact environment name (`pypi`). PyPI's match is case-sensitive
and exact.

**Tag was pushed but the workflow didn't trigger.**
Verify the tag matches `v[0-9]+.[0-9]+.[0-9]+`. A tag like
`v0.1` or `0.1.0` (no `v` prefix) won't fire the workflow. Delete
the tag locally and remotely, re-tag correctly, and re-push.

**PyPI succeeded but GitHub Release creation failed.**
The package is published; only the release notes / asset upload
failed. This is rare and usually transient. Re-running the workflow
from the Actions UI is not supported (the workflow only triggers on
tag push). Manual recovery: delete the tag remotely, re-push, approve
again. Or download the artifacts from the workflow run's
"Summary" page and attach them to a manually-created release.

## See also

- `docs/adr/0014-pypi-trusted-publishing.md` — why OIDC, not API
  tokens.
- `CONTEXT.md` — *Release*, *Release trigger*, *Trusted Publishing*,
  *`pypi` GitHub Environment* entries.