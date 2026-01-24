"""Tests for Skills Provider integration.

These tests verify that the mp_mcp skill and its reference files are
properly registered as MCP resources via the SkillsDirectoryProvider.
"""

import pytest


class TestSkillsProviderConfiguration:
    """Tests for skills provider setup."""

    def test_skills_directory_path_is_absolute(self) -> None:
        """Skills directory path should be absolute."""
        from mp_mcp.server import _SKILLS_DIR

        assert _SKILLS_DIR.is_absolute()

    def test_skills_directory_path_is_resolved(self) -> None:
        """Skills directory path should not contain relative components."""
        from mp_mcp.server import _SKILLS_DIR

        # Resolved paths should equal themselves when resolved again
        assert _SKILLS_DIR.resolve() == _SKILLS_DIR

    def test_mp_mcp_skill_structure_exists(self) -> None:
        """mp_mcp skill should have required directory structure."""
        from mp_mcp.server import _SKILLS_DIR

        skill_dir = _SKILLS_DIR / "mp_mcp"
        assert skill_dir.exists(), f"Expected skill directory at {skill_dir}"
        assert (skill_dir / "SKILL.md").exists(), "SKILL.md missing"
        assert (skill_dir / "references").is_dir(), "references directory missing"

    def test_mp_mcp_skill_has_all_reference_files(self) -> None:
        """mp_mcp skill should have all expected reference files."""
        from mp_mcp.server import _SKILLS_DIR

        skill_dir = _SKILLS_DIR / "mp_mcp"
        refs_dir = skill_dir / "references"

        expected_files = ["tools.md", "resources.md", "prompts.md", "patterns.md"]
        for filename in expected_files:
            assert (refs_dir / filename).exists(), f"Reference file {filename} missing"


class TestSkillResourceRegistration:
    """Tests for skill resource registration with MCP server."""

    def test_mp_mcp_skill_main_file_registered(
        self, registered_resource_uris: list[str]
    ) -> None:
        """mp_mcp SKILL.md should be registered as a resource."""
        assert "skill://mp_mcp/SKILL.md" in registered_resource_uris

    def test_mp_mcp_skill_manifest_registered(
        self, registered_resource_uris: list[str]
    ) -> None:
        """mp_mcp manifest should be registered for content hashing."""
        assert "skill://mp_mcp/_manifest" in registered_resource_uris

    @pytest.mark.parametrize(
        "reference_file",
        ["tools.md", "resources.md", "prompts.md", "patterns.md"],
    )
    def test_mp_mcp_reference_files_registered(
        self, registered_resource_uris: list[str], reference_file: str
    ) -> None:
        """mp_mcp reference files should be registered as resources."""
        expected_uri = f"skill://mp_mcp/references/{reference_file}"
        assert expected_uri in registered_resource_uris, (
            f"Expected {expected_uri} in registered resources"
        )

    def test_mixpanel_data_skill_also_registered(
        self, registered_resource_uris: list[str]
    ) -> None:
        """Existing mixpanel-data skill should also be exposed."""
        assert "skill://mixpanel-data/SKILL.md" in registered_resource_uris


class TestSkillResourceContent:
    """Tests for skill resource content accessibility."""

    @pytest.mark.asyncio
    async def test_mp_mcp_skill_content_readable(self) -> None:
        """mp_mcp SKILL.md content should be readable via MCP."""
        from fastmcp import Client

        from mp_mcp.server import mcp

        async with Client(mcp) as client:
            result = await client.read_resource("skill://mp_mcp/SKILL.md")
            # result is a list of content items
            assert len(result) > 0
            content = result[0].text if hasattr(result[0], "text") else str(result[0])
            assert "Mixpanel MCP Server" in content
            assert "Tool Categories" in content

    @pytest.mark.asyncio
    async def test_mp_mcp_tools_reference_readable(self) -> None:
        """mp_mcp tools reference should contain tool documentation."""
        from fastmcp import Client

        from mp_mcp.server import mcp

        async with Client(mcp) as client:
            result = await client.read_resource("skill://mp_mcp/references/tools.md")
            assert len(result) > 0
            content = result[0].text if hasattr(result[0], "text") else str(result[0])
            # Should contain tool documentation
            assert "list_events" in content
            assert "segmentation" in content
            assert "fetch_events" in content
