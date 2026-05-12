"""PKCE (Proof Key for Code Exchange) challenge generation.

Implements RFC 7636 PKCE for OAuth 2.0 Authorization Code flow.
Generates cryptographically secure code verifier and code challenge pairs
using SHA-256 hashing and base64url encoding.

Example:
    ```python
    from mixpanel_headless._internal.auth.pkce import PkceChallenge

    challenge = PkceChallenge.generate()
    # challenge.verifier  -> 86-char base64url string
    # challenge.challenge  -> 43-char base64url SHA-256 hash
    ```
"""

from __future__ import annotations

import base64
import hashlib
import secrets
from dataclasses import dataclass


@dataclass(frozen=True)
class PkceChallenge:
    """Immutable PKCE code verifier and challenge pair.

    A frozen dataclass containing a cryptographically secure code verifier
    and its corresponding SHA-256 code challenge, as specified in RFC 7636.

    The verifier is 86 characters of base64url-encoded random bytes (64 bytes).
    The challenge is the base64url-encoded SHA-256 hash of the verifier.

    Attributes:
        verifier: Base64url-encoded code verifier (86 chars, no padding).
        challenge: Base64url-encoded SHA-256 hash of the verifier (43 chars, no padding).
    """

    verifier: str
    """Base64url-encoded code verifier (86 chars, no padding)."""

    challenge: str
    """Base64url-encoded SHA-256 hash of the verifier (43 chars, no padding)."""

    @classmethod
    def generate(cls) -> PkceChallenge:
        """Generate a new PKCE verifier/challenge pair.

        Creates 64 cryptographically secure random bytes, encodes them as
        a base64url string (no padding) for the verifier, then computes
        the SHA-256 hash of the verifier encoded as base64url (no padding)
        for the challenge.

        Returns:
            A new PkceChallenge with verifier and challenge fields set.

        Example:
            ```python
            pkce = PkceChallenge.generate()
            assert len(pkce.verifier) == 86
            assert len(pkce.challenge) == 43
            ```
        """
        random_bytes = secrets.token_bytes(64)
        verifier = base64.urlsafe_b64encode(random_bytes).rstrip(b"=").decode("ascii")

        challenge_hash = hashlib.sha256(verifier.encode("ascii")).digest()
        challenge = (
            base64.urlsafe_b64encode(challenge_hash).rstrip(b"=").decode("ascii")
        )

        return cls(verifier=verifier, challenge=challenge)
