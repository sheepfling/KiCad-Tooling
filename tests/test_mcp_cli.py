"""MCP stdio CLI checkout selection and protocol startup."""

from __future__ import annotations

import os
import subprocess
import sys

import pytest
from mcp import Client, StdioServerParameters

from tests.mcp_test_support import DEFAULT_TOOLS, McpTestCase

pytestmark = [pytest.mark.slow, pytest.mark.template_checkout]


class McpTests(McpTestCase):
    async def test_stdio_cli_uses_explicit_checkout_from_unrelated_working_directory(self) -> None:
        caller = self.base / "caller"
        caller.mkdir()
        parameters = StdioServerParameters(
            command=sys.executable,
            args=["-B", "-m", "kicad_tooling.mcp", "--root", str(self.root)],
            cwd=caller,
            env={"PYTHONDONTWRITEBYTECODE": "1"},
        )
        async with Client(parameters, mode="legacy", read_timeout_seconds=20) as client:
            self.assertIsNotNone(client.server_info)
            data = self.structured(await client.call_tool("list_projects"))
            self.assertIn("controller", {project["id"] for project in data["projects"]})
            listing = await client.list_tools()
            self.assertEqual({tool.name for tool in listing.tools}, DEFAULT_TOOLS)
        self.assertEqual(list(caller.iterdir()), [])

    def test_cli_refuses_implicit_or_relative_checkout_selection(self) -> None:
        environment = os.environ | {"PYTHONDONTWRITEBYTECODE": "1"}
        for arguments in ((), ("--root", "repository")):
            with self.subTest(arguments=arguments):
                result = subprocess.run(
                    (sys.executable, "-I", "-B", "-m", "kicad_tooling.mcp", *arguments),
                    cwd=self.base,
                    env=environment,
                    capture_output=True,
                    text=True,
                    input="",
                    timeout=20,
                    check=False,
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stdout, "")
                self.assertIn("root", result.stderr.lower())
