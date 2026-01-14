"""Tests for MCP types module.

These tests verify the type classes and dataclasses work correctly.
"""

import time

from mp_mcp_server.types import CacheEntry


class TestCacheEntry:
    """Tests for CacheEntry dataclass."""

    def test_cache_entry_creation(self) -> None:
        """CacheEntry should store value and metadata."""
        now = time.time()
        entry = CacheEntry(key="test_key", value="test_value", created_at=now, ttl=60)

        assert entry.key == "test_key"
        assert entry.value == "test_value"
        assert entry.ttl == 60
        assert entry.created_at == now

    def test_cache_entry_not_expired(self) -> None:
        """is_expired should return False for fresh entry."""
        now = time.time()
        entry = CacheEntry(key="test", value="data", created_at=now, ttl=60)

        assert entry.is_expired is False

    def test_cache_entry_expired(self) -> None:
        """is_expired should return True for expired entry."""
        # Create entry with created_at in the past
        old_time = time.time() - 100  # 100 seconds ago
        entry = CacheEntry(key="test", value="data", created_at=old_time, ttl=50)

        assert entry.is_expired is True

    def test_cache_entry_just_expired(self) -> None:
        """is_expired should return True when past TTL boundary."""
        # Create entry that just expired
        old_time = time.time() - 10.1  # Just over 10 seconds ago
        entry = CacheEntry(key="test", value="data", created_at=old_time, ttl=10)

        assert entry.is_expired is True

    def test_cache_entry_not_yet_expired(self) -> None:
        """is_expired should return False when just under TTL."""
        # Create entry that's almost expired but not quite
        recent_time = time.time() - 9.5  # Just under 10 seconds ago
        entry = CacheEntry(key="test", value="data", created_at=recent_time, ttl=10)

        assert entry.is_expired is False

    def test_cache_entry_zero_ttl(self) -> None:
        """CacheEntry with 0 TTL should expire immediately."""
        now = time.time()
        entry = CacheEntry(key="test", value="data", created_at=now, ttl=0)

        # Even fresh entry with 0 TTL should be expired (0 > 0 is False initially)
        # But any time passing makes it True - wait tiny bit
        import time as time_module

        time_module.sleep(0.01)  # Small delay to ensure some time passed
        assert entry.is_expired is True

    def test_cache_entry_large_ttl(self) -> None:
        """CacheEntry with large TTL should not expire."""
        now = time.time()
        entry = CacheEntry(
            key="test", value="data", created_at=now, ttl=86400 * 365
        )  # 1 year TTL

        assert entry.is_expired is False
