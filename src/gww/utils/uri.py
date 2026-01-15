"""URI parsing utilities for git repository URLs."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse


@dataclass(frozen=True)
class ParsedURI:
    """Parsed URI components for git repository URLs.

    Attributes:
        uri: Original URI string.
        protocol: Protocol/scheme (http, https, ssh, git, file).
        host: Hostname or IP address.
        port: Port number as string, empty if not specified.
        path_segments: List of path segments without leading/trailing slashes.
    """

    uri: str
    protocol: str
    host: str
    port: str
    path_segments: list[str]

    def path(self, index: int) -> str:
        """Get path segment by index.

        Args:
            index: Segment index (0-based, negative for reverse indexing).

        Returns:
            Path segment at the specified index.

        Raises:
            IndexError: If index is out of range.
        """
        return self.path_segments[index]


# Pattern for SCP-style SSH URLs: git@host:path
SCP_PATTERN = re.compile(
    r"^(?P<user>[^@]+)@(?P<host>[^:]+):(?P<path>.+)$"
)


def parse_uri(uri: str) -> ParsedURI:
    """Parse a git repository URI into its components.

    Supports:
    - Standard URLs: https://github.com/user/repo.git
    - SSH URLs: ssh://git@github.com/user/repo.git
    - SCP-style SSH: git@github.com:user/repo.git
    - File URLs: file:///path/to/repo

    Args:
        uri: Git repository URI string.

    Returns:
        ParsedURI with extracted components.

    Raises:
        ValueError: If the URI cannot be parsed.
    """
    uri = uri.strip()

    if not uri:
        raise ValueError("Empty URI")

    # Try SCP-style SSH first (git@host:path)
    scp_match = SCP_PATTERN.match(uri)
    if scp_match:
        host = scp_match.group("host")
        path = scp_match.group("path")
        path_segments = _extract_path_segments(path)
        return ParsedURI(
            uri=uri,
            protocol="ssh",
            host=host,
            port="",
            path_segments=path_segments,
        )

    # Try standard URL parsing
    try:
        parsed = urlparse(uri)
    except Exception as e:
        raise ValueError(f"Invalid URI: {uri}") from e

    if not parsed.scheme:
        raise ValueError(f"Missing protocol/scheme in URI: {uri}")

    if not parsed.netloc and parsed.scheme != "file":
        raise ValueError(f"Missing host in URI: {uri}")

    # Extract protocol
    protocol = parsed.scheme.lower()

    # Extract host and port
    host = parsed.hostname or ""
    port = str(parsed.port) if parsed.port else ""

    # Extract and clean path segments
    path = parsed.path
    path_segments = _extract_path_segments(path)

    if not path_segments and protocol != "file":
        raise ValueError(f"Missing path in URI: {uri}")

    return ParsedURI(
        uri=uri,
        protocol=protocol,
        host=host,
        port=port,
        path_segments=path_segments,
    )


def _extract_path_segments(path: str) -> list[str]:
    """Extract clean path segments from a path string.

    Removes:
    - Leading/trailing slashes
    - Empty segments
    - .git suffix from the last segment

    Args:
        path: Path string to parse.

    Returns:
        List of path segments.
    """
    # Remove leading/trailing slashes and split
    segments = [s for s in path.strip("/").split("/") if s]

    # Remove .git suffix from last segment
    if segments and segments[-1].endswith(".git"):
        segments[-1] = segments[-1][:-4]

    return segments


def get_repo_name(uri: str) -> str:
    """Extract repository name from a URI.

    Args:
        uri: Git repository URI.

    Returns:
        Repository name (last path segment without .git).
    """
    parsed = parse_uri(uri)
    return parsed.path_segments[-1] if parsed.path_segments else ""


def get_owner(uri: str) -> Optional[str]:
    """Extract owner/organization from a URI.

    Args:
        uri: Git repository URI.

    Returns:
        Owner name (second-to-last path segment) or None.
    """
    parsed = parse_uri(uri)
    if len(parsed.path_segments) >= 2:
        return parsed.path_segments[-2]
    return None
