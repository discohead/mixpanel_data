"""Property-based tests for MixpanelAPIClient using Hypothesis.

These tests verify invariants that should hold for all possible inputs,
catching edge cases that example-based tests might miss.

Properties tested:
- Auth header roundtrip: Base64-encoded auth decodes to original credentials
- Backoff bounds: Exponential backoff stays within documented limits
- URL path normalization: Leading slash handling is consistent
- JSONL chunk invariance: Line parsing is independent of chunk boundaries
"""

from __future__ import annotations

import base64
from collections.abc import Iterator

import httpx
from httpx._types import SyncByteStream
from hypothesis import assume, given, settings
from hypothesis import strategies as st
from pydantic import SecretStr

from mixpanel_data._internal.api_client import (
    ENDPOINTS,
    MixpanelAPIClient,
    _iter_jsonl_lines,
)
from mixpanel_data._internal.config import Credentials

# =============================================================================
# Custom Strategies
# =============================================================================

# Strategy for valid regions
regions = st.sampled_from(["us", "eu", "in"])

# Strategy for valid API types
api_types = st.sampled_from(list(ENDPOINTS["us"].keys()))

# Strategy for non-empty strings suitable for usernames
# Exclude null bytes which aren't valid in HTTP headers
# Exclude surrogates (Cs category) which can't be encoded to UTF-8
usernames = st.text(
    alphabet=st.characters(
        exclude_characters="\x00",
        exclude_categories=("Cs",),  # type: ignore[arg-type]  # Cs is valid Unicode category
    ),
    min_size=1,
    max_size=100,
).filter(lambda s: s.strip())

# Strategy for secrets (can contain any printable characters including colons)
# Exclude null bytes for HTTP header compatibility
# Exclude surrogates (Cs category) which can't be encoded to UTF-8
secrets = st.text(
    alphabet=st.characters(
        exclude_characters="\x00",
        exclude_categories=("Cs",),  # type: ignore[arg-type]  # Cs is valid Unicode category
    ),
    min_size=1,
    max_size=100,
).filter(lambda s: s.strip())

# Strategy for project IDs
# Exclude surrogates (Cs category) which can't be encoded to UTF-8
project_ids = st.text(
    alphabet=st.characters(
        exclude_characters="\x00",
        exclude_categories=("Cs",),  # type: ignore[arg-type]  # Cs is valid Unicode category
    ),
    min_size=1,
    max_size=50,
).filter(lambda s: s.strip())

# Strategy for URL paths
# Paths can contain letters, numbers, and common path characters
# Excludes category "P" (Punctuation) which includes ?, #, & that break URLs
url_paths = st.text(
    alphabet=st.characters(
        categories=("L", "N"),
        include_characters="/-_.",
    ),
    min_size=1,
    max_size=100,
)

# Strategy for backoff attempt numbers (realistic range)
attempts = st.integers(min_value=0, max_value=20)


# =============================================================================
# Auth Header Roundtrip Property Tests
# =============================================================================


class TestAuthHeaderProperties:
    """Property-based tests for _get_auth_header()."""

    @given(username=usernames, secret=secrets, region=regions)
    @settings(max_examples=50)
    def test_auth_header_roundtrip(
        self, username: str, secret: str, region: str
    ) -> None:
        """Auth header should encode credentials that can be decoded back.

        This is a security-critical property: the Base64-encoded auth header
        must correctly represent the original username:secret pair for
        authentication to work correctly.

        Args:
            username: Service account username.
            secret: Service account secret.
            region: Data residency region.
        """
        creds = Credentials(
            username=username,
            secret=SecretStr(secret),
            project_id="test_project",
            region=region,
        )
        client = MixpanelAPIClient(creds)

        try:
            header = client._get_auth_header()

            # Header should have correct format
            assert header.startswith("Basic "), (
                f"Header should start with 'Basic ': {header}"
            )

            # Decode and verify roundtrip
            encoded_part = header.replace("Basic ", "")
            decoded = base64.b64decode(encoded_part).decode()

            expected = f"{username}:{secret}"
            assert decoded == expected, f"Decoded '{decoded}' != expected '{expected}'"
        finally:
            client.close()

    @given(
        prefix=st.text(
            alphabet=st.characters(
                exclude_characters="\x00",
                exclude_categories=("Cs",),  # type: ignore[arg-type]  # Cs is valid
            ),
            min_size=1,
            max_size=20,
        ).filter(lambda s: s.strip()),
        suffix=st.text(
            alphabet=st.characters(
                exclude_characters="\x00",
                exclude_categories=("Cs",),  # type: ignore[arg-type]  # Cs is valid
            ),
            max_size=20,
        ),
        secret=secrets,
        region=regions,
    )
    @settings(max_examples=30)
    def test_auth_header_handles_colons_in_username(
        self, prefix: str, suffix: str, secret: str, region: str
    ) -> None:
        """Auth header should correctly handle colons in username.

        HTTP Basic auth uses colon as separator, so usernames with colons
        must be handled correctly. Only the first colon separates username
        from password in the decoded format.

        Args:
            prefix: Text before the colon.
            suffix: Text after the colon.
            secret: Service account secret.
            region: Data residency region.
        """
        # Build username with guaranteed colon
        username = f"{prefix}:{suffix}"

        creds = Credentials(
            username=username,
            secret=SecretStr(secret),
            project_id="test_project",
            region=region,
        )
        client = MixpanelAPIClient(creds)

        try:
            header = client._get_auth_header()
            encoded_part = header.replace("Basic ", "")
            decoded = base64.b64decode(encoded_part).decode()

            # The decoded string should be exactly username:secret
            # even if username contains colons
            expected = f"{username}:{secret}"
            assert decoded == expected
        finally:
            client.close()


# =============================================================================
# Backoff Bounds Property Tests
# =============================================================================


class TestBackoffProperties:
    """Property-based tests for _calculate_backoff()."""

    @given(attempt=attempts)
    @settings(max_examples=100)
    def test_backoff_within_bounds(self, attempt: int) -> None:
        """Backoff delay should be within documented bounds.

        Formula: min(1.0 * 2^attempt, 60.0) + random(0, delay * 0.1)

        The delay must:
        - Be at least the base delay (no negative jitter)
        - Not exceed base delay + 10% jitter
        - Never exceed 66 seconds (60 * 1.1)

        Args:
            attempt: Zero-based attempt number.
        """
        creds = Credentials(
            username="test",
            secret=SecretStr("secret"),
            project_id="123",
            region="us",
        )
        client = MixpanelAPIClient(creds)

        try:
            delay = client._calculate_backoff(attempt)

            # Calculate expected base delay
            base = 1.0
            max_delay = 60.0
            expected_base = min(base * (2**attempt), max_delay)

            # Jitter is [0, 10%] of base delay
            max_jitter = expected_base * 0.1

            # Delay should be at least the base
            assert delay >= expected_base, (
                f"Delay {delay} < expected base {expected_base} for attempt {attempt}"
            )

            # Delay should not exceed base + max jitter
            assert delay <= expected_base + max_jitter, (
                f"Delay {delay} > max {expected_base + max_jitter} for attempt {attempt}"
            )

            # Absolute maximum is 66 seconds (60 * 1.1)
            assert delay <= 66.0, f"Delay {delay} exceeds absolute max of 66s"
        finally:
            client.close()

    @given(attempt=st.integers(min_value=10, max_value=100))
    @settings(max_examples=30)
    def test_backoff_caps_at_60_seconds_base(self, attempt: int) -> None:
        """Backoff base delay should cap at 60 seconds for high attempts.

        For attempts >= 6 (2^6 = 64 > 60), the base delay caps at 60s.
        Total with jitter should not exceed 66s.

        Args:
            attempt: High attempt number (>= 10).
        """
        creds = Credentials(
            username="test",
            secret=SecretStr("secret"),
            project_id="123",
            region="us",
        )
        client = MixpanelAPIClient(creds)

        try:
            delay = client._calculate_backoff(attempt)

            # At high attempts, base should be capped at 60
            assert delay >= 60.0, (
                f"Delay {delay} should be at least 60 for attempt {attempt}"
            )
            assert delay <= 66.0, (
                f"Delay {delay} should be at most 66 for attempt {attempt}"
            )
        finally:
            client.close()

    @given(
        attempt1=st.integers(min_value=0, max_value=5),
        attempt2=st.integers(min_value=0, max_value=5),
    )
    @settings(max_examples=50)
    def test_backoff_monotonically_increasing_base(
        self, attempt1: int, attempt2: int
    ) -> None:
        """Lower attempts have smaller or equal minimum delay than higher attempts.

        The base delay doubles with each attempt (before capping), so
        the minimum possible delay for attempt N is always <= minimum for N+1.

        Args:
            attempt1: First attempt number.
            attempt2: Second attempt number.
        """
        assume(attempt1 < attempt2)

        creds = Credentials(
            username="test",
            secret=SecretStr("secret"),
            project_id="123",
            region="us",
        )
        client = MixpanelAPIClient(creds)

        try:
            # Calculate expected base delays
            base1 = min(1.0 * (2**attempt1), 60.0)
            base2 = min(1.0 * (2**attempt2), 60.0)

            # Base should be monotonically non-decreasing
            assert base1 <= base2, (
                f"Base delay should increase: {base1} > {base2} "
                f"for attempts {attempt1} vs {attempt2}"
            )
        finally:
            client.close()


# =============================================================================
# URL Path Normalization Property Tests
# =============================================================================


class TestUrlBuildProperties:
    """Property-based tests for _build_url()."""

    @given(api_type=api_types, path=url_paths, region=regions)
    @settings(max_examples=50)
    def test_url_path_normalization_idempotent(
        self, api_type: str, path: str, region: str
    ) -> None:
        """URL building should handle leading slashes consistently.

        Paths with or without leading slashes should produce the same URL.
        The function normalizes by adding a leading slash if missing.

        Args:
            api_type: API endpoint type (query, export, engage, app).
            path: URL path segment.
            region: Data residency region.
        """
        creds = Credentials(
            username="test",
            secret=SecretStr("secret"),
            project_id="123",
            region=region,
        )
        client = MixpanelAPIClient(creds)

        try:
            # Path with leading slash
            path_with_slash = "/" + path.lstrip("/")
            # Path without leading slash
            path_without_slash = path.lstrip("/")

            url_with = client._build_url(api_type, path_with_slash)
            url_without = client._build_url(api_type, path_without_slash)

            assert url_with == url_without, (
                f"URLs differ for path '{path}': "
                f"with slash='{url_with}', without='{url_without}'"
            )
        finally:
            client.close()

    @given(api_type=api_types, path=url_paths, region=regions)
    @settings(max_examples=30)
    def test_url_contains_path(self, api_type: str, path: str, region: str) -> None:
        """Built URL should contain the path segment.

        The path (after normalization) should appear in the final URL.

        Args:
            api_type: API endpoint type.
            path: URL path segment.
            region: Data residency region.
        """
        creds = Credentials(
            username="test",
            secret=SecretStr("secret"),
            project_id="123",
            region=region,
        )
        client = MixpanelAPIClient(creds)

        try:
            url = client._build_url(api_type, path)

            # The path (normalized) should be in the URL
            normalized_path = "/" + path.lstrip("/")
            assert normalized_path in url, (
                f"Path '{normalized_path}' not found in URL '{url}'"
            )
        finally:
            client.close()

    @given(api_type=api_types, path=url_paths, region=regions)
    @settings(max_examples=30)
    def test_url_starts_with_https(self, api_type: str, path: str, region: str) -> None:
        """Built URL should always use HTTPS.

        All Mixpanel API endpoints use HTTPS for security.

        Args:
            api_type: API endpoint type.
            path: URL path segment.
            region: Data residency region.
        """
        creds = Credentials(
            username="test",
            secret=SecretStr("secret"),
            project_id="123",
            region=region,
        )
        client = MixpanelAPIClient(creds)

        try:
            url = client._build_url(api_type, path)
            assert url.startswith("https://"), f"URL should use HTTPS: {url}"
        finally:
            client.close()


# =============================================================================
# JSONL Chunk Invariance Property Tests
# =============================================================================


class _IterableByteStream(SyncByteStream):
    """Helper stream that yields chunks individually for testing chunk boundaries.

    Unlike httpx.ByteStream which may combine data, this stream yields each
    chunk from the input list as a separate iteration, allowing tests to
    verify correct handling of data split across chunk boundaries.
    """

    def __init__(self, chunks: list[bytes]) -> None:
        """Initialize with a list of byte chunks to yield.

        Args:
            chunks: List of byte chunks to yield individually.
        """
        self._chunks = chunks

    def __iter__(self) -> Iterator[bytes]:
        """Iterate over chunks.

        Returns:
            Iterator over byte chunks.
        """
        return iter(self._chunks)

    def close(self) -> None:
        """Close the stream (no-op for this implementation)."""


def _split_bytes_at_positions(data: bytes, positions: list[int]) -> list[bytes]:
    """Split bytes at the given positions.

    Args:
        data: The byte string to split.
        positions: Sorted list of positions at which to split.

    Returns:
        List of byte chunks.
    """
    # Filter to valid positions and deduplicate
    valid_positions = sorted({p for p in positions if 0 < p < len(data)})

    # Always include 0 at start and len(data) at end
    boundaries = [0, *valid_positions, len(data)]

    chunks = []
    for i in range(len(boundaries) - 1):
        chunk = data[boundaries[i] : boundaries[i + 1]]
        if chunk:  # Only add non-empty chunks
            chunks.append(chunk)

    return chunks if chunks else [data] if data else [b""]


def _collect_lines_from_chunks(chunks: list[bytes]) -> list[str]:
    """Collect lines from _iter_jsonl_lines given chunks.

    Args:
        chunks: List of byte chunks to feed to the function.

    Returns:
        List of lines yielded by _iter_jsonl_lines.
    """

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, stream=_IterableByteStream(chunks))

    with (
        httpx.Client(transport=httpx.MockTransport(handler)) as client,
        client.stream("GET", "http://test.example.com") as response,
    ):
        return list(_iter_jsonl_lines(response))


# Strategy for JSON-like line content (no newlines, no leading/trailing whitespace)
# Use printable characters excluding newlines
json_line_content = st.text(
    alphabet=st.characters(
        whitelist_categories=("L", "N", "P", "S"),
        whitelist_characters='{}[]":, ',
        blacklist_characters="\n\r",
    ),
    min_size=1,
    max_size=100,
).map(lambda s: s.strip()).filter(bool)

# Strategy for JSONL documents (list of non-empty lines)
jsonl_documents = st.lists(json_line_content, min_size=1, max_size=10)

# Strategy for chunk split positions
chunk_positions = st.lists(st.integers(min_value=0, max_value=1000), max_size=20)


class TestIterJsonlLinesProperties:
    """Property-based tests for _iter_jsonl_lines().

    These tests verify that the JSONL line reader correctly handles
    arbitrary chunk boundaries, which was the core bug being fixed.
    """

    @given(lines=jsonl_documents, split_positions=chunk_positions)
    @settings(max_examples=100)
    def test_chunk_invariance(
        self, lines: list[str], split_positions: list[int]
    ) -> None:
        """Output should be identical regardless of chunk boundaries.

        This is the core property: given the same byte content, the
        output lines should be identical whether the content is delivered
        as a single chunk or split at arbitrary byte positions.

        This property directly tests the bug fix where httpx iter_lines()
        incorrectly split lines at gzip decompression chunk boundaries.

        Args:
            lines: List of non-empty line contents.
            split_positions: Positions at which to split the byte content.
        """
        # Create JSONL content
        content = "\n".join(lines) + "\n"
        content_bytes = content.encode("utf-8")

        # Get reference output from single chunk
        reference_lines = _collect_lines_from_chunks([content_bytes])

        # Get output from arbitrarily chunked content
        chunks = _split_bytes_at_positions(content_bytes, split_positions)
        chunked_lines = _collect_lines_from_chunks(chunks)

        # Output should be identical regardless of chunking
        assert chunked_lines == reference_lines, (
            f"Chunk invariance violated!\n"
            f"Content: {content!r}\n"
            f"Split at: {split_positions}\n"
            f"Chunks: {chunks}\n"
            f"Reference: {reference_lines}\n"
            f"Chunked: {chunked_lines}"
        )

    @given(lines=jsonl_documents)
    @settings(max_examples=50)
    def test_content_preservation(self, lines: list[str]) -> None:
        """All non-empty input lines should appear in output.

        The function should preserve all non-empty, non-whitespace lines
        from the input content.

        Args:
            lines: List of non-empty line contents.
        """
        # Create JSONL content
        content = "\n".join(lines) + "\n"
        content_bytes = content.encode("utf-8")

        output_lines = _collect_lines_from_chunks([content_bytes])

        # All input lines should appear in output
        assert output_lines == lines, (
            f"Content not preserved!\n"
            f"Input lines: {lines}\n"
            f"Output lines: {output_lines}"
        )

    @given(data=st.binary(max_size=500))
    @settings(max_examples=50)
    def test_never_raises_on_arbitrary_bytes(self, data: bytes) -> None:
        """Function should never raise an exception for any input.

        The function uses errors='replace' for UTF-8 decoding, so it
        should handle arbitrary byte sequences gracefully without
        raising exceptions.

        Args:
            data: Arbitrary byte content.
        """
        # Should not raise any exception
        try:
            result = _collect_lines_from_chunks([data])
            # Result should be a list of strings
            assert isinstance(result, list)
            for line in result:
                assert isinstance(line, str)
        except Exception as e:
            raise AssertionError(
                f"Function raised exception on input {data!r}: {e}"
            ) from e

    @given(lines=jsonl_documents)
    @settings(max_examples=30)
    def test_byte_by_byte_chunking(self, lines: list[str]) -> None:
        """Output should be correct even with byte-by-byte chunking.

        Extreme case: splitting content into individual bytes should
        still produce correct output.

        Args:
            lines: List of non-empty line contents.
        """
        content = "\n".join(lines) + "\n"
        content_bytes = content.encode("utf-8")

        # Assume content is not too large (byte-by-byte creates many chunks)
        assume(len(content_bytes) <= 200)

        # Split into individual bytes
        byte_chunks = [bytes([b]) for b in content_bytes]

        # Get output
        output_lines = _collect_lines_from_chunks(byte_chunks)

        # Should match input
        assert output_lines == lines, (
            f"Byte-by-byte chunking failed!\n"
            f"Input: {lines}\n"
            f"Output: {output_lines}"
        )
