"""Unit tests for migrate command helpers in src/gww/cli/commands/migrate.py."""

import subprocess
from pathlib import Path

import pytest

from gww.cli.commands.migrate import _find_git_repositories


@pytest.mark.unit
class TestFindGitRepositories:
    """Tests for _find_git_repositories."""

    def test_does_not_descend_into_repository_interior(
        self, tmp_path: Path
    ) -> None:
        """When a repo root is found, the walk does not descend into its subdirectories."""
        root = tmp_path / "root"
        root.mkdir()
        repo_a = root / "repo_a"
        repo_a.mkdir()
        subprocess.run(["git", "init"], cwd=repo_a, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@test.com"],
            cwd=repo_a,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test"],
            cwd=repo_a,
            check=True,
            capture_output=True,
        )
        (repo_a / "src").mkdir()
        (repo_a / "src" / "file.txt").write_text("x")
        (repo_a / "docs").mkdir()
        (repo_a / "docs" / "readme.txt").write_text("y")

        visited: list[Path] = []

        result = _find_git_repositories(
            root, progress_callback=lambda p: visited.append(Path(p))
        )

        assert result == [repo_a]
        # Only root and repo_a should be visited; repo_a/src and repo_a/docs must not
        visited_resolved = [p.resolve() for p in visited]
        repo_a_resolved = repo_a.resolve()
        assert repo_a_resolved in visited_resolved
        assert (repo_a / "src").resolve() not in visited_resolved
        assert (repo_a / "docs").resolve() not in visited_resolved
