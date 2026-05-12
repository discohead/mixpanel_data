"""Unit tests for PKCE challenge generation (T007).

Tests the PkceChallenge class which implements RFC 7636 PKCE
(Proof Key for Code Exchange) for OAuth 2.0 authorization.

Verifies:
- Verifier is 86 characters, base64url no-pad encoded
- Challenge is SHA-256 of verifier in base64url no-pad encoding
- Challenge computation is deterministic for the same verifier input
- Each generation produces a different verifier (randomness)
"""

from __future__ import annotations

import base64
import hashlib
import re

from mixpanel_headless._internal.auth.pkce import PkceChallenge

# Base64url alphabet: A-Z, a-z, 0-9, -, _ (no padding =)
BASE64URL_NO_PAD_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")


class TestPkceChallenge:
    """Tests for PkceChallenge.generate() and its attributes."""

    def test_verifier_length_is_86_chars(self) -> None:
        """Verify that the generated verifier is exactly 86 characters.

        RFC 7636 specifies that 64 random bytes base64url-encoded without
        padding produces an 86-character string, which is within the
        required 43-128 character range.
        """
        challenge = PkceChallenge.generate()
        assert len(challenge.verifier) == 86

    def test_verifier_is_base64url_no_pad(self) -> None:
        """Verify that the verifier uses only base64url characters without padding.

        The verifier must contain only characters from the base64url alphabet
        (A-Z, a-z, 0-9, '-', '_') and must not include '=' padding.
        """
        challenge = PkceChallenge.generate()
        assert BASE64URL_NO_PAD_PATTERN.match(challenge.verifier), (
            f"Verifier contains invalid characters: {challenge.verifier}"
        )
        assert "=" not in challenge.verifier

    def test_challenge_is_base64url_no_pad(self) -> None:
        """Verify that the challenge uses only base64url characters without padding.

        The challenge (code_challenge) is the base64url-encoded SHA-256 hash
        of the verifier, without padding.
        """
        challenge = PkceChallenge.generate()
        assert BASE64URL_NO_PAD_PATTERN.match(challenge.challenge), (
            f"Challenge contains invalid characters: {challenge.challenge}"
        )
        assert "=" not in challenge.challenge

    def test_challenge_is_sha256_of_verifier(self) -> None:
        """Verify that the challenge is the SHA-256 hash of the verifier, base64url-encoded.

        Per RFC 7636 Section 4.2:
            code_challenge = BASE64URL(SHA256(code_verifier))

        We independently compute the expected challenge and compare.
        """
        challenge = PkceChallenge.generate()

        # Independently compute SHA-256 of the verifier
        verifier_bytes = challenge.verifier.encode("ascii")
        sha256_digest = hashlib.sha256(verifier_bytes).digest()
        expected_challenge = (
            base64.urlsafe_b64encode(sha256_digest).rstrip(b"=").decode("ascii")
        )

        assert challenge.challenge == expected_challenge

    def test_challenge_computation_is_deterministic(self) -> None:
        """Verify that the same verifier always produces the same challenge.

        Given a fixed verifier string, the SHA-256 hash and base64url encoding
        should always produce the same challenge value.
        """
        challenge = PkceChallenge.generate()

        # Recompute challenge from the verifier twice
        verifier_bytes = challenge.verifier.encode("ascii")
        digest1 = hashlib.sha256(verifier_bytes).digest()
        digest2 = hashlib.sha256(verifier_bytes).digest()

        result1 = base64.urlsafe_b64encode(digest1).rstrip(b"=").decode("ascii")
        result2 = base64.urlsafe_b64encode(digest2).rstrip(b"=").decode("ascii")

        assert result1 == result2
        assert result1 == challenge.challenge

    def test_each_generation_produces_different_verifier(self) -> None:
        """Verify that successive calls to generate() produce different verifiers.

        The verifier is derived from cryptographically random bytes, so each
        generation should be unique. We generate multiple and check they
        are all distinct.
        """
        verifiers = {PkceChallenge.generate().verifier for _ in range(10)}
        assert len(verifiers) == 10, (
            "Expected 10 unique verifiers from 10 generations, "
            f"got {len(verifiers)} unique values"
        )

    def test_each_generation_produces_different_challenge(self) -> None:
        """Verify that successive calls to generate() produce different challenges.

        Since each verifier is unique, the corresponding challenges must also
        be unique.
        """
        challenges = {PkceChallenge.generate().challenge for _ in range(10)}
        assert len(challenges) == 10, (
            "Expected 10 unique challenges from 10 generations, "
            f"got {len(challenges)} unique values"
        )

    def test_challenge_length_is_43_chars(self) -> None:
        """Verify that the challenge is exactly 43 characters.

        SHA-256 produces 32 bytes. Base64url-encoded without padding:
        ceil(32 * 4 / 3) = 43 characters.
        """
        challenge = PkceChallenge.generate()
        assert len(challenge.challenge) == 43

    def test_verifier_and_challenge_are_strings(self) -> None:
        """Verify that verifier and challenge attributes are plain strings.

        Both attributes should be regular str instances, not bytes or other types.
        """
        challenge = PkceChallenge.generate()
        assert isinstance(challenge.verifier, str)
        assert isinstance(challenge.challenge, str)
